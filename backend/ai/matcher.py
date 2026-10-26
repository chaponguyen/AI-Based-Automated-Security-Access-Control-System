# Agent 1 (AI) — so khớp với kho embedding
import numpy as np

from .config import SIM_THRESHOLD  # noqa: F401  (giữ tên ai.matcher.SIM_THRESHOLD cho A2)


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
    if embedding is None:
        return None, 0.0
    if not gallery:
        return None, 0.0

    query = _unit(embedding)
    if query is None:
        return None, 0.0

    best_id = None
    best_sim = -1.0
    for user_id, vectors in gallery.items():
        if vectors is None:
            continue
        matrix = np.asarray(vectors, dtype=np.float64)
        if matrix.size == 0:
            continue
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2 or matrix.shape[1] != query.size:
            raise ValueError(
                f"gallery cua {user_id!r} phai co shape (n, {query.size}), nhan duoc {matrix.shape}")

        norms = np.linalg.norm(matrix, axis=1)
        valid = norms > 1e-12
        if not np.any(valid):
            continue
        sims = (matrix[valid] / norms[valid, None]) @ query
        k = min(3, sims.size)
        similarity = float(np.sort(sims)[-k:].mean())
        if similarity > best_sim:
            best_id, best_sim = user_id, similarity

    if best_id is None:
        return None, 0.0
    if best_sim >= SIM_THRESHOLD:
        return best_id, best_sim
    return None, best_sim
