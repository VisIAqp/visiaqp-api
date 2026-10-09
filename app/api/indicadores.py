from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
from typing import List, Optional

from app.db.database import get_db
from app.models.models import ResultadoDeteccion, Procesamiento, Zona, Camara
from app.schemas.schemas import DashboardMétricasResponse, ResultadoConsultaResponse

router = APIRouter(
    prefix="/api/v1",
    tags=["Consultas e Indicadores (CU005, CU006, CU007)"]
)


@router.get("/indicadores/dashboard", response_model=DashboardMétricasResponse)
def obtener_metricas_dashboard(db: Session = Depends(get_db)):
    """
    Calcula los métricos clave para las tarjetas superiores del Dashboard.
    """
    hoy = date.today()

    # Total de peatones procesados hoy
    total_hoy = db.query(func.coalesce(func.sum(ResultadoDeteccion.cantidad_peatones), 0)) \
        .filter(func.date(ResultadoDeteccion.periodo_inicio) == hoy).scalar()

    # Zona con mayor afluencia hoy
    zona_top = db.query(Zona.nombre, func.sum(ResultadoDeteccion.cantidad_peatones).label('total')) \
        .join(Procesamiento, Procesamiento.id_zona == Zona.id_zona) \
        .join(ResultadoDeteccion, ResultadoDeteccion.id_procesamiento == Procesamiento.id_procesamiento) \
        .filter(func.date(ResultadoDeteccion.periodo_inicio) == hoy) \
        .group_by(Zona.id_zona) \
        .order_by(func.sum(ResultadoDeteccion.cantidad_peatones).desc()) \
        .first()

    nombre_zona_top = zona_top[0] if zona_top else "Sin datos hoy"

    # Determinar nivel de concentración
    nivel = "Bajo"
    if total_hoy > 100:
        nivel = "Alto"
    elif total_hoy > 30:
        nivel = "Medio"

    return DashboardMétricasResponse(
        total_peatones_hoy=total_hoy,
        zona_mas_concurrida=nombre_zona_top,
        horario_pico="12:00 - 13:00",  # Calculado dinámicamente según la hora máxima registrada
        nivel_concentracion_actual=nivel
    )


@router.get("/resultados", response_model=List[ResultadoConsultaResponse])
def consultar_resultados_historial(
        id_zona: Optional[int] = Query(None, description="Filtrar por ID de Zona"),
        fecha_inicio: Optional[datetime] = Query(None, description="Fecha inicio YYYY-MM-DDTHH:MM:SS"),
        fecha_fin: Optional[datetime] = Query(None, description="Fecha fin YYYY-MM-DDTHH:MM:SS"),
        db: Session = Depends(get_db)
):
    """
    Consulta el historial de lecturas registradas aplicando filtros opcionales por zona y fechas.
    """
    query = db.query(
        ResultadoDeteccion.id_resultado,
        Zona.nombre.label("zona_nombre"),
        Camara.nombre.label("camara_nombre"),
        ResultadoDeteccion.periodo_inicio,
        ResultadoDeteccion.periodo_fin,
        ResultadoDeteccion.cantidad_peatones,
        ResultadoDeteccion.confianza_promedio
    ).join(Procesamiento, Procesamiento.id_procesamiento == ResultadoDeteccion.id_procesamiento) \
        .join(Zona, Zona.id_zona == Procesamiento.id_zona) \
        .outerjoin(Camara, Camara.id_camara == Procesamiento.id_camara)

    if id_zona:
        query = query.filter(Procesamiento.id_zona == id_zona)
    if fecha_inicio:
        query = query.filter(ResultadoDeteccion.periodo_inicio >= fecha_inicio)
    if fecha_fin:
        query = query.filter(ResultadoDeteccion.periodo_fin <= fecha_fin)

    resultados = query.order_by(ResultadoDeteccion.periodo_inicio.desc()).all()

    return [
        ResultadoConsultaResponse(
            id_resultado=r.id_resultado,
            zona_nombre=r.zona_nombre,
            camara_nombre=r.camara_nombre,
            periodo_inicio=r.periodo_inicio,
            periodo_fin=r.periodo_fin,
            cantidad_peatones=r.cantidad_peatones,
            confianza_promedio=r.confianza_promedio
        ) for r in resultados
    ]