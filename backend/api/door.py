"""Router API điều khiển cửa mô phỏng (B16 CP-05).

Các route:
- POST /api/door/open: Mở cửa mô phỏng (mọi nhân viên: security và manager).
- GET  /api/door/status: Lấy trạng thái cửa hiện tại (mọi nhân viên: security và manager).
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import require_staff
from database.database import get_db
from database.models import StaffAccount
from services.door_service import get_door_service, _clean_reason
from services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/door", tags=["door"], dependencies=[Depends(require_staff)])


class DoorOpenRequest(BaseModel):
    reason: Optional[str] = None


class DoorOpenResponse(BaseModel):
    state: str = "open"
    open_seconds: int = 10
    until: str
    remaining_seconds: float = 10.0
    already_open: bool


class DoorStatusResponse(BaseModel):
    state: str
    until: Optional[str] = None
    remaining_seconds: float = 0
    by: Optional[str] = None


@router.post("/open", response_model=DoorOpenResponse, status_code=status.HTTP_200_OK)
def open_door(
    payload: Optional[DoorOpenRequest] = None,
    current_staff: StaffAccount = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Mở cửa mô phỏng trong DOOR_OPEN_SECONDS giây (yêu cầu vai trò security hoặc manager).
    
    Quy tắc:
    - Nếu cửa đang đóng: chuyển trạng thái sang mở, hẹn giờ tự đóng sau open_seconds giây.
    - Nếu cửa đang mở: trả already_open=True và KHÔNG kéo dài thời gian mở.
    - Lý do cắt tối đa 200 ký tự và loại bỏ ký tự điều khiển.
    - Ghi nhận nhật ký kiểm toán audit_logs.
    """
    reason_input = payload.reason if payload else None
    door_svc = get_door_service()
    res = door_svc.open(by=current_staff.username, reason=reason_input)

    # Ghi nhận audit log (sử dụng lý do đã loại bỏ ký tự điều khiển và cắt ngắn)
    try:
        clean_reason = _clean_reason(reason_input) or "không ghi"
        detail_msg = f"Mở cửa thủ công (Lý do: {clean_reason})"
        if res.get("already_open"):
            detail_msg = f"Yêu cầu mở khi cửa đang mở (Lý do: {clean_reason})"


        audit_service.record(
            db,
            current_staff,
            "door_open",
            target_type="door",
            target_id=None,
            detail=detail_msg,
        )
    except Exception as e:
        logger.error("Lỗi khi ghi audit door_open: %s", e)

    return res


@router.get("/status", response_model=DoorStatusResponse)
def get_door_status(
    current_staff: StaffAccount = Depends(require_staff),
):
    """Lấy trạng thái cửa hiện tại (yêu cầu vai trò security hoặc manager)."""
    door_svc = get_door_service()
    return door_svc.get_status()
