import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Callable, Union
from collections import deque
import threading
import numpy as np
import cv2
from dotenv import load_dotenv

# Tải biến môi trường từ .env
load_dotenv()

logger = logging.getLogger(__name__)


def _parse_int_env(key: str, default: int) -> int:
    """Đọc biến môi trường kiểu số nguyên, dùng mặc định nếu thiếu, báo lỗi nếu sai kiểu."""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as e:
        msg = f"Cấu hình '{key}={raw}' không hợp lệ: phải là số nguyên."
        logger.error(msg)
        raise ValueError(msg) from e


def _parse_str_env(key: str, default: str) -> str:
    """Đọc biến môi trường kiểu chuỗi."""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


class FrameSource(ABC):
    """Lớp trừu tượng cho nguồn cung cấp khung hình camera."""

    @abstractmethod
    def start(self) -> None:
        """Khởi động luồng nền thu thập khung hình."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Dừng luồng nền và giải phóng tài nguyên."""
        pass

    @abstractmethod
    def latest(self) -> Tuple[Optional[float], Optional[np.ndarray]]:
        """Trả về (thời điểm, khung hình BGR mới nhất)."""
        pass

    @abstractmethod
    def last_seconds(self, sec: float) -> List[Tuple[float, np.ndarray]]:
        """Trả về danh sách các khung hình trong sec giây vừa qua."""
        pass

    @abstractmethod
    def record(self, sec: float, on_tick: Optional[Callable[..., None]] = None) -> List[np.ndarray]:
        """Thu các khung hình mới trong sec giây tiếp theo."""
        pass


    @abstractmethod
    def status(self) -> dict:
        """Trả về trạng thái camera {running, fps, width, height, viewers}."""
        pass


