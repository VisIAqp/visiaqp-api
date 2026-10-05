from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Numeric, Text, JSON
from sqlalchemy.sql import func
from app.db.database import Base

class Rol(Base):
    __tablename__ = "rol"
    id_rol = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False, unique=True)
    descripcion = Column(String(150), nullable=True)

class Usuario(Base):
    __tablename__ = "usuario"
    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    id_rol = Column(Integer, ForeignKey("rol.id_rol"), nullable=False)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(120), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    estado = Column(Enum('activo', 'inactivo', name='estado_usuario_enum'), default='activo')
    fecha_registro = Column(DateTime, default=func.now())

class Zona(Base):
    __tablename__ = "zona"
    id_zona = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(String(255), nullable=True)
    ubicacion = Column(String(150), nullable=True)
    pais = Column(String(2), default='PE')
    # Corregido: Decimal -> Numeric
    latitud = Column(Numeric(10, 7), nullable=True)
    longitud = Column(Numeric(10, 7), nullable=True)
    estado = Column(Enum('activa', 'inactiva', name='estado_zona_enum'), default='activa')
    fecha_registro = Column(DateTime, default=func.now())

class Camara(Base):
    __tablename__ = "camara"
    id_camara = Column(Integer, primary_key=True, autoincrement=True)
    id_zona = Column(Integer, ForeignKey("zona.id_zona"), nullable=False)
    nombre = Column(String(100), nullable=False)
    url_stream = Column(String(255), nullable=False)
    tipo = Column(Enum('fija', 'movil', name='tipo_camara_enum'), default='fija')
    estado = Column(Enum('activa', 'inactiva', 'mantenimiento', name='estado_camara_enum'), default='activa')
    intervalo_muestreo_seg = Column(Integer, default=60)
    zone_polygon = Column(JSON, nullable=True)
    ultima_conexion = Column(DateTime, nullable=True)
    fecha_registro = Column(DateTime, default=func.now())

class Procesamiento(Base):
    __tablename__ = "procesamiento"
    id_procesamiento = Column(Integer, primary_key=True, autoincrement=True)
    id_zona = Column(Integer, ForeignKey("zona.id_zona"), nullable=False)
    id_camara = Column(Integer, nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=True)
    tipo_fuente = Column(Enum('imagen', 'video', 'stream', name='tipo_fuente_enum'), nullable=False)
    ruta_archivo = Column(String(255), nullable=True)
    fecha_captura_inicio = Column(DateTime, nullable=False)
    fecha_inicio_proceso = Column(DateTime, default=func.now())
    fecha_fin_proceso = Column(DateTime, nullable=True)
    estado = Column(Enum('pendiente', 'procesando', 'completado', 'error', name='estado_procesamiento_enum'), default='pendiente')
    mensaje_error = Column(Text, nullable=True)

class ResultadoDeteccion(Base):
    __tablename__ = "resultado_deteccion"
    id_resultado = Column(Integer, primary_key=True, autoincrement=True)
    id_procesamiento = Column(Integer, ForeignKey("procesamiento.id_procesamiento"), nullable=False)
    periodo_inicio = Column(DateTime, nullable=False)
    periodo_fin = Column(DateTime, nullable=False)
    cantidad_peatones = Column(Integer, nullable=False)
    # Corregido: Decimal -> Numeric
    confianza_promedio = Column(Numeric(5, 2), nullable=True)