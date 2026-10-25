# Agent 1 (AI) — vector đặc trưng 512 chiều, chuẩn hóa L2
import numpy as np

from .detector import get_app


def _recognition_model():
    """Model recognition của buffalo_sc, đã nạp sẵn cùng get_app()."""
    model = get_app().models.get("recognition")
    if model is None:
        raise RuntimeError("buffalo_sc khong co model recognition (kiem tra lai thu muc model)")
    return model


def _check_aligned(aligned_112):
    if aligned_112 is None or not isinstance(aligned_112, np.ndarray):
        raise ValueError("aligned_112 phai la numpy array BGR 112x112x3")
    if aligned_112.shape != (112, 112, 3):
        raise ValueError(f"aligned_112 phai co shape (112, 112, 3), nhan duoc {aligned_112.shape}")
    return np.ascontiguousarray(aligned_112)


def _normalize(vec):
    """Chuẩn hóa L2, trả float32 (512,) hoặc None nếu vector toàn 0 / không hữu hạn."""
    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(v))
    if norm < 1e-12 or not np.isfinite(norm):
        return None
    return (v / norm).astype(np.float32)


def get_embedding(aligned_112):
    """Trả vector đặc trưng 512 chiều đã chuẩn hóa L2 (float32), hoặc None nếu vector toàn 0."""
    aligned = _check_aligned(aligned_112)
    feat = _recognition_model().get_feat(aligned)
    return _normalize(feat)


def get_embeddings(aligned_list):
    """Chấm nhiều khung đã căn chỉnh một lượt (đăng ký 20 khung).

    Trả ndarray (n, 512) float32 đã chuẩn hóa L2; bỏ các khung cho vector toàn 0.
    """
    items = [_check_aligned(a) for a in aligned_list]
    if not items:
        return np.zeros((0, 512), np.float32)

    feats = _recognition_model().get_feat(items)
    vectors = [v for v in (_normalize(row) for row in feats) if v is not None]
    if not vectors:
        return np.zeros((0, 512), np.float32)
    return np.stack(vectors).astype(np.float32)
