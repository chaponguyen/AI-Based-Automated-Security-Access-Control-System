"""Dependencies xác thực và phân quyền cho FastAPI (B15 CP-04)."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import StaffAccount
from services import auth_service


def require_staff(request: Request, db: Session = Depends(get_db)) -> StaffAccount:
    """Dependency kiểm tra phiên đăng nhập của nhân viên an ninh hoặc ban quản lý.
    
    Yêu cầu cookie 'session' hợp lệ, còn hạn và tài khoản is_active=True.
    Nếu không hợp lệ trả về 401 {"reason": "not_authenticated"}.
    """
    raw_token = request.cookies.get("session")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"reason": "not_authenticated"},
        )

    staff = auth_service.get_session_user(db, raw_token)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"reason": "not_authenticated"},
        )

    return staff


def require_manager(staff: StaffAccount = Depends(require_staff)) -> StaffAccount:
    """Dependency bắt buộc vai trò quản lý (manager).
    
    Nhân viên security bị từ chối với mã 403 {"reason": "forbidden"}.
    """
    if staff.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "forbidden"},
        )
    return staff
