# Agent 1 (AI) — lọc khung hình khi quay đăng ký 3 giây
# Loại khung: không đúng 1 mặt, mặt quá nhỏ, mờ (Laplacian variance), quá tối/sáng, nghiêng quá mức.
# Trả về điểm chất lượng 0..1 để chọn các khung tốt nhất.
import cv2
import numpy as np

from .aligner import tight_box
from .config import (BLUR_MIN, BRIGHT_RANGE, CROP_SIZE, MAX_ROLL_DEG, MAX_YAW_RATIO,
                     MIN_FACE_PX)


def _bbox_xyxy(face):
    """Lấy bbox (x1, y1, x2, y2) từ dict mặt; dữ liệu sai thì ném ValueError."""
    if not isinstance(face, dict):
        raise ValueError(f"face phai la dict, nhan duoc {type(face).__name__}")
    bbox = face.get("bbox")
    if bbox is None or len(bbox) != 4:
        raise ValueError(f"face['bbox'] phai co 4 so, nhan duoc {bbox}")
    x1, y1, x2, y2 = (float(v) for v in bbox)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"face['bbox'] khong hop le: {bbox}")
    return x1, y1, x2, y2


def _short_edge(bbox):
    x1, y1, x2, y2 = bbox
    return min(x2 - x1, y2 - y1)


def _size_score(short_edge):
    """Điểm kích thước 0..1: đạt MIN_FACE_PX được 0,5, gấp đôi ngưỡng được 1,0."""
    return max(0.0, min(1.0, short_edge / (2.0 * MIN_FACE_PX)))


def _quality_gray(image_bgr, face, bbox):
    """Vùng chấm chất lượng: tight_box quanh mặt, chuyển xám, resize 112.

    Không có ảnh hoặc vùng cắt rỗng thì trả None (bỏ qua các phép đo cần điểm ảnh).
    """
    if image_bgr is None or not hasattr(image_bgr, "shape") or image_bgr.ndim < 2:
        return None
    if image_bgr.shape[0] == 0 or image_bgr.shape[1] == 0:
        return None

    kps = face.get("kps")
    if kps is not None:
        x1, y1, x2, y2 = tight_box(kps, image_bgr.shape)
    else:
        # Chỗ gọi chỉ truyền bbox: dùng bbox, vẫn kẹp trong biên ảnh.
        h, w = image_bgr.shape[:2]
        x1 = min(max(int(round(bbox[0])), 0), w - 1)
        y1 = min(max(int(round(bbox[1])), 0), h - 1)
        x2 = min(max(int(round(bbox[2])), x1 + 1), w)
        y2 = min(max(int(round(bbox[3])), y1 + 1), h)

    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    if crop.ndim == 2:
        gray = crop
    elif crop.ndim == 3 and crop.shape[2] == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        return None
    return cv2.resize(gray, (CROP_SIZE, CROP_SIZE), interpolation=cv2.INTER_AREA)


