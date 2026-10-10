from fastapi import APIRouter

from app.api.routes import auth, camaras, indicadores, motor, usuarios, zonas

api_router = APIRouter(prefix="/api")
api_router.include_router(motor.router)
api_router.include_router(auth.router)
api_router.include_router(indicadores.router)
api_router.include_router(zonas.router)
api_router.include_router(camaras.router)
api_router.include_router(usuarios.router)