# Agent 2 — thêm cư dân PHẢI kèm khuôn mặt, lưu trong một transaction
MIN_GOOD_FRAMES = 15   # ít hơn thì từ chối, không tạo cư dân
MAX_KEEP = 20          # giữ tối đa 20 khung tốt nhất

def register_resident(db, info, frames):
    """info: full_name, age, apartment_number. frames: ảnh quay trong 3 giây.
    Lọc chất lượng -> chọn tốt nhất -> embedding -> lưu User + FaceEmbedding.
    Lỗi thì rollback toàn bộ. Trả về user hoặc ném lỗi not_enough_quality_frames."""
    raise NotImplementedError
