# Agent 2 — Vòng lặp tự động xác thực khuôn mặt chạy nền (B12 CP-01)
import time
import logging
import threading
from typing import Optional, Dict, Any, List
import numpy as np

from database.database import SessionLocal
from services.camera_service import get_camera
from services import ai_control
from ai.detector import detect_faces

logger = logging.getLogger(__name__)

# ==================== CẤU HÌNH THAM SỐ VÒNG LẶP ====================
AI_FPS_ACTIVE = 6.0         # Tốc độ tối đa khi có mặt hoặc vừa thấy mặt (khung/giây)
AI_FPS_IDLE = 3.0           # Tốc độ khi không có mặt trong 5 giây (khung/giây)
IDLE_TIMEOUT_SEC = 5.0      # Thời gian không thấy mặt để chuyển sang chế độ tiết kiệm CPU

# Cấu hình cho CP-02 đến CP-05 (sẽ kích hoạt ở các checkpoint tiếp theo)
MIN_FACE_PX_VERIFY = 110    # Cạnh ngắn tối thiểu của bbox để kích hoạt xác thực
STABLE_FRAMES_REQUIRED = 3  # Số khung hình liên tiếp ổn định
IOU_THRESHOLD = 0.5         # Ngưỡng IoU để liên kết theo dõi khuôn mặt

RESIDENT_COOLDOWN_SEC = 60.0  # Chống báo lặp cho cư dân granted (giây)
STRANGER_COOLDOWN_SEC = 15.0  # Thời gian nghỉ sau khi cảnh báo người lạ (giây)
STRANGER_MIN_DENIED = 3       # Số lần denied trong 5 kết quả gần nhất để cảnh báo người lạ


class AutoVerifyService:
    """Quản lý luồng nền tự động xác thực khuôn mặt khi có người trước camera.

    CP-01:
    - Khởi động trong lifespan của FastAPI, dừng sạch sẽ khi tắt hệ thống.
    - Đọc camera.latest(), bỏ qua các khung đã xử lý.
    - Giới hạn tốc độ: tối đa 6 fps khi có mặt; tự hạ xuống 3 fps khi không có mặt sau 5s.
    - Mỗi chu kỳ tạo SessionLocal() riêng và giải phóng trong finally.
    - Bắt mọi ngoại lệ trong vòng lặp, ghi log cảnh báo và tiếp tục chạy.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False

        # Quản lý thời gian và tần số
        self._last_processed_time: float = 0.0
        self._last_face_seen_time: float = 0.0
        self._actual_fps: float = 0.0
        self._fps_count: int = 0
        self._fps_start_time: float = time.time()
        self._is_idle: bool = True

        # Trạng thái theo dõi khuôn mặt (CP-02..CP-05)
        self._tracked_faces: Dict[int, Any] = {}
        self._last_event_at: Optional[float] = None

    def start(self) -> None:
        """Khởi động luồng nền nếu chưa chạy."""
        with self._lock:
            if self._running and self._thread is not None and self._thread.is_alive():
                logger.info("AutoVerifyService đã đang chạy.")
                return

            self._stop_event.clear()
            self._running = True
            self._last_processed_time = 0.0
            self._last_face_seen_time = 0.0
            self._is_idle = True
            self._fps_count = 0
            self._fps_start_time = time.time()

            self._thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="AutoVerifyWorker",
            )
            self._thread.start()
            logger.info("AutoVerifyService luồng nền đã khởi động thành công.")

    def stop(self, timeout: float = 3.0) -> None:
        """Dừng luồng nền sạch sẽ."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            logger.info("AutoVerifyService luồng nền đã dừng sạch sẽ.")
        self._thread = None

    def is_running(self) -> bool:
        """Kiểm tra luồng nền có đang chạy hay không."""
        with self._lock:
            return self._running and self._thread is not None and self._thread.is_alive()

    def status(self) -> Dict[str, Any]:
        """Trả về thông tin trạng thái hoạt động của dịch vụ."""
        with self._lock:
            return {
                "running": self._running,
                "fps": round(self._actual_fps, 2),
                "is_idle": self._is_idle,
                "tracking": len(self._tracked_faces),
                "is_paused": ai_control.is_ai_paused(),
                "last_event_at": self._last_event_at,
            }

    def _worker(self) -> None:
        """Vòng lặp thực thi của luồng nền."""
        logger.info("Bắt đầu vòng lặp worker AutoVerifyService.")
        camera = get_camera()

        while not self._stop_event.is_set():
            loop_start = time.perf_counter()

            try:
                # 1. Kiểm tra cờ tạm dừng AI (khi B5 đang quay video đăng ký)
                if ai_control.is_ai_paused():
                    self._stop_event.wait(timeout=0.2)
                    continue

                # 2. Xác định tần số mục tiêu (Idle 3 fps hoặc Active 6 fps)
                now = time.time()
                time_since_face = now - self._last_face_seen_time
                if self._last_face_seen_time > 0 and time_since_face <= IDLE_TIMEOUT_SEC:
                    target_fps = AI_FPS_ACTIVE
                    self._is_idle = False
                else:
                    target_fps = AI_FPS_IDLE
                    self._is_idle = True

                target_interval = 1.0 / target_fps

                # 3. Lấy khung hình mới nhất từ camera
                t_frame, frame = camera.latest()

                # Bỏ qua nếu camera chưa có khung hoặc khung này đã được xử lý rồi
                if frame is None or t_frame is None or t_frame <= self._last_processed_time:
                    self._stop_event.wait(timeout=min(0.05, target_interval))
                    continue

                self._last_processed_time = t_frame

                # 4. Tạo Session DB riêng cho mỗi lượt và giải phóng an toàn trong finally
                db = SessionLocal()
                try:
                    # Phát hiện các khuôn mặt trong khung hình
                    faces = detect_faces(frame)

                    if faces:
                        self._last_face_seen_time = time.time()
                        self._is_idle = False
                    else:
                        # Khi không có khuôn mặt trong khung: xóa trạng thái theo dõi
                        if self._tracked_faces:
                            self._tracked_faces.clear()

                    # (Các bước CP-02..CP-05 sẽ tiếp tục phát triển ở đây)
                finally:
                    db.close()

                # 5. Cập nhật thống kê FPS thực tế
                self._fps_count += 1
                fps_elapsed = now - self._fps_start_time
                if fps_elapsed >= 1.0:
                    with self._lock:
                        self._actual_fps = self._fps_count / fps_elapsed
                    self._fps_count = 0
                    self._fps_start_time = now

            except Exception as e:
                # Đảm bảo vòng lặp không bao giờ chết âm thầm vì ngoại lệ
                logger.error("Lỗi trong vòng lặp auto_verify: %s", e, exc_info=True)

            # 6. Điều tiết thời gian ngủ để duy trì đúng tần số target_fps
            loop_duration = time.perf_counter() - loop_start
            sleep_needed = target_interval - loop_duration
            if sleep_needed > 0.001:
                self._stop_event.wait(timeout=sleep_needed)

        logger.info("Vòng lặp worker AutoVerifyService đã kết thúc.")


# Singleton toàn cục
_auto_verify_service = AutoVerifyService()


def get_auto_verify_service() -> AutoVerifyService:
    return _auto_verify_service


def start() -> None:
    _auto_verify_service.start()


def stop() -> None:
    _auto_verify_service.stop()


def status() -> Dict[str, Any]:
    return _auto_verify_service.status()


def is_running() -> bool:
    return _auto_verify_service.is_running()
