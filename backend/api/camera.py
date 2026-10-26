from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services.camera_service import get_camera
from api.deps import require_staff

router = APIRouter(prefix="/api/camera", tags=["camera"], dependencies=[Depends(require_staff)])


class CameraStatusResponse(BaseModel):
    running: bool
    fps: float
    width: int
    height: int
    viewers: int


@router.get("/status", response_model=CameraStatusResponse)
def get_camera_status():
    """Lấy trạng thái hoạt động hiện tại của camera.
    
    Khớp API CONTRACT: {running, fps, width, height, viewers}.
    """
    camera = get_camera()
    return camera.status()