def _sharpness(gray):
    """Phương sai Laplacian: càng lớn càng nét."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness(gray):
    return float(gray.mean())


def _angles(kps):
    """Góc thô từ 5 landmark: (yaw_ratio, roll_deg).

    yaw_ratio = (nose_x - eye_mid_x) / d (d = khoảng cách hai mắt);
    roll_deg = góc đường nối hai mắt so với phương ngang.
    Chỉ 5 điểm nên đây là ước lượng, không phải góc quay 3D thật.
    """
    arr = np.asarray(kps, dtype=np.float64)
    if arr.shape != (5, 2):
        raise ValueError(f"kps phai co hinh dang (5, 2), nhan duoc {arr.shape}")
    dx = float(arr[1][0] - arr[0][0])
    dy = float(arr[1][1] - arr[0][1])
    d = float(np.hypot(dx, dy))
    if d < 1e-6:
        raise ValueError("kps khong hop le: hai mat trung nhau")
    eye_mid_x = float((arr[0][0] + arr[1][0]) / 2.0)
    yaw_ratio = float((arr[2][0] - eye_mid_x) / d)
    roll_deg = float(np.degrees(np.arctan2(dy, dx)))
    return yaw_ratio, roll_deg


def _brightness_score(bright):
    """Điểm sáng 0..1: cao nhất ở giữa BRIGHT_RANGE, giảm dần về hai biên."""
    lo, hi = BRIGHT_RANGE
    center = (lo + hi) / 2.0
    half = (hi - lo) / 2.0
    return max(0.0, min(1.0, 1.0 - abs(bright - center) / half))


def _straight_score(yaw_ratio, roll_deg):
    """Điểm thẳng 0..1: trung bình điểm yaw và điểm roll, mỗi điểm giảm tuyến tính về ngưỡng."""
    yaw_score = max(0.0, 1.0 - abs(yaw_ratio) / MAX_YAW_RATIO)
    roll_score = max(0.0, 1.0 - abs(roll_deg) / MAX_ROLL_DEG)
    return (yaw_score + roll_score) / 2.0


def frame_quality(image_bgr, faces, allow_multiple=False) -> dict:
    """{"ok": bool, "score": float, "reason": str|None, "detail": str|None}

    CP-04: số mặt và kích thước. CP-05: độ mờ (Laplacian) và độ sáng trên vùng tight_box.
    CP-06: góc nghiêng thô từ landmark và điểm tổng hợp 0..1.
    Nhận list các dict mặt từ detect_faces; để tương thích chỗ gọi cũ, nhận cả một dict mặt đơn lẻ.
    """
    if isinstance(faces, dict):
        faces = [faces]
    faces = [f for f in (faces or []) if f is not None]

    if not faces:
        return {"ok": False, "score": 0.0, "reason": "no_face", "detail": None}

    if len(faces) > 1 and not allow_multiple:
        return {"ok": False, "score": 0.0, "reason": "multiple_faces", "detail": None}

    boxes = [_bbox_xyxy(f) for f in faces]
    largest = max(range(len(faces)), key=lambda i: (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1]))
    bbox = boxes[largest]
    short_edge = _short_edge(bbox)
    if short_edge < MIN_FACE_PX:
        return {"ok": False, "score": 0.0, "reason": "low_quality", "detail": "too_small"}

    sharp_score = 0.0
    bright_score = 0.0
    straight_score = 0.0

    gray = _quality_gray(image_bgr, faces[largest], bbox)
    if gray is not None:
        bright = _brightness(gray)
        # Kiểm tra sáng trước: ảnh quá tối cũng làm Laplacian tụt, báo too_dark hữu ích hơn blurry.
        if bright < BRIGHT_RANGE[0]:
            return {"ok": False, "score": 0.0, "reason": "too_dark",
                    "detail": f"brightness={bright:.1f}"}
        if bright > BRIGHT_RANGE[1]:
            return {"ok": False, "score": 0.0, "reason": "too_bright",
                    "detail": f"brightness={bright:.1f}"}

        blur = _sharpness(gray)
        if blur < BLUR_MIN:
            return {"ok": False, "score": 0.0, "reason": "blurry",
                    "detail": f"laplacian={blur:.1f}"}

        sharp_score = min(1.0, blur / (BLUR_MIN * 3.0))
        bright_score = _brightness_score(bright)

    kps = faces[largest].get("kps")
    if kps is not None:
        yaw_ratio, roll_deg = _angles(kps)
        if abs(yaw_ratio) > MAX_YAW_RATIO or abs(roll_deg) > MAX_ROLL_DEG:
            return {"ok": False, "score": 0.0, "reason": "off_angle",
                    "detail": f"yaw_ratio={yaw_ratio:.2f}, roll={roll_deg:.1f}"}
        straight_score = _straight_score(yaw_ratio, roll_deg)

    score = (0.4 * sharp_score
             + 0.2 * _size_score(short_edge)
             + 0.2 * bright_score
             + 0.2 * straight_score)
    return {"ok": True, "score": round(score, 4), "reason": None, "detail": None}
