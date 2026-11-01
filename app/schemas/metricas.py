"""Contratos públicos de métricas; los conteos no representan visitantes únicos."""
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel


class FiltrosMetricas(BaseModel):
    desde: datetime
    hasta: datetime
    periodo: Literal['hora', 'dia'] = 'hora'
    id_zona: int | None = None
    id_camara: int | None = None
    id_procesamiento: int | None = None
    tipo_fuente: Literal['imagen', 'video', 'stream'] | None = None


class ContextoMetricas(BaseModel):
    desde: datetime
    hasta: datetime
    consultado_en: datetime
    zona_horaria: str = 'America/Lima'
    criterio_temporal: str = 'inicio_ventana; desde inclusivo y hasta exclusivo'


class MedicionAgregada(BaseModel):
    id_zona: int
    nombre_zona: str
    cantidad_ventanas: int
    suma_identificadores: int
    ventanas_con_ocupacion: int
    camaras_distintas: int
    procesamientos_distintos: int
    primera_ventana_inicio: datetime
    ultima_ventana_fin: datetime
    ultima_recepcion: datetime
    promedio_presentes: float | None
    max_presentes: int | None
    segundos_observados: float | None
    nivel_ocupacion: Literal['bajo', 'medio', 'alto'] | None
    estado_ocupacion: Literal['disponible', 'sin_datos', 'datos_incompletos',
                              'fuentes_sin_consolidar', 'ejecuciones_sin_consolidar']


class PuntoSerie(MedicionAgregada):
    id_camara: int | None
    id_procesamiento: int
    tipo_fuente: str
    periodo_inicio: datetime
    periodo_fin: datetime
    periodo_cerrado: bool


class PatronHorario(MedicionAgregada):
    dia_semana: int  # Lunes=0, domingo=6.
    hora: int


class DistribucionNivel(BaseModel):
    id_zona: int
    nombre_zona: str
    nivel_ocupacion: str | None
    estado_ocupacion: str
    cantidad_periodos: int


T = TypeVar('T')


class PaginaMetricas(ContextoMetricas, Generic[T]):
    total: int
    limite: int
    desplazamiento: int
    tiene_mas: bool
    datos: list[T]


class ResumenMetricas(ContextoMetricas):
    cantidad_ventanas: int
    suma_identificadores: int
    ventanas_con_ocupacion: int
    zonas_con_resultados: int
    camaras_con_resultados: int
    procesamientos_con_resultados: int
    ultima_ventana_fin: datetime | None
    ultima_recepcion: datetime | None
    camaras_habilitadas: int
    camaras_registradas: int
    zonas_activas: int
    procesamientos_en_curso: int
    videos_pendientes: int
    transmisiones_reportando: int


class EstadoCamara(BaseModel):
    id_camara: int
    id_zona: int
    nombre_camara: str
    nombre_zona: str
    estado_configuracion: str
    estado_operativo: str
    id_procesamiento: int | None
    ultima_actividad: datetime | None
    ultima_muestra: datetime | None
    segundos_sin_actividad: int | None
    fps_procesamiento: float | None
    edad_imagen_seg: float | None


class PaginaCamaras(BaseModel):
    consultado_en: datetime
    zona_horaria: str = 'America/Lima'
    inactividad_limite_seg: int
    total: int
    limite: int
    desplazamiento: int
    tiene_mas: bool
    datos: list[EstadoCamara]
