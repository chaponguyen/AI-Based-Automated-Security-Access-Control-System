# Agent 1 (AI) — chống giả mạo khuôn mặt, MiniFASNetV2 (bản ONNX)
# LƯU Ý: model này cần vùng cắt MỞ RỘNG quanh mặt (cấu hình gốc dùng hệ số khoảng 2.7),
# khác với vùng cắt chặt dùng để nhận diện. Kiểm tra lại cấu hình khi tích hợp.
def check_liveness(image_bgr, bbox):
    """Trả về (is_real: bool, score: float)."""
    raise NotImplementedError
