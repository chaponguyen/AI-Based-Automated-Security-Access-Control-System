# Agent 1 (AI) — lọc khung hình khi quay đăng ký 3 giây
# Loại khung: không đúng 1 mặt, mặt quá nhỏ, mờ (Laplacian variance), quá tối/sáng, nghiêng quá mức.
# Trả về điểm chất lượng 0..1 để chọn các khung tốt nhất.
from .config import MIN_FACE_PX


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


def frame_quality(image_bgr, faces, allow_multiple=False) -> dict:
    """{"ok": bool, "score": float, "reason": str|None, "detail": str|None}

    CP-04: số mặt và kích thước. Nhận list các dict mặt từ detect_faces;
    để tương thích chỗ gọi cũ, nhận cả một dict mặt đơn lẻ.
    """
    if isinstance(faces, dict):
        faces = [faces]
    faces = [f for f in (faces or []) if f is not None]

    if not faces:
        return {"ok": False, "score": 0.0, "reason": "no_face", "detail": None}

    if len(faces) > 1 and not allow_multiple:
        return {"ok": False, "score": 0.0, "reason": "multiple_faces", "detail": None}

    boxes = [_bbox_xyxy(f) for f in faces]
    bbox = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    short_edge = _short_edge(bbox)
    if short_edge < MIN_FACE_PX:
        return {"ok": False, "score": 0.0, "reason": "low_quality", "detail": "too_small"}

    return {"ok": True, "score": round(_size_score(short_edge), 4), "reason": None, "detail": None}
