import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.recalculo_indicadores import ejecutar_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    detener = asyncio.Event()
    worker = asyncio.create_task(ejecutar_worker(SessionLocal, detener))
    try:
        yield
    finally:
        detener.set()
        await worker


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

origenes = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}
