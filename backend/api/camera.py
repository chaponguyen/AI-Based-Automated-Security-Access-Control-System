from fastapi import APIRouter
from pydantic import BaseModel
from services.camera_service import get_camera

router = APIRouter(prefix="/api/camera", tags=["camera"])


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
