# Agent 2 — ảnh -> detect -> liveness -> crop -> embedding -> so khớp -> decide -> ghi access_logs
# -> publish MQTT (giai đoạn 2) -> đẩy WebSocket cho Dashboard
def verify_image(db, image_bgr):
    raise NotImplementedError
