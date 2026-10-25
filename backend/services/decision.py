# Ngưỡng cosine similarity lấy từ config AI (A1 hiệu chỉnh)
try:
    from ai.config import SIM_THRESHOLD
except (ImportError, AttributeError):
    try:
        from ai.matcher import SIM_THRESHOLD
    except (ImportError, AttributeError):
        SIM_THRESHOLD = 0.50


def decide(
    similarity: float,
    liveness: bool,
    user: any,
    threshold: float = SIM_THRESHOLD,
) -> tuple[str, str]:
    """Quyết định cấp quyền hoặc từ chối ra vào dựa trên kết quả AI.

    Thứ tự kiểm tra theo docs/plan/MO_TA_CONG_VIEC.md:
    1. liveness không đạt (giả mạo) -> ("denied", "spoof_detected")
    2. Không nhận diện được cư dân (user is None) hoặc similarity < ngưỡng -> ("denied", "not_matched")
    3. Cư dân bị vô hiệu hóa (user.status != 'active') -> ("denied", "inactive_user")
    4. Đạt tất cả điều kiện -> ("granted", "ok")

    Args:
        similarity: Điểm tương đồng cosine (0.0 đến 1.0)
        liveness: True nếu là người thật, False nếu là giả mạo (màn hình, ảnh in...)
        user: Đối tượng User hoặc dict thông tin cư dân (hoặc None nếu là người lạ)
        threshold: Ngưỡng tương đồng tối thiểu (mặc định 0.50)

    Returns:
        tuple[str, str]: (decision, reason) với:
            decision in ('granted', 'denied')
            reason in ('ok', 'spoof_detected', 'not_matched', 'inactive_user')
    """
    # 1. Kiểm tra giả mạo (Liveness check)
    if not liveness:
        return "denied", "spoof_detected"

    # 2. Kiểm tra nhận diện cư dân và ngưỡng tương đồng
    if user is None or similarity is None or similarity < threshold:
        return "denied", "not_matched"

    # 3. Kiểm tra trạng thái hoạt động của cư dân
    user_status = user.get("status") if isinstance(user, dict) else getattr(user, "status", None)
    if user_status != "active":
        return "denied", "inactive_user"

    # 4. Hợp lệ hoàn toàn
    return "granted", "ok"
