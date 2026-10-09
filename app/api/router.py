from fastapi import APIRouter

from app.api.routes import auth, motor

api_router = APIRouter(prefix="/api")
api_router.include_router(motor.router)
api_router.include_router(auth.router)