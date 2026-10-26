# Agent 2 — Endpoint xác thực khuôn mặt (B6 CP-05)
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.database import get_db
from services.verification_service import verify_image, record_access
from api.deps import require_staff

router = APIRouter(prefix="/api/verify", tags=["verify"], dependencies=[Depends(require_staff)])


@router.post("")
@router.post("/")
def verify_face_api(
    image: UploadFile = File(..., description="Ảnh chụp khuôn mặt cần xác thực (multipart/form-data)"),
    db: Session = Depends(get_db),
):
    """Xác thực khuôn mặt từ ảnh tải lên.

    Contract: POST /api/verify
    Đầu vào: multipart file image (JPEG/PNG)
    Đầu ra: {user, similarity, liveness, decision, reason, box, crop_b64, faces, ms}
    Lỗi: 400 nếu ảnh hỏng, rỗng hoặc không thể giải mã

    Lưu ý: Dùng 'def' thường (đồng bộ) để FastAPI tự động dispatch sang threadpool
    worker (anyio.to_thread.run_sync), không làm chặn asyncio event loop của server.
    """
    if not image or not image.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp ảnh không hợp lệ hoặc thiếu",
        )

    # Đọc dữ liệu ảnh nhị phân
    try:
        contents = image.file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể đọc tệp ảnh: {e}",
        )

    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp ảnh rỗng (0 bytes)",
        )

    # Giải mã ảnh bằng OpenCV
    nparr = np.frombuffer(contents, np.uint8)
    image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image_bgr is None or image_bgr.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp ảnh bị hỏng hoặc không đúng định dạng ảnh (JPEG/PNG)",
        )

    # Thực hiện pipeline nhận diện và xác thực khuôn mặt
    result = verify_image(db, image_bgr)

    # Ghi nhận nhật ký truy cập vào CSDL (bỏ qua nếu không có mặt - no_face)
    record_access(db, result)

    # Tự động mở cửa 10 giây khi xác thực thành công (granted)
    if result.get("decision") == "granted":
        try:
            from services.door_service import get_door_service
            door_svc = get_door_service()
            u_info = result.get("user") or {}
            u_name = u_info.get("full_name") or "Cư dân"
            door_svc.open(by=u_name, reason=f"Xác thực ảnh: {u_name}")
        except Exception as door_err:
            logger.warning("Verify API: Không thể tự động mở cửa: %s", door_err)

    return result
