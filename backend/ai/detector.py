# Agent 1 (AI) — phát hiện mặt bằng SCRFD trong InsightFace buffalo_sc
# TODO: nạp FaceAnalysis(name="buffalo_sc") một lần khi khởi động, không nạp lại mỗi request.
def detect_faces(image_bgr):
    """Trả về list[dict(bbox, kps, score)]; kps là 5 landmark (mắt, mũi, 2 khóe miệng)."""
    raise NotImplementedError
