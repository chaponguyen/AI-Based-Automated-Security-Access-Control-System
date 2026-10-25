import logging
import threading

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


def register_resident(db, info, frames):
    """info: full_name, age, apartment_number. frames: ảnh quay trong 3 giây.
    Lọc chất lượng -> chọn tốt nhất -> embedding -> lưu User + FaceEmbedding.
    Lỗi thì rollback toàn bộ. Trả về user hoặc ném lỗi not_enough_quality_frames."""
    raise NotImplementedError

