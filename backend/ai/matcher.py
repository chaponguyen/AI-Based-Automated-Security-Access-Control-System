# Agent 1 (AI) — so khớp với kho embedding
SIM_THRESHOLD = 0.50   # chỉnh bằng thực nghiệm (FAR/FRR), xem docs/context/DECISIONS_LOG.md

def best_match(embedding, gallery):
    """gallery: {user_id: [embedding,...]}. Mỗi người lấy trung bình top-3 độ giống cosine.
    Trả về (user_id | None, similarity)."""
    raise NotImplementedError
