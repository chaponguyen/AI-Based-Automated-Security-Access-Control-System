"""Router quản lý tài khoản nhân viên và ban quản lý (B16 CP-01).

Tất cả các route yêu cầu vai trò 'manager' (require_manager).
Các route:
- GET    /api/staff: Lấy danh sách nhân viên.
- POST   /api/staff: Tạo tài khoản nhân viên mới.
- PATCH  /api/staff/{id}: Cập nhật thông tin nhân viên, đổi vai trò, mật khẩu, trạng thái.
- DELETE /api/staff/{id}: Xóa tài khoản nhân viên.
"""

import datetime
import logging
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import require_manager
from database.database import get_db
from database.models import StaffAccount
from services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/staff", tags=["staff"], dependencies=[Depends(require_manager)])

USERNAME_REGEX = re.compile(r"^[a-z0-9._-]+$")


class StaffResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime.datetime] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class StaffCreateRequest(BaseModel):
    username: str
    full_name: str
    password: str
    role: str


class StaffUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


def _record_audit(
    db: Session,
    staff: StaffAccount,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[str] = None,
    commit: bool = True,
) -> None:
    """Ghi vết kiểm toán an toàn."""
    try:
        from services import audit_service
        audit_service.record(
            db,
            staff=staff,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            commit=commit,
        )
    except Exception as e:
        logger.debug("Ghi audit thất bại: %s", e)
        raise e


@router.get("", response_model=List[StaffResponse])
def get_staff_list(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả tài khoản nhân viên trong hệ thống (manager)."""
    staff_list = db.query(StaffAccount).order_by(StaffAccount.id.asc()).all()
    return staff_list


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StaffResponse)
def create_staff(
    payload: StaffCreateRequest,
    current_staff: StaffAccount = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Tạo tài khoản nhân viên mới (manager).
    
    Quy tắc:
    - username lưu chữ thường, 3 đến 50 ký tự [a-z0-9._-].
    - full_name từ 2 đến 150 ký tự.
    - password tối thiểu 8 ký tự.
    - role chỉ nhận 'security' hoặc 'manager'.
    - Trùng username trả 409 {"reason": "username_taken"}.
    - Sai định dạng trả 422.
    """
    username_clean = payload.username.strip().lower()
    full_name_clean = payload.full_name.strip()

    # 1. Kiểm tra định dạng username
    if len(username_clean) < 3 or len(username_clean) > 50 or not USERNAME_REGEX.match(username_clean):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "invalid_username", "message": "Tên đăng nhập phải từ 3 đến 50 ký tự [a-z0-9._-]"},
        )

    # 2. Kiểm tra định dạng full_name
    if len(full_name_clean) < 2 or len(full_name_clean) > 150:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "invalid_full_name", "message": "Họ và tên phải từ 2 đến 150 ký tự"},
        )

    # 3. Kiểm tra độ dài mật khẩu
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "invalid_password", "message": "Mật khẩu phải có tối thiểu 8 ký tự"},
        )

    # 4. Kiểm tra vai trò
    if payload.role not in ("security", "manager"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "invalid_role", "message": "Vai trò chỉ được là 'security' hoặc 'manager'"},
        )

    # 5. Kiểm tra trùng username
    existing = db.query(StaffAccount).filter(StaffAccount.username == username_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "username_taken"},
        )

    # 6. Băm mật khẩu scrypt và lưu tài khoản mới
    password_hash = auth_service.hash_password(payload.password)
    new_staff = StaffAccount(
        username=username_clean,
        full_name=full_name_clean,
        password_hash=password_hash,
        role=payload.role,
        is_active=True,
        failed_attempts=0,
    )
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)

    # 7. Ghi audit log
    _record_audit(
        db,
        current_staff,
        "staff_created",
        target_type="staff",
        target_id=str(new_staff.id),
        detail=f"Tạo tài khoản {new_staff.username} vai trò {new_staff.role}",
    )

    return new_staff


