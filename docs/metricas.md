# VisIAqp — endpoints agregados de métricas

## Entrega

Se añadieron seis endpoints autenticados con JWT de usuario. Las agregaciones, conteos, niveles y paginación se calculan en MySQL sobre `resultado_deteccion` y `procesamiento`, sin descargar las ventanas para sumarlas en Python. No se modificó el contrato del motor ni se añadieron servicios externos.

| Endpoint GET | Resultado |
|---|---|
| `/api/metricas/resumen` | Ventanas e identificadores del rango; inventario y ejecuciones actuales sin el límite de 500 filas |
| `/api/metricas/series` | Series por periodo, zona, cámara, fuente y ejecución |
| `/api/metricas/comparativas` | Agregados de las zonas con resultados |
| `/api/metricas/patrones` | Mapa de calor por zona, día de la semana y hora de captura |
| `/api/metricas/distribucion-niveles` | Cantidad de periodos de cada serie según nivel y estado de ocupación |
| `/api/metricas/estado-camaras` | Estado actual a partir de la última transmisión de cada cámara |

La interfaz actual todavía no consume estos endpoints. Su integración corresponde a la siguiente fase.

## Filtros

Los primeros cinco endpoints aceptan:

- `desde` y `hasta`: fechas en hora de Lima, sin sufijo de zona horaria. El inicio es inclusivo y el final exclusivo. Se selecciona cada ventana por su inicio, no por su fecha de recepción. Por defecto se consultan los últimos siete días; el rango máximo es exactamente 31 días.
- `id_zona`, `id_camara`, `id_procesamiento`, `tipo_fuente` (`imagen`, `video` o `stream`): opcionales. Entidades inexistentes producen 404; filtros incompatibles producen 422.
- `periodo`: `hora` o `dia`. Determina la agrupación de series y distribución. No modifica los conteos del resumen ni la agrupación fija de patrones y comparativas.

Los endpoints paginados aceptan `limite`, de 1 a 1000, y `desplazamiento`, desde cero. El resumen no requiere paginación. Todas las páginas incluyen `total`, `limite`, `desplazamiento`, `tiene_mas` y `datos`. Los resultados se ordenan de forma estable y no se truncan sin indicación.

El estado de cámaras admite únicamente filtros de zona y cámara, más paginación. Siempre refleja el estado actual; no es una reconstrucción histórica por el rango de eventos.

Ejemplo de serie:

```text
GET /api/metricas/series?desde=2026-10-01T00:00:00&hasta=2026-11-01T00:00:00&periodo=hora&id_zona=1&limite=100
Authorization: Bearer <token de usuario>
```

## Significado de las métricas

`suma_identificadores` suma los conteos por ventana. Puede repetir personas entre ventanas, cámaras y reprocesamientos. No representa entradas, visitantes únicos ni ocupación simultánea.

`promedio_presentes` pondera el promedio de cada ventana por sus segundos observados. `max_presentes` es el máximo de personas presentes en una muestra. `segundos_observados` informa duración observada y no certifica cobertura completa del periodo. No se suman ocupaciones entre zonas o cámaras.

Los niveles utilizan los umbrales actuales de la zona, con valores predeterminados 10 y 30 cuando no hay configuración. Se calculan al consultar; por tanto, cambiar un umbral afecta inmediatamente las respuestas nuevas sin requerir recálculo de estos endpoints. Los indicadores históricos materializados del contrato anterior mantienen su funcionamiento independiente.

Los agregados incluyen:

- `cantidad_ventanas`, `ventanas_con_ocupacion`, `camaras_distintas` y `procesamientos_distintos`.
- `primera_ventana_inicio`, `ultima_ventana_fin` y `ultima_recepcion` para distinguir tiempo del evento y tiempo de recepción.
- `estado_ocupacion` y `nivel_ocupacion`, separando ausencias de un cero medido.

Los estados son:

| Estado | Significado |
|---|---|
| `disponible` | Todas las ventanas tienen ocupación y proceden de una sola cámara, fuente y ejecución |
| `sin_datos` | Las ventanas seleccionadas solo tienen conteos históricos, sin ocupación medida |
| `datos_incompletos` | Se mezclan ventanas con ocupación y ventanas antiguas sin ella |
| `fuentes_sin_consolidar` | Hay varias cámaras, tipos de fuente o resultados sin cámara |
| `ejecuciones_sin_consolidar` | Hay varias ejecuciones de una misma cámara y fuente |

Salvo en `disponible`, el promedio, máximo, duración y nivel de ocupación se devuelven nulos. La ocupación cero medida sí devuelve cero y nivel bajo. Una consulta sin ventanas devuelve una lista vacía, no una serie de ceros inventados.

