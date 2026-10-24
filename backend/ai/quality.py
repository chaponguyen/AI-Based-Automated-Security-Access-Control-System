# Agent 1 (AI) — lọc khung hình khi quay đăng ký 3 giây
# Loại khung: không đúng 1 mặt, mặt quá nhỏ, mờ (Laplacian variance), quá tối/sáng, nghiêng quá mức.
# Trả về điểm chất lượng 0..1 để chọn các khung tốt nhất.
def frame_quality(image_bgr, face) -> dict:
    """{"ok": bool, "score": float, "reason": str|None}"""
    raise NotImplementedError
