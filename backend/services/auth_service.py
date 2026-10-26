"""Dịch vụ băm mật khẩu và quản lý phiên làm việc nhân viên (B15 CP-02).

Quy tắc kỹ thuật:
- Thuần thư viện chuẩn Python (hashlib, hmac, secrets, datetime).
- Băm mật khẩu bằng scrypt (n=16384, r=8, p=1, salt 16 bytes ngẫu nhiên).
- Định dạng chuỗi băm: 'scrypt$n$r$p$salt_hex$hash_hex'.
- Mật khẩu tối thiểu 8 ký tự.
- So sánh mật khẩu an toàn chống timing attack bằng hmac.compare_digest.
- Token phiên URL-safe 32 bytes (secrets.token_urlsafe(32)), lưu băm sha256 vào DB.
"""

import datetime
import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from database.models import StaffAccount, StaffSession

logger = logging.getLogger(__name__)

# Cấu hình môi trường
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))
LOGIN_MAX_FAILS = int(os.getenv("LOGIN_MAX_FAILS", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "5"))
COOKIE_SECURE = int(os.getenv("COOKIE_SECURE", "0"))  # 0: HTTP dev, 1: HTTPS production

# Tham số scrypt theo thiết kế B15
SCRYPT_N = 2**14  # 16384
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_LEN = 32
MIN_PASSWORD_LENGTH = 8

# Chuỗi băm mẫu chuẩn bị sẵn cho kỹ thuật chống timing attack khi tài khoản không tồn tại (CP-03)
DUMMY_SALT_HEX = "0102030405060708090a0b0c0d0e0f10"
_dummy_derived = hashlib.scrypt(
    b"dummy_timing_padding_password",
    salt=bytes.fromhex(DUMMY_SALT_HEX),
    n=SCRYPT_N,
    r=SCRYPT_R,
    p=SCRYPT_P,
    maxmem=0,
    dklen=KEY_LEN,
).hex()
DUMMY_PASSWORD_HASH = f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${DUMMY_SALT_HEX}${_dummy_derived}"


def hash_password(password: str) -> str:
    """Băm mật khẩu người dùng bằng thuật toán scrypt với muối ngẫu nhiên 16 bytes.

    Định dạng trả về: 'scrypt$n$r$p$salt_hex$hash_hex'
    Yêu cầu mật khẩu tối thiểu 8 ký tự.
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Mật khẩu phải có độ dài tối thiểu {MIN_PASSWORD_LENGTH} ký tự.")

    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=0,
        dklen=KEY_LEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Xác thực mật khẩu đã nhập với chuỗi băm lưu trữ bằng hmac.compare_digest.

    Chống lộ thời gian phản hồi (timing attack).
    """
    if not password or not stored_hash:
        return False

    try:
        parts = stored_hash.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False

        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        expected_hash = bytes.fromhex(parts[5])

        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=0,
            dklen=len(expected_hash),
        )
        return hmac.compare_digest(actual_hash, expected_hash)
    except Exception as e:
        logger.debug("Lỗi khi giải mã hoặc so khớp mật khẩu scrypt: %s", e)
        return False


def hash_token(raw_token: str) -> str:
    """Tính băm SHA-256 của token phiên để lưu hoặc tra cứu trong CSDL."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(db: Session, staff_id: int) -> Tuple[str, StaffSession]:
    """Tạo phiên làm việc mới cho nhân viên.

    Trả về:
        (raw_token, session_record)
        - raw_token: gửi về client qua HttpOnly cookie, không lưu vào DB.
        - session_record: bản ghi staff_sessions lưu token_hash (sha256).
    """
    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(hours=SESSION_HOURS)

    session = StaffSession(
        token_hash=token_h,
        staff_id=staff_id,
        created_at=now,
        expires_at=expires_at,
        last_seen_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw_token, session


def get_session_user(db: Session, raw_token: Optional[str]) -> Optional[StaffAccount]:
    """Xác thực token phiên, kiểm tra hết hạn, is_active, cập nhật last_seen và dọn phiên cũ.

    Trả về StaffAccount nếu hợp lệ, None nếu không hợp lệ hoặc đã bị vô hiệu hóa.
    """
    if not raw_token or not isinstance(raw_token, str):
        return None

    token_h = hash_token(raw_token)
    now = datetime.datetime.utcnow()

    # Dọn dẹp phiên hết hạn trong hệ thống
    try:
        db.query(StaffSession).filter(StaffSession.expires_at < now).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.debug("Lỗi dọn phiên hết hạn: %s", e)

    # Tìm phiên tương ứng
    session = db.query(StaffSession).filter(StaffSession.token_hash == token_h).first()
    if not session:
        return None

    # Kiểm tra thời hạn phiên
    if session.expires_at <= now:
        try:
            db.delete(session)
            db.commit()
        except Exception:
            db.rollback()
        return None

    # Lấy thông tin tài khoản nhân viên
    staff = db.query(StaffAccount).filter(StaffAccount.id == session.staff_id).first()
    if not staff or not staff.is_active:
        return None

    # Kiểm tra khóa tài khoản (nếu đang bị khóa)
    if staff.locked_until and staff.locked_until > now:
        return None

    # Cập nhật thời điểm hoạt động gần nhất
    try:
        session.last_seen_at = now
        db.commit()
    except Exception:
        db.rollback()

    return staff


def revoke_session(db: Session, raw_token: Optional[str]) -> bool:
    """Thu hồi (xóa) phiên làm việc khi người dùng đăng xuất."""
    if not raw_token:
        return False

    token_h = hash_token(raw_token)
    try:
        deleted = (
            db.query(StaffSession)
            .filter(StaffSession.token_hash == token_h)
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted > 0
    except Exception as e:
        db.rollback()
        logger.warning("Lỗi thu hồi phiên: %s", e)
        return False
