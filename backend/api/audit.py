"""Router API nhật ký kiểm toán quản trị audit_logs (B16 CP-04).

Các route:
- GET /api/audit: Lấy danh sách nhật ký kiểm toán (chỉ manager).
Bảng audit_logs là bất biến (append-only), TUYỆT ĐỐI KHÔNG có route nào sửa hay xóa.
"""

from datetime import datetime
import logging
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
    timestamp: datetime
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
    current_staff: StaffAccount = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Lấy danh sách nhật ký kiểm toán hệ thống (yêu cầu vai trò manager).
    
    Quy tắc:
    - Sắp xếp mới nhất trước (timestamp giảm dần, id giảm dần).
    - Hỗ trợ lọc theo action và tìm kiếm tự do theo từ khóa q.
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

    limit_val = limit if isinstance(limit, int) and 1 <= limit <= 1000 else 200

    # 3. Sắp xếp mới nhất trước
    results = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit_val)
        .all()
    )

    return results
