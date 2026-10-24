import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Callable
import threading
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class FrameSource(ABC):
    """Lớp trừu tượng cho nguồn cung cấp khung hình camera."""

    @abstractmethod
    def latest(self) -> Tuple[Optional[float], Optional[np.ndarray]]:
        """Trả về (thời điểm, khung hình BGR mới nhất)."""
        pass

    @abstractmethod
    def last_seconds(self, sec: float) -> List[Tuple[float, np.ndarray]]:
        """Trả về danh sách các khung hình trong sec giây vừa qua."""
        pass

    @abstractmethod
    def record(self, sec: float, on_tick: Optional[Callable[[int, int], None]] = None) -> List[np.ndarray]:
        """Thu các khung hình mới trong sec giây tiếp theo."""
        pass

    @abstractmethod
    def status(self) -> dict:
        """Trả về trạng thái camera {running, fps, width, height, viewers}."""
        pass


class LocalCamera(FrameSource):
    """Nguồn camera cục bộ (webcam) dùng OpenCV cv2.VideoCapture."""

    def __init__(
        self,
        index: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ):
        # Lấy từ tham số hoặc biến môi trường .env
        env_index = os.getenv("CAMERA_INDEX", "0")
        env_w = os.getenv("CAMERA_W", "1280")
        env_h = os.getenv("CAMERA_H", "720")

        self.index = int(index if index is not None else env_index)
        self.width = int(width if width is not None else env_w)
        self.height = int(height if height is not None else env_h)

        self._cap: Optional[cv2.VideoCapture] = None
        self._running: bool = False
        self._actual_fps: float = 0.0
        self._viewers: int = 0

        self._latest_frame: Optional[np.ndarray] = None
        self._latest_time: Optional[float] = None
        self._lock = threading.Lock()

    def open(self) -> bool:
        """Mở kết nối camera với DirectShow trên Windows."""
        try:
            # Trên Windows dùng CAP_DSHOW giúp mở nhanh hơn
            self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                # Fallback nếu DirectShow không mở được
                self._cap = cv2.VideoCapture(self.index)

            if self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                # Đọc kích thước thực tế
                actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if actual_w > 0 and actual_h > 0:
                    self.width = actual_w
                    self.height = actual_h
                self._running = True
                logger.info("LocalCamera[%d] đã mở thành công (%dx%d)", self.index, self.width, self.height)
                return True
            else:
                self._running = False
                logger.warning("Không thể mở LocalCamera[%d]", self.index)
                return False
        except Exception as e:
            self._running = False
            logger.error("Lỗi khi mở LocalCamera[%d]: %s", self.index, e)
            return False

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Đọc 1 khung hình trực tiếp từ camera."""
        if self._cap is None or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if ret and frame is not None:
            now = time.time()
            with self._lock:
                self._latest_frame = frame
                self._latest_time = now
            return True, frame
        return False, None

    def release(self):
        """Giải phóng camera."""
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception as e:
                    logger.warning("Lỗi giải phóng camera: %s", e)
                self._cap = None
            self._running = False
        logger.info("LocalCamera[%d] đã được giải phóng", self.index)

    def latest(self) -> Tuple[Optional[float], Optional[np.ndarray]]:
        """Trả về (thời điểm, khung hình mới nhất) an toàn luồng."""
        with self._lock:
            return self._latest_time, self._latest_frame

    def last_seconds(self, sec: float) -> List[Tuple[float, np.ndarray]]:
        """TODO (CP-03): Trả về danh sách khung hình từ bộ đệm vòng."""
        return []

    def record(self, sec: float, on_tick: Optional[Callable[[int, int], None]] = None) -> List[np.ndarray]:
        """TODO (CP-03): Thu thập các khung hình mới trong sec giây."""
        return []

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

    def set_viewers(self, count: int):
        with self._lock:
            self._viewers = max(0, count)

    def change_viewers(self, delta: int):
        with self._lock:
            self._viewers = max(0, self._viewers + delta)
