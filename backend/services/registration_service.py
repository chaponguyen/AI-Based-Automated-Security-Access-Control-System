import logging
import threading

from typing import List, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)

# Agent 2 — thêm cư dân PHẢI kèm khuôn mặt, lưu trong một transaction
# Hằng số cấu hình riêng theo quy định, không viết cứng trong mã xử lý
MIN_GOOD_FRAMES = 15   # ít hơn thì từ chối, không tạo cư dân
MAX_KEEP = 20          # giữ tối đa 20 khung tốt nhất

# Khóa luồng đảm bảo chỉ có tối đa một phiên đăng ký cư dân diễn ra tại một thời điểm
registration_lock = threading.Lock()


class NotEnoughQualityFramesError(Exception):
    """Ném ra khi số khung hình đạt chuẩn nhỏ hơn ngưỡng tối thiểu MIN_GOOD_FRAMES."""

    def __init__(self, good: int, required: int = MIN_GOOD_FRAMES):
        self.good = good
        self.required = required
        super().__init__(f"Chỉ thu được {good}/{required} khung hình đạt chất lượng.")


def record_registration_frames(camera: Optional[Any] = None) -> List[np.ndarray]:
    """Quay 3 giây từ camera backend, tạm dừng AI và phát tiến độ qua WebSocket.

    CP-02:
    - Bật cờ ai_control.pause_ai().
    - Gọi camera.record(3.0, on_tick).
    - Mỗi tick tính nhanh detect_faces + frame_quality cho khung đó và phát record_progress {t_ms, got, kept} qua WebSocket broadcast.
    - Luôn tắt cờ ai_control.resume_ai() trong finally kể cả khi lỗi.
    """
    if camera is None:
        from services.camera_service import get_camera
        camera = get_camera()

    from services.ai_control import pause_ai, resume_ai
    from api.ws import broadcast
    from ai.detector import detect_faces
    from ai.quality import frame_quality

    pause_ai()
    kept_count = 0
    try:
        def on_tick(t_ms: int, got: int, frame: Optional[np.ndarray] = None):
            nonlocal kept_count
            if frame is not None:
                try:
                    faces = detect_faces(frame)
                    q = frame_quality(frame, faces, allow_multiple=False)
                    if q.get("ok"):
                        kept_count += 1
                except Exception as err:
                    logger.debug("Lỗi tính nhanh chất lượng khung tại tick %d ms: %s", t_ms, err)

            broadcast("record_progress", {
                "t_ms": t_ms,
                "got": got,
                "kept": kept_count,
            })

        frames = camera.record(3.0, on_tick=on_tick)
        return frames
    finally:
        resume_ai()


def register_resident(db, info, frames):
    """info: full_name, age, apartment_number. frames: ảnh quay trong 3 giây.
    Lọc chất lượng -> chọn tốt nhất -> embedding -> lưu User + FaceEmbedding.
    Lỗi thì rollback toàn bộ. Trả về user hoặc ném lỗi not_enough_quality_frames."""
    raise NotImplementedError

