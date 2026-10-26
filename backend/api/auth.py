"""Router API xác thực người dùng nhân viên và quản lý (B15 CP-03).

Các route:
- POST /api/auth/login: Đăng nhập bằng username, password. Đặt cookie session HttpOnly.
- POST /api/auth/logout: Đăng xuất, thu hồi phiên làm việc, xóa cookie.
- GET  /api/auth/me: Lấy thông tin tài khoản hiện tại từ cookie session.
"""

import datetime
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import StaffAccount
from services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class StaffResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str


@router.post("/login", response_model=StaffResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Đăng nhập nhân viên: xác thực scrypt, đặt cookie session và quản lý khóa tài khoản."""
    username_clean = payload.username.strip().lower()
    password = payload.password
    now = datetime.datetime.utcnow()

    staff = db.query(StaffAccount).filter(StaffAccount.username == username_clean).first()

    # 1. Kiểm tra tài khoản đang bị khóa tạm thời do sai quá số lần
    if staff and staff.locked_until:
        if staff.locked_until > now:
            retry_after_s = int((staff.locked_until - now).total_seconds()) + 1
            return JSONResponse(
                status_code=423,
                content={"reason": "locked", "retry_after_s": max(1, retry_after_s)},
            )
        else:
            # Hết thời gian khóa, tự động mở khóa và reset số lần sai
            staff.locked_until = None
            staff.failed_attempts = 0
            db.commit()

    # 2. Xử lý trường hợp tài khoản không tồn tại hoặc bị vô hiệu hóa
    if not staff or not staff.is_active:
        # Chạy băm giả để chống timing attack (không để lộ username có tồn tại hay không)
        auth_service.verify_password(password, auth_service.DUMMY_PASSWORD_HASH)
        return JSONResponse(status_code=401, content={"reason": "invalid_credentials"})

    # 3. Xác thực mật khẩu scrypt
    is_valid = auth_service.verify_password(password, staff.password_hash)

    # 4. Mật khẩu không đúng: tăng số lần sai và khóa nếu vượt ngưỡng LOGIN_MAX_FAILS
    if not is_valid:
        staff.failed_attempts = (staff.failed_attempts or 0) + 1
        if staff.failed_attempts >= auth_service.LOGIN_MAX_FAILS:
            staff.locked_until = now + datetime.timedelta(minutes=auth_service.LOGIN_LOCK_MINUTES)
            db.commit()
            retry_after_s = auth_service.LOGIN_LOCK_MINUTES * 60
            logger.warning("Tài khoản %s bị khóa tạm thời %s phút do nhập sai 5 lần", staff.username, auth_service.LOGIN_LOCK_MINUTES)
            try:
                from services import audit_service
                audit_service.record(
                    db,
                    staff,
                    "login_locked",
                    target_type="auth",
                    target_id=str(staff.id),
                    detail=f"Khóa tài khoản {auth_service.LOGIN_LOCK_MINUTES} phút do nhập sai 5 lần",
                )
            except Exception as e:
                logger.debug("Lỗi ghi audit login_locked: %s", e)
            return JSONResponse(
                status_code=423,
                content={"reason": "locked", "retry_after_s": retry_after_s},
            )

        db.commit()
        return JSONResponse(status_code=401, content={"reason": "invalid_credentials"})

    # 5. Đăng nhập thành công: reset số lần sai, ghi nhận last_login_at
    staff.failed_attempts = 0
    staff.locked_until = None
    staff.last_login_at = now
    db.commit()

    # Ghi audit login thành công
    try:
        from services import audit_service
        audit_service.record(
            db,
            staff,
            "login",
            target_type="auth",
            target_id=str(staff.id),
            detail="Đăng nhập thành công",
        )
    except Exception as e:
        logger.debug("Lỗi ghi audit login: %s", e)

    # 6. Tạo phiên đăng nhập và gán cookie HttpOnly
    raw_token, session_record = auth_service.create_session(db, staff.id)

    max_age_sec = auth_service.SESSION_HOURS * 3600
    secure_cookie = bool(auth_service.COOKIE_SECURE)

    # Đặt cookie trực tiếp lên đối tượng response
    response.set_cookie(
        key="session",
        value=raw_token,
        max_age=max_age_sec,
        httponly=True,
        samesite="lax",
        path="/",
        secure=secure_cookie,
    )

    return {
        "id": staff.id,
        "username": staff.username,
        "full_name": staff.full_name,
        "role": staff.role,
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Đăng xuất tài khoản, thu hồi phiên làm việc trong DB và xóa cookie."""
    raw_token = request.cookies.get("session")
    if raw_token:
        try:
            current_user = auth_service.get_session_user(db, raw_token)
            if current_user:
                from services import audit_service
                audit_service.record(
                    db,
                    current_user,
                    "logout",
                    target_type="auth",
                    target_id=str(current_user.id),
                    detail="Đăng xuất",
                )
        except Exception as e:
            logger.debug("Lỗi ghi audit logout: %s", e)

        auth_service.revoke_session(db, raw_token)

    response.delete_cookie(
        key="session",
        path="/",
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}


@router.get("/me", response_model=StaffResponse)
def get_me(request: Request, db: Session = Depends(get_db)):
    """Lấy thông tin tài khoản đang đăng nhập từ cookie session."""
    raw_token = request.cookies.get("session")
    staff = auth_service.get_session_user(db, raw_token)

    if not staff:
        return JSONResponse(status_code=401, content={"reason": "not_authenticated"})

    return {
        "id": staff.id,
        "username": staff.username,
        "full_name": staff.full_name,
        "role": staff.role,
    }
