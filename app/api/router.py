from fastapi import APIRouter

from app.api.routes import motor

api_router = APIRouter(prefix="/api")
api_router.include_router(motor.router)