@router.patch("/{id}", response_model=StaffResponse)
def update_staff(
    id: int,
    payload: StaffUpdateRequest,
    current_staff: StaffAccount = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin tài khoản nhân viên (manager).
    
    Quy tắc bảo vệ:
    - Không tự tắt tài khoản hoặc tự hạ quyền chính mình (409 self_protected).
    - Không tắt tài khoản hoặc hạ quyền manager đang hoạt động cuối cùng (409 last_manager).
    - Đổi mật khẩu, đổi vai trò hoặc tắt tài khoản thì thu hồi mọi phiên của tài khoản đó.
    - Mật khẩu không bao giờ nằm trong phản hồi hay log.
    """
    target = db.query(StaffAccount).filter(StaffAccount.id == id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "not_found"},
        )

    # 1. Kiểm tra luật tự bảo vệ (self_protected)
    if target.id == current_staff.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "self_protected"},
            )
        if payload.role is not None and payload.role != "manager":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "self_protected"},
            )

    # 2. Kiểm tra luật bảo vệ manager cuối cùng (last_manager)
    if target.role == "manager" and target.is_active:
        will_deactivate = (payload.is_active is False)
        will_downgrade = (payload.role is not None and payload.role != "manager")
        if will_deactivate or will_downgrade:
            active_managers_count = (
                db.query(func.count(StaffAccount.id))
                .filter(StaffAccount.role == "manager", StaffAccount.is_active == True)
                .scalar()
                or 0
            )
            if active_managers_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"reason": "last_manager"},
                )

    # 3. Validate các trường nếu được cung cấp
    if payload.full_name is not None:
        fn_clean = payload.full_name.strip()
        if len(fn_clean) < 2 or len(fn_clean) > 150:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_full_name", "message": "Họ và tên phải từ 2 đến 150 ký tự"},
            )
        target.full_name = fn_clean

    if payload.role is not None:
        if payload.role not in ("security", "manager"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_role", "message": "Vai trò chỉ được là 'security' hoặc 'manager'"},
            )

    if payload.password is not None:
        if len(payload.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_password", "message": "Mật khẩu phải có tối thiểu 8 ký tự"},
            )

    # 4. Áp dụng thay đổi và xác định nhu cầu thu hồi phiên
    revoke_needed = False
    details = []

    if payload.password is not None:
        target.password_hash = auth_service.hash_password(payload.password)
        revoke_needed = True
        details.append("đổi mật khẩu")

    if payload.is_active is not None and target.is_active != payload.is_active:
        target.is_active = payload.is_active
        if not payload.is_active:
            revoke_needed = True
        details.append(f"trạng thái={target.is_active}")

    if payload.role is not None and target.role != payload.role:
        old_role = target.role
        target.role = payload.role
        revoke_needed = True
        details.append(f"vai trò {old_role}->{target.role}")

    if payload.full_name is not None:
        details.append("cập nhật họ tên")

    db.commit()
    db.refresh(target)

    # 5. Thu hồi mọi phiên nếu có thay đổi nhạy cảm (mật khẩu, tắt tài khoản, đổi vai trò)
    if revoke_needed:
        revoked_count = auth_service.revoke_all_staff_sessions(db, target.id)
        logger.info("Đã thu hồi %d phiên của tài khoản %s sau khi cập nhật thông tin", revoked_count, target.username)

    # 6. Ghi audit log
    _record_audit(
        db,
        current_staff,
        "staff_updated",
        target_type="staff",
        target_id=str(target.id),
        detail=", ".join(details) if details else "không thay đổi",
    )

    return target


@router.delete("/{id}")
def delete_staff(
    id: int,
    current_staff: StaffAccount = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Xóa tài khoản nhân viên (manager).
    
    Quy tắc bảo vệ:
    - Không tự xóa tài khoản chính mình (409 self_protected).
    - Không xóa manager đang hoạt động cuối cùng (409 last_manager).
    - Trả về 200 {"ok": true} khi thành công.
    - Không tìm thấy trả 404 {"reason": "not_found"}.
    """
    target = db.query(StaffAccount).filter(StaffAccount.id == id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "not_found"},
        )

    # 1. Tự bảo vệ
    if target.id == current_staff.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "self_protected"},
        )

    # 2. Bảo vệ manager cuối cùng
    if target.role == "manager" and target.is_active:
        active_managers_count = (
            db.query(func.count(StaffAccount.id))
            .filter(StaffAccount.role == "manager", StaffAccount.is_active == True)
            .scalar()
            or 0
        )
        if active_managers_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "last_manager"},
            )

    deleted_username = target.username
    target_id = target.id

    # 3. Xóa tài khoản (các session sẽ tự động CASCADE xóa theo FK)
    # và ghi vết kiểm toán trong CÙNG TRANSACTION (nếu lỗi thì rollback)
    try:
        db.delete(target)
        from services import audit_service
        audit_service.record(
            db,
            current_staff,
            "staff_deleted",
            target_type="staff",
            target_id=str(target_id),
            detail=f"Xóa tài khoản {deleted_username}",
            commit=False,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Lỗi khi xóa tài khoản staff hoặc ghi audit: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"reason": "database_error", "message": "Không thể xóa tài khoản"},
        )

    return {"ok": True}
