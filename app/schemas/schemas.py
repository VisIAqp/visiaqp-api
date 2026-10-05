from pydantic import BaseModel
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