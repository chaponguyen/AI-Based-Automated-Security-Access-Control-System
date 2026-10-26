"""Dịch vụ nhật ký kiểm toán quản trị hệ thống (B16 CP-04).

Quản lý việc ghi vết kiểm toán (audit trail) cho các hành vi quản trị nhạy cảm:
- login (thành công, bị khóa), logout
- resident_registered, resident_status_changed, resident_deleted
- staff_created, staff_updated, staff_deleted
- logs_deleted
- door_open

Đặc điểm an ninh:
- Bảng audit_logs là nhật ký bất biến (append-only), KHÔNG có API sửa hay xóa.
- Sao chép staff_username vào từng dòng để lưu vết vĩnh viễn kể cả khi tài khoản bị xóa.
"""

from datetime import datetime
import logging
from typing import Any, Optional, Union
from sqlalchemy.orm import Session

from database.models import AuditLog, StaffAccount

logger = logging.getLogger(__name__)


def record(
    db: Session,
    staff: Union[StaffAccount, str, None],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    """Ghi một bản ghi nhật ký kiểm toán vào bảng audit_logs.

    Tham số:
    - db: phiên làm việc SQLAlchemy.
    - staff: đối tượng StaffAccount hoặc chuỗi username hoặc None (hệ thống).
    - action: mã hành động (ví dụ: login, logout, resident_registered, ...).
    - target_type: đối tượng bị tác động (ví dụ: resident, staff, access_logs, door).
    - target_id: ID của đối tượng bị tác động (chuỗi).
    - detail: mô tả chi tiết của hành động.
    - commit: nếu True thì gọi db.commit() ngay; nếu False thì chỉ db.add và db.flush để caller commit cùng transaction.
    """
    staff_id = None
    staff_username = "system"

    if isinstance(staff, StaffAccount):
        staff_id = staff.id
        staff_username = staff.username
    elif isinstance(staff, str) and staff.strip():
        staff_username = staff.strip()
        # Tra cứu xem có tài khoản với username này không
        acc = db.query(StaffAccount).filter(StaffAccount.username == staff_username).first()
        if acc:
            staff_id = acc.id

    now = datetime.utcnow()
    audit_entry = AuditLog(
        staff_id=staff_id,
        staff_username=staff_username,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail,
        timestamp=now,
    )

    try:
        db.add(audit_entry)
        if commit:
            db.commit()
            db.refresh(audit_entry)
        else:
            db.flush()
        logger.info(
            "AuditLog recorded: staff=%s action=%s target_type=%s target_id=%s detail=%s (commit=%s)",
            staff_username,
            action,
            target_type,
            target_id,
            detail,
            commit,
        )
        return audit_entry
    except Exception as e:
        if commit:
            db.rollback()
        logger.error("Lỗi khi ghi AuditLog (%s by %s): %s", action, staff_username, e)
        raise e

