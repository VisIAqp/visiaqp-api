from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ==================== SCHEMAS ZONAS ====================
class ZonaBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    pais: Optional[str] = "PE"
    latitud: Optional[float] = None
    longitud: Optional[float] = None

class ZonaCreate(ZonaBase):
    pass

class ZonaResponse(ZonaBase):
    id_zona: int
    estado: str
    fecha_registro: datetime

    class Config:
        from_attributes = True

# ==================== SCHEMAS CÁMARAS ====================
class CamaraBase(BaseModel):
    id_zona: int
    nombre: str
    url_stream: str
    tipo: Optional[str] = "fija"
    intervalo_muestreo_seg: Optional[int] = 60
    zone_polygon: Optional[List[List[float]]] = None

class CamaraCreate(CamaraBase):
    pass

class CamaraResponse(CamaraBase):
    id_camara: int
    estado: str
    ultima_conexion: Optional[datetime] = None
    fecha_registro: datetime

    class Config:
        from_attributes = True

# ==================== SCHEMAS CONTEOS Y PROCESAMIENTO ====================

class ResultadoDeteccionCreate(BaseModel):
    periodo_inicio: datetime
    periodo_fin: datetime
    cantidad_peatones: int = Field(..., ge=0)
    confianza_promedio: Optional[float] = Field(None, ge=0.0, le=100.0)

class ResultadoDeteccionResponse(ResultadoDeteccionCreate):
    id_resultado: int
    id_procesamiento: int
    fecha_registro: datetime

    class Config:
        from_attributes = True

# Esquema principal para recibir las detecciones completas enviadas por la IA
class ConteosLoteCreate(BaseModel):
    id_zona: int
    id_camara: Optional[int] = None
    id_usuario: Optional[int] = None
    tipo_fuente: str = Field(..., description="imagen, video o stream")
    ruta_archivo: Optional[str] = None
    fecha_captura_inicio: datetime
    detecciones: List[ResultadoDeteccionCreate]

class ConteosLoteResponse(BaseModel):
    mensaje: str
    id_procesamiento: int
    total_registros_guardados: int