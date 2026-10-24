# Agent 1 (AI) — cắt khuôn mặt, KHÔNG lấy tóc và tai
# Dùng insightface.utils.face_align.norm_crop(image, kps) -> ảnh 112x112 căn theo 5 landmark.
# Vùng cắt chuẩn này chỉ gồm lông mày đến cằm, đồng thời là đầu vào của model nhận diện.
def crop_face(image_bgr, kps):
    raise NotImplementedError

def tight_box(kps):
    """Khung hiển thị trên UI, tính từ landmark (lông mày đến cằm), không phải bbox thô của SCRFD."""
    raise NotImplementedError
