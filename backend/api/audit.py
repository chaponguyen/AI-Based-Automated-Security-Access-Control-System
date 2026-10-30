"""Router API nhật ký kiểm toán quản trị audit_logs (B16 CP-04).

Các route:
- GET /api/audit: Lấy danh sách nhật ký kiểm toán (chỉ manager).
Bảng audit_logs là bất biến (append-only), TUYỆT ĐỐI KHÔNG có route nào sửa hay xóa.
"""

from datetime import datetime
import logging
from services.time_service import to_api_iso, parse_filter_dt
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.deps import require_manager
from database.database import get_db
from database.models import AuditLog, StaffAccount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_manager)])


class AuditLogResponse(BaseModel):
    id: int
    timestamp: str  # ISO 8601 có offset — audit_logs lưu UTC
    staff_username: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(200, ge=1, le=1000, description="Số lượng dòng tối đa (mặc định 200, tối đa 1000)"),
    action: Optional[str] = Query(None, description="Lọc theo hành động (ví dụ: login, resident_registered, ...)"),
    q: Optional[str] = Query(None, description="Tìm kiếm theo username, mô tả detail hoặc target_id"),
    from_time: Optional[str] = Query(None, alias="from", description="Thời điểm bắt đầu (ISO 8601)"),
    to_time: Optional[str] = Query(None, alias="to", description="Thời điểm kết thúc (ISO 8601)"),
    current_staff: StaffAccount = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Lấy danh sách nhật ký kiểm toán hệ thống (yêu cầu vai trò manager).
    
    Quy tắc:
    - Sắp xếp mới nhất trước (timestamp giảm dần, id giảm dần).
    - Hỗ trợ lọc theo action và tìm kiếm tự do theo từ khóa q.
    - Hỗ trợ lọc theo khoảng thời gian from/to (audit_logs.timestamp lưu UTC).
    - Giới hạn limit từ 1 đến 1000 dòng (mặc định 200).
    """
    query = db.query(AuditLog)

    # 1. Lọc theo action
    if isinstance(action, str) and action.strip():
        action_clean = action.strip()
        query = query.filter(AuditLog.action == action_clean)

    # 2. Tìm kiếm tự do theo q (staff_username, detail, target_id)
    if isinstance(q, str) and q.strip():
        q_clean = q.strip()
        pattern = f"%{q_clean}%"
        query = query.filter(
            or_(
                AuditLog.staff_username.ilike(pattern),
                AuditLog.detail.ilike(pattern),
                AuditLog.target_id.ilike(pattern),
                AuditLog.action.ilike(pattern),
            )
        )

    # 3. Lọc theo khoảng thời gian from - to
    #    audit_logs.timestamp lưu UTC (Python utcnow()).
    #    parse_filter_dt chuyển chuỗi lọc sang naive theo quy ước UTC.
    if isinstance(from_time, str) and from_time.strip():
        try:
            dt_from = parse_filter_dt(from_time.strip(), "UTC")
            query = query.filter(AuditLog.timestamp >= dt_from)
        except ValueError:
            pass  # Bỏ qua nếu định dạng không hợp lệ

    if isinstance(to_time, str) and to_time.strip():
        try:
            dt_to = parse_filter_dt(to_time.strip(), "UTC")
            query = query.filter(AuditLog.timestamp <= dt_to)
        except ValueError:
            pass  # Bỏ qua nếu định dạng không hợp lệ

    limit_val = limit if isinstance(limit, int) and 1 <= limit <= 1000 else 200

    # 4. Sắp xếp mới nhất trước
    results = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit_val)
        .all()
    )

    # audit_logs.timestamp lưu UTC (Python utcnow()) — gắn offset +00:00
    return [
        AuditLogResponse(
            id=r.id,
            timestamp=to_api_iso(r.timestamp, "UTC"),
            staff_username=r.staff_username,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            detail=r.detail,
        )
        for r in results
    ]

