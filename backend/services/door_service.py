"""Dịch vụ điều khiển cửa mô phỏng (B16 CP-05).

Quản lý trạng thái cửa trong bộ nhớ, an toàn luồng:
- Trạng thái: "closed" hoặc "open".
- Khi mở cửa: chuyển sang "open", hẹn giờ DOOR_OPEN_SECONDS (mặc định 10 giây).
- Phát sự kiện WebSocket door_state {state, until, open_seconds, remaining_seconds, by, reason}.
- Khi đang mở mà có yêu cầu mở tiếp: trả already_open=True và KHÔNG kéo dài thời gian mở.
- Khi hết giờ: tự động chuyển về "closed" và phát sự kiện door_state "closed".
- Tắt backend: hủy timer sạch sẽ, không rò rỉ luồng nền.

LƯU Ý QUAN TRỌNG:
Đây là MÔ PHỎNG TRẠNG THÁI CỬA trong bộ nhớ phần mềm backend, chưa nối với khóa điện thật
(khóa thật sẽ được kết nối qua STM32/ESP32 ở giai đoạn 2).
"""

from datetime import datetime, timedelta, timezone
import logging
import os
import re
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _get_open_seconds() -> int:
    """Đọc thời gian mở cửa (giây) từ biến môi trường DOOR_OPEN_SECONDS, mặc định 10."""
    try:
        val = int(os.getenv("DOOR_OPEN_SECONDS", "10"))
        return val if val > 0 else 10
    except Exception:
        return 10


def _clean_reason(reason: Optional[str]) -> Optional[str]:
    """Cắt ngắn lý do ở 200 ký tự và loại bỏ toàn bộ ký tự điều khiển ASCII/Unicode."""
    if not reason:
        return None
    # Loại bỏ ký tự điều khiển \x00-\x1f và \x7f-\x9f
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", str(reason)).strip()
    if not cleaned:
        return None
    return cleaned[:200]


class DoorService:
    """Quản lý trạng thái cửa an toàn luồng trong bộ nhớ."""

    def __init__(self):
        self._lock = threading.RLock()
        self._state: str = "closed"  # "closed" | "open"
        self._until: Optional[datetime] = None
        self._by: Optional[str] = None
        self._reason: Optional[str] = None
        self._timer: Optional[threading.Timer] = None
        self._open_seconds: int = _get_open_seconds()
        logger.info("DoorService khởi tạo: state=closed, open_seconds=%d", self._open_seconds)

    @property
    def open_seconds(self) -> int:
        return self._open_seconds

    def open(self, by: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Mở cửa mô phỏng trong open_seconds giây.

        - Nếu cửa đang đóng: mở cửa, hẹn giờ tự đóng sau open_seconds giây, phát sự kiện door_state 'open'.
        - Nếu cửa đang mở: trả already_open=True và KHÔNG kéo dài thời gian mở.
        """
        reason_clean = _clean_reason(reason)
        now = datetime.utcnow()

        with self._lock:
            # 1. Trường hợp cửa đã đang mở: KHÔNG kéo dài thời gian hẹn giờ
            if self._state == "open" and self._until is not None:
                logger.info(
                    "Cửa đã đang mở bởi %s (until=%s). Bỏ qua yêu cầu mở thêm từ %s (lý do: %s)",
                    self._by,
                    self._until.isoformat(),
                    by,
                    reason_clean,
                )
                return {
                    "state": "open",
                    "open_seconds": self._open_seconds,
                    "until": self._until.isoformat(),
                    "already_open": True,
                }

            # 2. Trường hợp cửa đang đóng: chuyển trạng thái sang mở
            self._state = "open"
            self._by = str(by) if by else "unknown"
            self._reason = reason_clean
            self._until = now + timedelta(seconds=self._open_seconds)

            # Hủy timer cũ nếu có để tránh chạy lặp
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            # Bật timer đếm ngược tự đóng cửa
            self._timer = threading.Timer(self._open_seconds, self._auto_close)
            self._timer.daemon = True
            self._timer.start()

            event_payload = self.get_door_state_event_payload()
            until_iso = self._until.isoformat()

        # Phát sự kiện door_state ra ngoài lock để tránh deadlock
        self._broadcast_state(event_payload)
        logger.info(
            "Cửa đã MỞ bởi %s trong %d giây (until=%s, reason=%s)",
            by,
            self._open_seconds,
            until_iso,
            reason_clean,
        )

        return {
            "state": "open",
            "open_seconds": self._open_seconds,
            "until": until_iso,
            "already_open": False,
        }

    def _auto_close(self) -> None:
        """Hàm callback được gọi khi hết giờ mở cửa: tự động đóng cửa."""
        with self._lock:
            if self._state != "open":
                return
            self._state = "closed"
            self._until = None
            self._by = None
            self._reason = None
            self._timer = None
            event_payload = self.get_door_state_event_payload()

        self._broadcast_state(event_payload)
        logger.info("Cửa đã TỰ ĐỘNG ĐÓNG sau khi hết thời gian mở.")

    def _broadcast_state(self, payload: Dict[str, Any]) -> None:
        """Phát sự kiện door_state an toàn luồng qua WebSocket broadcast."""
        try:
            from api.ws import broadcast
            broadcast("door_state", payload)
        except Exception as e:
            logger.debug("Không thể broadcast sự kiện door_state: %s", e)

    def _remaining_seconds(self) -> Optional[float]:
        """Số giây còn lại (chưa khóa; chỉ gọi trong lock)."""
        if self._state != "open" or self._until is None:
            return None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # _until được lưu naive UTC (datetime.utcnow())
        diff = (self._until - now).total_seconds()
        return round(max(0.0, diff), 1)

    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái cửa hiện tại (GET /api/door/status)."""
        with self._lock:
            return {
                "state": self._state,
                "until": self._until.isoformat() if self._until else None,
                "remaining_seconds": self._remaining_seconds(),
                "by": self._by,
            }

    def get_door_state_event_payload(self) -> Dict[str, Any]:
        """Tạo payload cho sự kiện WebSocket door_state đúng hợp đồng API_CONTRACT."""
        with self._lock:
            return {
                "state": self._state,
                "until": self._until.isoformat() if self._until else None,
                "open_seconds": self._open_seconds,
                "remaining_seconds": self._remaining_seconds(),
                "by": self._by,
                "reason": self._reason,
            }

    def shutdown(self) -> None:
        """Dừng sạch sẽ dịch vụ cửa khi backend tắt, hủy timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._state = "closed"
            self._until = None
            self._by = None
            self._reason = None
        logger.info("DoorService đã shutdown và hủy timer sạch sẽ.")


# Biến singleton nội bộ
_door_service_instance: Optional[DoorService] = None
_instance_lock = threading.Lock()


def get_door_service() -> DoorService:
    """Lấy singleton instance của DoorService."""
    global _door_service_instance
    if _door_service_instance is None:
        with _instance_lock:
            if _door_service_instance is None:
                _door_service_instance = DoorService()
    return _door_service_instance
