# Agent 1 (AI) — lọc khung hình khi quay đăng ký 3 giây
# Loại khung: không đúng 1 mặt, mặt quá nhỏ, mờ (Laplacian variance), quá tối/sáng, nghiêng quá mức.
# Trả về điểm chất lượng 0..1 để chọn các khung tốt nhất.
import cv2

from .aligner import tight_box
from .config import BLUR_MIN, BRIGHT_RANGE, CROP_SIZE, MIN_FACE_PX


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


def frame_quality(image_bgr, faces, allow_multiple=False) -> dict:
    """{"ok": bool, "score": float, "reason": str|None, "detail": str|None}

    CP-04: số mặt và kích thước. CP-05: độ mờ (Laplacian) và độ sáng trên vùng tight_box.
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

    return {"ok": True, "score": round(_size_score(short_edge), 4), "reason": None, "detail": None}