class LocalCamera(FrameSource):
    """Nguồn camera cục bộ (webcam) chạy luồng nền và tự kết nối lại."""

    def __init__(
        self,
        index: Optional[Union[int, str]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        source: Optional[str] = None,
    ):
        self.source = source if source is not None else _parse_str_env("CAMERA_SOURCE", "local")

        # Đọc cấu hình từ tham số hoặc .env (CP-05)
        if index is not None:
            self.index = index
        else:
            if self.source == "local":
                self.index = _parse_int_env("CAMERA_INDEX", 0)
            else:
                self.index = self.source

        self.width = int(width if width is not None else _parse_int_env("CAMERA_W", 1280))
        self.height = int(height if height is not None else _parse_int_env("CAMERA_H", 720))

        self._cap: Optional[cv2.VideoCapture] = None
        self._running: bool = False
        self._actual_fps: float = 0.0
        self._viewers: int = 0

        self._latest_frame: Optional[np.ndarray] = None
        self._latest_time: Optional[float] = None
        self._lock = threading.Lock()

        # Luồng nền và tự mở lại (CP-02)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._fps_count: int = 0
        self._fps_start_time: float = time.time()

        # Bộ đệm vòng 3.5 giây lấy mẫu 10 fps (CP-03, maxlen=35 khung ~95 MB ở 720p)
        self._buffer: deque = deque(maxlen=35)
        self._last_sample_time: float = 0.0
        self._frame_cond = threading.Condition(self._lock)

    def open(self) -> bool:
        """Mở kết nối camera với DirectShow trên Windows."""
        try:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

            # Trên Windows dùng CAP_DSHOW giúp mở nhanh hơn nếu là camera cục bộ (int index)
            if isinstance(self.index, int):
                cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    # Fallback nếu DirectShow không mở được
                    cap = cv2.VideoCapture(self.index)
            else:
                # Giai đoạn 3: nguồn URL từ xa (ví dụ ESP32-CAM stream http://...)
                cap = cv2.VideoCapture(self.index)

            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                with self._lock:
                    self._cap = cap
                    if actual_w > 0 and actual_h > 0:
                        self.width = actual_w
                        self.height = actual_h
                    self._running = True
                logger.info("LocalCamera[%d] đã mở thành công (%dx%d)", self.index, self.width, self.height)
                return True
            else:
                with self._lock:
                    self._cap = None
                    self._running = False
                logger.warning("Không thể mở LocalCamera[%d]", self.index)
                return False
        except Exception as e:
            with self._lock:
                self._cap = None
                self._running = False
            logger.error("Lỗi khi mở LocalCamera[%d]: %s", self.index, e)
            return False

    def is_opened(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Đọc 1 khung hình trực tiếp từ camera."""
        with self._lock:
            cap = self._cap
        if cap is None or not cap.isOpened():
            return False, None
        try:
            ret, frame = cap.read()
            if ret and frame is not None:
                return True, frame
        except Exception as e:
            logger.warning("Lỗi ngoại lệ khi read() camera: %s", e)
        return False, None

    def start(self) -> None:
        """Khởi động luồng nền thu thập khung hình."""
        if self._thread is not None and self._thread.is_alive():
            logger.info("LocalCamera[%d] luồng nền đã đang chạy", self.index)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, name="CameraWorkerThread", daemon=True)
        self._thread.start()
        logger.info("LocalCamera[%d] đã khởi động luồng nền daemon", self.index)

    def stop(self) -> None:
        """Dừng luồng nền và giải phóng camera sạch sẽ."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None
        self.release()
        logger.info("LocalCamera[%d] đã dừng luồng nền và giải phóng", self.index)

    def _worker(self) -> None:
        """Vòng lặp luồng nền đọc khung hình liên tục và tự mở lại khi mất tín hiệu."""
        retry_delay = 1.0
        while not self._stop_event.is_set():
            if not self.is_opened():
                logger.info("LocalCamera[%d] chưa mở hoặc bị ngắt, thử mở lại...", self.index)
                if self.open():
                    retry_delay = 1.0
                    self._fps_count = 0
                    self._fps_start_time = time.time()
                else:
                    with self._lock:
                        self._running = False
                        self._actual_fps = 0.0
                    # Chờ 1 giây tăng dần tới tối đa 10 giây
                    self._stop_event.wait(timeout=retry_delay)
                    retry_delay = min(retry_delay * 1.5, 10.0)
                    continue

            # Đọc khung hình
            ret, frame = self.read()
            if ret and frame is not None:
                now = time.time()
                with self._lock:
                    self._latest_frame = frame
                    self._latest_time = now
                    self._running = True

                    # Lấy mẫu ~10 khung/giây vào bộ đệm vòng (khoảng 35 khung cho 3.5 giây)
                    # Ước lượng bộ nhớ ở 720p: 35 * (1280 * 720 * 3) bytes ≈ 95 MB
                    if now - self._last_sample_time >= 0.095:
                        self._buffer.append((now, frame))
                        self._last_sample_time = now

                    self._frame_cond.notify_all()

                self._fps_count += 1
                elapsed = now - self._fps_start_time
                if elapsed >= 1.0:
                    with self._lock:
                        self._actual_fps = self._fps_count / elapsed
                    self._fps_count = 0
                    self._fps_start_time = now
                retry_delay = 1.0
            else:
                logger.warning("LocalCamera[%d] đọc khung hình thất bại, giải phóng và chờ mở lại...", self.index)
                self.release()
                with self._lock:
                    self._running = False
                    self._actual_fps = 0.0
                self._stop_event.wait(timeout=retry_delay)
                retry_delay = min(retry_delay * 1.5, 10.0)

    def release(self) -> None:
        """Giải phóng camera."""
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception as e:
                    logger.warning("Lỗi giải phóng camera: %s", e)
                self._cap = None
            self._running = False
            self._actual_fps = 0.0
        logger.info("LocalCamera[%d] đã được giải phóng", self.index)

    def latest(self) -> Tuple[Optional[float], Optional[np.ndarray]]:
        """Trả về (thời điểm, khung hình mới nhất) an toàn luồng."""
        with self._lock:
            return self._latest_time, self._latest_frame

    def last_seconds(self, sec: float) -> List[Tuple[float, np.ndarray]]:
        """Trả về danh sách (thời điểm, khung hình) trong sec giây vừa qua từ bộ đệm vòng."""
        cutoff = time.time() - sec
        with self._lock:
            return [(t, f) for t, f in self._buffer if t >= cutoff]

    def record(
        self,
        sec: float,
        on_tick: Optional[Callable[..., None]] = None,
    ) -> List[np.ndarray]:
        """Thu các khung hình mới trong sec giây tiếp theo với tốc độ lấy mẫu ~10 khung/giây.

        Gọi on_tick(t_ms, got, [frame]) mỗi khung thu được.
        Trả về danh sách các khung hình đã thu (khoảng 25 - 32 khung với sec=3.0).
        """
        frames: List[np.ndarray] = []
        start_time = time.time()
        end_time = start_time + sec
        last_frame_ts: Optional[float] = None
        target_interval = 0.10  # 10 fps
        tolerance = 0.035
        max_frames = int(round(sec * 10.0)) + 2  # Với sec=3.0 tối đa 32 khung

        with self._frame_cond:
            # Ghi nhận timestamp hiện tại để chỉ nhận các khung mới sau khi gọi record
            last_frame_ts = self._latest_time

            while True:
                now = time.time()
                remaining = end_time - now
                if remaining <= 0 or len(frames) >= max_frames:
                    break

                self._frame_cond.wait(timeout=min(remaining, 0.05))
                now = time.time()
                if now >= end_time or len(frames) >= max_frames:
                    break

                # Kiểm tra có khung hình mới từ luồng nền không
                if self._latest_time is not None and self._latest_time != last_frame_ts:
                    last_frame_ts = self._latest_time
                    target_time = start_time + len(frames) * target_interval - tolerance
                    if now >= target_time and self._latest_frame is not None:
                        current_frame = self._latest_frame.copy()
                        frames.append(current_frame)
                        got = len(frames)
                        t_ms = int((now - start_time) * 1000)
                        if on_tick is not None:
                            try:
                                try:
                                    on_tick(t_ms, got, current_frame)
                                except TypeError:
                                    on_tick(t_ms, got)
                            except Exception as e:
                                logger.warning("Lỗi trong on_tick callback của record: %s", e)

        return frames

    def status(self) -> dict:
        """Thông tin trạng thái camera theo API contract."""
        with self._lock:
            return {
                "running": self._running,
                "fps": round(self._actual_fps, 1),
                "width": self.width,
                "height": self.height,
                "viewers": self._viewers,
            }

    def set_viewers(self, count: int) -> None:
        with self._lock:
            self._viewers = max(0, count)

    def change_viewers(self, delta: int) -> None:
        with self._lock:
            self._viewers = max(0, self._viewers + delta)


# Module-level singleton
_camera_instance: Optional[LocalCamera] = None
_camera_lock = threading.Lock()


def get_camera() -> LocalCamera:
    """Lấy hoặc khởi tạo instance LocalCamera duy nhất (Singleton)."""
    global _camera_instance
    with _camera_lock:
        if _camera_instance is None:
            _camera_instance = LocalCamera()
        return _camera_instance