Esta política es conservadora: tampoco fusiona automáticamente ejecuciones legítimas que no se superponen, como reconexiones de una transmisión en distintas horas. Se puede filtrar por ejecución o consultar las series separadas. No se implementó todavía una política para excluir o reemplazar reprocesamientos.

## Series, patrones y distribución

Las series conservan `id_zona`, `id_camara`, `id_procesamiento` y `tipo_fuente`. Distintas ejecuciones en una misma hora producen filas distintas. `periodo_cerrado` significa únicamente que el reloj ya pasó el final de la hora o del día; no significa que toda su duración tenga observación.

Las ventanas que atraviesan un límite horario continúan asignándose por su inicio. Los periodos parcialmente incluidos en el rango no se recortan ni se convierten en una estimación del periodo completo. No se generan puntos para huecos sin observaciones.

El mapa de calor utiliza `dia_semana` de 0 (lunes) a 6 (domingo), y `hora` de 0 a 23, según las fechas de captura almacenadas. Las comparativas y patrones solo devuelven grupos con resultados; una zona sin resultados no se presenta como zona de ocupación cero.

La distribución cuenta **periodos por cámara y ejecución**, no horas únicas de una zona ni personas. Las ausencias de medición aparecen con nivel nulo y su estado; no se clasifican como concentración baja. El tiempo sin resultados no forma parte de esta distribución.

## Resumen y estado operativo

En el resumen, `cantidad_ventanas`, `suma_identificadores`, `ventanas_con_ocupacion`, `zonas_con_resultados`, `camaras_con_resultados`, `procesamientos_con_resultados`, `ultima_ventana_fin` y `ultima_recepcion` corresponden al rango de captura y sus filtros.

`camaras_registradas`, `camaras_habilitadas` y `zonas_activas` son inventario actual filtrado por zona y cámara. `procesamientos_en_curso`, `videos_pendientes` y `transmisiones_reportando` son estados actuales, filtrados también por ejecución y tipo de fuente cuando se indican. Estos contadores operativos no se restringen al rango de captura. El resumen no presenta un supuesto total global de personas presentes.

El estado de cámaras consulta la última ejecución de tipo `stream`, aunque haya videos más recientes. Expira las ejecuciones abandonadas con la política de la fase anterior y distingue `reportando`, `sin_actividad`, `sin_transmision`, `interrumpida`, `finalizada` y `deshabilitada`. También conserva el estado de configuración original, incluida la diferencia entre inactiva y mantenimiento.

No devuelve `url_stream`, credenciales ni mensajes internos de error. `edad_imagen_seg` sigue midiendo desde la recepción local hasta el procesamiento; no es latencia desde el sensor remoto.

## Archivos

- `C:\Users\Wilson\Desktop\VisIAqp-backend\visiaqp-api\app\api\routes\metricas.py`
- `C:\Users\Wilson\Desktop\VisIAqp-backend\visiaqp-api\app\crud\metricas.py`
- `C:\Users\Wilson\Desktop\VisIAqp-backend\visiaqp-api\app\schemas\metricas.py`
- `C:\Users\Wilson\Desktop\VisIAqp-backend\visiaqp-api\tests\test_metricas.py`
- `C:\Users\Wilson\Desktop\VisIAqp-backend\visiaqp-api\alembic\versions\e59c3a1248cd_indice_metricas.py`

Se registró el router en `app\api\router.py` y se declaró el índice en `app\models\resultado_deteccion.py`.

## Verificación y migración

Las 99 pruebas del backend aprobaron. Incluyen 26 pruebas nuevas de autenticación, promedio ponderado, cero personas, umbrales, datos históricos, separación de ejecuciones y cámaras, paginación, fechas, rango exclusivo, patrones, distribución y estado operativo. Se comprobó un resumen con 501 videos pendientes para verificar que no dependa del límite anterior de 500 ejecuciones.

El índice `ix_resultado_periodo_proceso`, sobre inicio de ventana y procesamiento, se verificó primero en una copia vacía del esquema real en `visiaqp_test`. Después se aplicó en `visiaqp`, MySQL local 9.4.0, puerto 3306. Se conservaron las cantidades de registros de resultados, indicadores, procesamientos, cámaras y zonas.

Desde `C:\Users\Wilson\Desktop\VisIAqp-backend\visiaqp-api`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

La migración ya está aplicada. Reiniciar el backend para cargar las rutas nuevas si el servidor no usa recarga automática. Los contratos pueden consultarse en `/docs`.

No se modificaron el motor ni el frontend en esta fase, por lo que no se repitieron sus suites. No se midió rendimiento con millones de ventanas ni una carga elevada de usuarios concurrentes. El índice y los rangos acotados ayudan a las consultas, pero no sustituyen esa medición. Continúa vigente el contrato de fechas locales sin zona explícita; migrar a otra zona requiere unificarlo.
