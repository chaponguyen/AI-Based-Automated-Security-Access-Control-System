# Agent 1 (AI) — cắt khuôn mặt, KHÔNG lấy tóc và tai
# Dùng insightface.utils.face_align.norm_crop(image, kps) -> ảnh 112x112 căn theo 5 landmark.
# Vùng cắt chuẩn này chỉ gồm lông mày đến cằm, đồng thời là đầu vào của model nhận diện.
import numpy as np

from .config import CROP_SIZE

# Hệ số khung hiển thị (tight box) theo khoảng cách hai mắt d.
# Chỉnh 4 số này nếu khung còn lấn tóc/tai hoặc cắt mất cằm.
BOX_LEFT = 0.95    # x1 = cx - BOX_LEFT * d
BOX_RIGHT = 0.95   # x2 = cx + BOX_RIGHT * d
BOX_UP = 0.55      # y1 = eye_y - BOX_UP * d
BOX_DOWN = 0.55    # y2 = mouth_y + BOX_DOWN * d


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


def tight_box(kps, image_shape=None):
    """Khung hiển thị trên UI, tính từ landmark (lông mày đến cằm), không phải bbox thô của SCRFD.

    Trả (x1, y1, x2, y2) theo pixel, làm tròn về int. Nếu truyền `image_shape`
    (dạng (h, w) hoặc (h, w, 3), hoặc chính mảng ảnh) thì khung được kẹp trong biên ảnh.
    """
    landmarks = _landmarks_5x2(kps)

    left_eye, right_eye = landmarks[0], landmarks[1]
    d = float(np.linalg.norm(left_eye - right_eye))
    cx = float((left_eye[0] + right_eye[0]) / 2.0)
    eye_y = float((left_eye[1] + right_eye[1]) / 2.0)
    mouth_y = float((landmarks[3][1] + landmarks[4][1]) / 2.0)

    x1 = int(round(cx - BOX_LEFT * d))
    x2 = int(round(cx + BOX_RIGHT * d))
    y1 = int(round(eye_y - BOX_UP * d))
    y2 = int(round(mouth_y + BOX_DOWN * d))

    if image_shape is not None:
        shape = getattr(image_shape, "shape", image_shape)
        if len(shape) < 2:
            raise ValueError(f"image_shape phai co it nhat 2 chieu, nhan duoc {shape}")
        h, w = int(shape[0]), int(shape[1])
        x1 = min(max(x1, 0), w - 1)
        x2 = min(max(x2, 0), w - 1)
        y1 = min(max(y1, 0), h - 1)
        y2 = min(max(y2, 0), h - 1)
        # Ảnh quá nhỏ hoặc landmark sát biên có thể làm khung bị dẹt: giữ tối thiểu 1 pixel.
        x2 = max(x2, x1 + 1)
        y2 = max(y2, y1 + 1)

    return x1, y1, x2, y2
