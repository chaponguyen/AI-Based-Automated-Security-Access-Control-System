"""API endpoints cho video streaming và snapshot."""
import cv2
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from services.stream_service import generate_mjpeg_stream
from services.camera_service import get_camera
from api.deps import require_staff

router = APIRouter(prefix="/api/stream", tags=["stream"], dependencies=[Depends(require_staff)])


@router.get("")
@router.get("/")
async def stream_video(request: Request):
    """Stream camera trực tiếp định dạng MJPEG (multipart/x-mixed-replace; boundary=frame).
    
    Trình duyệt web có thể hiển thị trực tiếp bằng thẻ:
    <img src="http://localhost:8000/api/stream" />
    """
    return StreamingResponse(
        generate_mjpeg_stream(request),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/snapshot")
def get_snapshot():
    """Trả về 1 ảnh JPEG tĩnh của khung hình camera mới nhất.
    
    Dùng để hiển thị ảnh chụp tức thì khi web chưa bật chế độ xem trực tiếp.
    """
    camera = get_camera()
    ts, frame = camera.latest()
    if frame is None:
        raise HTTPException(status_code=503, detail="Camera chưa có khung hình hoặc đang tắt.")
    ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ret:
        raise HTTPException(status_code=500, detail="Không thể mã hóa khung hình sang JPEG.")
    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
