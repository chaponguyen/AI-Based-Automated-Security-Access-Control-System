"""Dịch vụ xử lý múi giờ trung tâm (sửa lỗi hiển thị giờ B16 post-review).

Vấn đề:
- Tất cả cột DateTime trong model là naive (không có tzinfo).
- Một số cột được PostgreSQL ghi theo giờ server (DB_LOCAL, hiện = UTC+7).
- Một số cột được Python ghi bằng datetime.utcnow() (UTC).
- Khi trả ra API không kèm offset → trình duyệt hiển thị sai 7 giờ.

Giải pháp:
- Đọc offset thực tế của PostgreSQL một lần lúc khởi động (SELECT extract(timezone from now())).
- Hàm to_api_iso(dt, convention) gắn đúng tzinfo rồi trả isoformat() có offset.
- Hàm parse_filter_dt(s, target_convention) chuyển chuỗi ISO lọc sang naive
  theo quy ước của cột được lọc, để so sánh trực tiếp với giá trị trong DB.

Quy ước từng cột (đã đo thực tế 2026-10-30, xem DB_SCHEMA.md):
  DB_LOCAL: users.created_at, face_embeddings.created_at,
            access_logs.timestamp, staff_accounts.created_at
  UTC     : staff_sessions.{created_at, expires_at, last_seen_at},
            staff_accounts.last_login_at, audit_logs.timestamp

RỦI RO: Nếu DB được di chuyển sang máy có múi giờ khác, cột DB_LOCAL đổi nghĩa.
Giảm nhẹ: offset được đọc lại mỗi lần backend khởi động thay vì hard-code.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Hai quy ước lưu trữ
Convention = Literal["DB_LOCAL", "UTC"]

# Offset thực tế của PostgreSQL (giây), đọc khi init_db_offset() được gọi.
_db_offset_seconds: int = 7 * 3600  # mặc định +7 nếu chưa đọc được
_db_tz: timezone = timezone(timedelta(hours=7))
_initialized: bool = False

# Múi giờ Việt Nam dùng để diễn giải chuỗi lọc không có offset
_VN_TZ = timezone(timedelta(hours=7))


def init_db_offset() -> None:
    """Đọc offset thực tế của DB một lần lúc khởi động backend.

    Gọi từ lifespan của FastAPI (main.py) sau khi engine được tạo.
    Nếu thất bại thì log cảnh báo và giữ mặc định +7.
    """
    global _db_offset_seconds, _db_tz, _initialized
    if _initialized:
        return
    try:
        from database.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            row = conn.execute(text("SELECT extract(timezone from now())")).fetchone()
            secs = int(row[0]) if row and row[0] is not None else None
        if secs is None:
            raise ValueError("extract(timezone from now()) tra None")
        _db_offset_seconds = secs
        _db_tz = timezone(timedelta(seconds=secs))
        _initialized = True
        logger.info(
            "time_service: DB timezone offset = %d giay = %.1f gio -> %s",
            secs,
            secs / 3600,
            _db_tz,
        )
    except Exception as e:
        logger.warning(
            "time_service: Khong doc duoc timezone DB, dung mac dinh UTC+7. Loi: %s", e
        )
        _db_offset_seconds = 7 * 3600
        _db_tz = timezone(timedelta(hours=7))
        _initialized = True


def to_api_iso(dt: Optional[datetime], convention: Convention = "UTC") -> Optional[str]:
    """Chuyển naive datetime thành ISO 8601 có offset để trả ra API.

    Args:
        dt: datetime naive hoặc aware từ DB / Python code.
        convention: "UTC" nếu cột được ghi bằng datetime.utcnow(),
                    "DB_LOCAL" nếu cột được ghi bằng server_default=func.now().

    Returns:
        Chuỗi ISO 8601 có offset (vi du "2026-10-30T11:30:00+07:00"),
        hoặc None nếu dt là None.
    """
    if dt is None:
        return None
    # Nếu đã có tzinfo (aware) thì giữ nguyên offset
    if dt.tzinfo is not None:
        return dt.isoformat()
    # Gắn đúng tzinfo theo quy ước
    if convention == "UTC":
        aware = dt.replace(tzinfo=timezone.utc)
    else:  # DB_LOCAL
        aware = dt.replace(tzinfo=_db_tz)
    return aware.isoformat()


def parse_filter_dt(
    s: str,
    target_convention: Convention,
) -> datetime:
    """Chuyển chuỗi ISO lọc (from/to) thành naive datetime ĐÚNG quy ước của cột.

    Quy tắc:
    - Chuỗi có offset (Z, +07:00, ...): parse rồi chuyển về naive theo quy ước cột.
    - Chuỗi không có offset: coi là giờ Việt Nam (UTC+7) rồi chuyển về naive theo quy ước.

    Args:
        s: Chuỗi datetime từ query param.
        target_convention: Quy ước của cột đang lọc ("UTC" hoặc "DB_LOCAL").

    Returns:
        datetime naive để so sánh trực tiếp với giá trị trong DB.

    Raises:
        ValueError: Nếu chuỗi không phân tích được.
    """
    s = s.strip().replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Dinh dang datetime khong hop le: {s!r}")

    if dt.tzinfo is None:
        # Không có offset: coi là giờ Việt Nam
        dt = dt.replace(tzinfo=_VN_TZ)

    # Chuyển sang naive theo quy ước cột
    if target_convention == "UTC":
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:  # DB_LOCAL
        return dt.astimezone(_db_tz).replace(tzinfo=None)


# Bảng quy ước từng cột
COLUMN_CONVENTION: dict = {
    # DB_LOCAL: ghi bởi PostgreSQL func.now()
    "users.created_at":              "DB_LOCAL",
    "face_embeddings.created_at":    "DB_LOCAL",
    "access_logs.timestamp":         "DB_LOCAL",
    "staff_accounts.created_at":     "DB_LOCAL",
    # UTC: ghi bởi Python datetime.utcnow()
    "staff_accounts.last_login_at":  "UTC",
    "staff_sessions.created_at":     "UTC",
    "staff_sessions.expires_at":     "UTC",
    "staff_sessions.last_seen_at":   "UTC",
    "audit_logs.timestamp":          "UTC",
}
