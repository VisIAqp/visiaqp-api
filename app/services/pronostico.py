"""Serie de ocupación por cámara y regresión directa a dos horizontes."""
from datetime import datetime, timedelta
from itertools import groupby
from math import ceil, cos, pi, sin

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.camara import Camara
from app.models.procesamiento import Procesamiento
from app.models.resultado_deteccion import ResultadoDeteccion


BLOQUE = timedelta(minutes=5)
ESPERA = timedelta(minutes=1)
VIGENCIA = BLOQUE + 2 * ESPERA
HORIZONTES = (15, 30)
ESQUEMA = 1
COBERTURA_MINIMA = 0.80 * BLOQUE.total_seconds()


class HistorialInsuficiente(ValueError):
    """Todavía faltan ejemplos válidos para entrenar un horizonte."""


def inicio_bloque(fecha: datetime) -> datetime:
    return fecha.replace(minute=fecha.minute // 5 * 5, second=0, microsecond=0)


def camara_apta(camara: Camara) -> bool:
    return camara.estado == "activa" and camara.tipo == "fija" and bool(camara.zone_polygon)


def serie_ocupacion(db: Session, id_camara: int, firma: str, desde: datetime, hasta: datetime) -> dict[datetime, float]:
    r, p = ResultadoDeteccion, Procesamiento
    consulta = (
        select(r.periodo_inicio, r.periodo_fin, r.recibido_en, r.promedio_presentes, r.segundos_observados)
        .join(p, p.id_procesamiento == r.id_procesamiento)
        .where(p.id_camara == id_camara, p.firma_captura == firma, p.tipo_fuente == "stream",
               r.periodo_inicio >= desde, r.periodo_inicio < hasta, r.periodo_fin <= hasta,
               r.recibido_en.is_not(None), r.clave_ventana.is_not(None),
               r.promedio_presentes >= 0, r.max_presentes >= r.promedio_presentes,
               r.max_presentes <= r.cantidad_peatones, r.segundos_observados > 0)
        .order_by(r.periodo_inicio, r.periodo_fin, r.id_resultado)
        .execution_options(yield_per=1000)
    )
    bloques = {}
    with db.execute(consulta) as filas:
        for inicio, ventanas in groupby(filas, key=lambda fila: inicio_bloque(fila[0])):
            fin = inicio + BLOQUE
            previo = inicio
            segundos = personas_segundo = 0.0
            solapado = False
            for a, b, recibido, promedio, observado in ventanas:
                duracion = (b - a).total_seconds()
                # Un bloque se congela un minuto después de cerrar, también en el entrenamiento.
                if (b > fin or recibido > fin + ESPERA or recibido < b - timedelta(seconds=5)
                        or duracion <= 0 or float(observado) > duracion + 0.001):
                    continue
                if a < previo:
                    solapado = True
                    break
                peso = min(float(observado), duracion)
                segundos += peso
                personas_segundo += float(promedio) * peso
                previo = b
            if not solapado and segundos >= COBERTURA_MINIMA:
                bloques[fin] = personas_segundo / segundos
    return bloques


def variables(serie: dict[datetime, float], base: datetime, horizonte: int) -> tuple[float, ...] | None:
    rezagos = tuple(serie.get(base - i * BLOQUE) for i in range(3))
    if any(valor is None for valor in rezagos):
        return None
    objetivo = base + timedelta(minutes=horizonte)
    hora = 2 * pi * (objetivo.hour * 60 + objetivo.minute) / (24 * 60)
    dia = 2 * pi * objetivo.weekday() / 7
    return (*rezagos, sin(hora), cos(hora), sin(dia), cos(dia))


def predecir(artefacto: dict, serie: dict[datetime, float], base: datetime) -> list[dict]:
    resultados = []
    for horizonte in HORIZONTES:
        x = variables(serie, base, horizonte)
        if x is None:
            return []
        modelo = artefacto["horizontes"][str(horizonte)]
        metodo = modelo["metodo"]
        valor = x[0]
        if metodo == "regresion_ridge":
            valor = modelo["intercepto"] + sum(a * b for a, b in zip(modelo["coeficientes"], x, strict=True))
        objetivo = base + timedelta(minutes=horizonte)
        resultados.append({
            "horizonte_min": horizonte,
            "objetivo_en": objetivo.isoformat(),
            "promedio_presentes": round(max(0.0, valor), 2),
            "metodo": metodo,
        })
    return resultados


def entrenar(serie: dict[datetime, float]) -> dict:
    # La dependencia se instala solamente donde se ajusta el modelo.
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error
    from sklearn.preprocessing import StandardScaler

    modelos = {}
    for horizonte in HORIZONTES:
        delta = timedelta(minutes=horizonte)
        ejemplos = []
        for base in sorted(serie):
            x, y = variables(serie, base, horizonte), serie.get(base + delta)
            if x is not None and y is not None:
                ejemplos.append((base, x, y))

        fechas = sorted({base.date() for base, _, _ in ejemplos})
        if len(fechas) < 5:
            raise HistorialInsuficiente(f"{horizonte} min: se requieren ejemplos válidos en al menos cinco fechas")
        dias_validacion = max(2, ceil(len(fechas) / 5))
        corte = datetime.combine(fechas[-dias_validacion], datetime.min.time())
        # Purgar objetivos del entrenamiento que caigan dentro de la validación.
        ajuste = [(x, y) for base, x, y in ejemplos if base + delta + ESPERA < corte]
        validacion = [(x, y) for base, x, y in ejemplos if base >= corte]
        if len(ajuste) < 72 or len(validacion) < 24:
            raise HistorialInsuficiente(
                f"{horizonte} min: {len(ajuste)} ejemplos de ajuste y {len(validacion)} de validación; mínimos 72 y 24"
            )

        x_ajuste, y_ajuste = zip(*ajuste)
        x_val, y_val = zip(*validacion)
        escala = StandardScaler().fit(x_ajuste)
        modelo = Ridge(alpha=1.0).fit(escala.transform(x_ajuste), y_ajuste)
        mae_ridge = float(mean_absolute_error(y_val, modelo.predict(escala.transform(x_val)).clip(min=0)))
        mae_persistencia = float(mean_absolute_error(y_val, [x[0] for x in x_val]))

        x_final, y_final = zip(*[(x, y) for _, x, y in ejemplos])
        escala = StandardScaler().fit(x_final)
        modelo.fit(escala.transform(x_final), y_final)
        coeficientes = modelo.coef_ / escala.scale_
        modelos[str(horizonte)] = {
            "metodo": "regresion_ridge" if mae_ridge < mae_persistencia else "persistencia",
            "coeficientes": coeficientes.tolist(),
            "intercepto": float(modelo.intercept_ - coeficientes @ escala.mean_),
            "mae_ridge": mae_ridge,
            "mae_persistencia": mae_persistencia,
            "ejemplos_ajuste": len(ajuste),
            "ejemplos_validacion": len(validacion),
        }
    return {"esquema": ESQUEMA, "horizontes": modelos}
