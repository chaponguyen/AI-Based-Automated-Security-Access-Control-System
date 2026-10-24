# Agent 1 (AI) — cắt khuôn mặt, KHÔNG lấy tóc và tai
# Dùng insightface.utils.face_align.norm_crop(image, kps) -> ảnh 112x112 căn theo 5 landmark.
# Vùng cắt chuẩn này chỉ gồm lông mày đến cằm, đồng thời là đầu vào của model nhận diện.
import numpy as np

from .config import CROP_SIZE


def _landmarks_5x2(kps):
    """Chuẩn hóa landmark về float32 (5, 2); sai hình dạng thì ném ValueError."""
    if kps is None:
        raise ValueError("kps phai la 5 diem landmark, nhan duoc None")
    arr = np.asarray(kps, dtype=np.float32)
    if arr.shape != (5, 2):
        raise ValueError(f"kps phai co hinh dang (5, 2), nhan duoc {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("kps chua gia tri khong hop le (NaN/Inf)")
    # Hai mat trung nhau thi khong uoc luong duoc phep bien doi (ma tran ra NaN).
    if float(np.linalg.norm(arr[0] - arr[1])) < 1e-3:
        raise ValueError("kps khong hop le: hai mat trung nhau")
    return arr


def crop_face(image_bgr, kps):
    """Trả ảnh 112x112 BGR đã căn chỉnh theo 5 landmark.

    Vùng cắt chỉ gồm lông mày đến cằm (loại tóc và tai), đúng chuẩn ArcFace
    nên dùng thẳng làm đầu vào model nhận diện.
    """
    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        raise ValueError("image_bgr phai la numpy array BGR")
    if image_bgr.size == 0 or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError(f"image_bgr phai la anh BGR 3 kenh, nhan duoc shape {getattr(image_bgr, 'shape', None)}")

    landmarks = _landmarks_5x2(kps)

    from insightface.utils import face_align

    crop = face_align.norm_crop(image_bgr, landmark=landmarks, image_size=CROP_SIZE)
    return np.ascontiguousarray(crop, dtype=np.uint8)


def tight_box(kps):
    """Khung hiển thị trên UI, tính từ landmark (lông mày đến cằm), không phải bbox thô của SCRFD."""
    raise NotImplementedError
