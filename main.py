from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Zona
from app.api import zonas, camaras

app = FastAPI(
    title="VisIAqp API Backend",
    description="API RESTful para el sistema inteligente de análisis de concentración peatonal y prevención de accidentes.",
    version="1.0.0"
)

# Incluir los Routers
app.include_router(zonas.router)
app.include_router(camaras.router)

@app.get("/", tags=["General"])
def root():
    return {
        "sistema": "VisIAqp API Backend",
        "estado": "Operativo",
        "version": "1.0.0"
    }

@app.get("/api/v1/health-check", tags=["General"])
def health_check(db: Session = Depends(get_db)):
    """Endpoint para verificar el estado de conexión con la base de datos MySQL."""
    try:
        zonas_count = db.query(Zona).count()
        return {
            "status": "Conexión a MySQL Exitosa",
            "zonas_registradas": zonas_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {str(e)}")