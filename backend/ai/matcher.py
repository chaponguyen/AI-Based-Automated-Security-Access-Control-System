# Agent 1 (AI) — so khớp với kho embedding
import numpy as np

SIM_THRESHOLD = 0.50   # chỉnh bằng thực nghiệm (FAR/FRR), xem docs/context/DECISIONS_LOG.md


def _unit(vec):
    """Chuẩn hóa L2 ở float64; trả None nếu vector rỗng/toàn 0/không hữu hạn."""
    if vec is None:
        raise ValueError("vector khong duoc la None")
    arr = np.asarray(vec, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        raise ValueError("vector rong")
    norm = float(np.linalg.norm(arr))
    if not np.isfinite(norm) or norm < 1e-12:
        return None
    return arr / norm


def cosine(a, b):
    """Độ giống cosine trong [-1, 1]; vector toàn 0 coi như không giống (0.0)."""
    ua = _unit(a)
    ub = _unit(b)
    if ua is None or ub is None:
        return 0.0
    if ua.size != ub.size:
        raise ValueError(f"hai vector khac so chieu: {ua.size} va {ub.size}")
    return float(max(-1.0, min(1.0, float(np.dot(ua, ub)))))


def best_match(embedding, gallery):
    """gallery: {user_id: [embedding,...]}. Mỗi người lấy trung bình top-3 độ giống cosine.
    Trả về (user_id | None, similarity)."""
    raise NotImplementedError
