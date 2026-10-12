from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import video as crud_video
from app.schemas.video import VideoOut

router = APIRouter(
    prefix="/videos", tags=["videos"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[VideoOut])
def listar_videos(solo_disponibles: bool = True, db: Session = Depends(get_db)):
    """Catálogo que el motor sincroniza desde su carpeta de videos."""
    return crud_video.listar(db, solo_disponibles)