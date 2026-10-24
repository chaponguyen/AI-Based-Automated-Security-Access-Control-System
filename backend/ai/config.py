# Agent 1 (AI) — tham số dùng chung cho pipeline khuôn mặt.
# Chỉnh các hằng số ở đây, không rải số vào code.

# Phát hiện (SCRFD trong buffalo_sc)
DET_SIZE = (640, 640)
DET_SCORE_MIN = 0.5

# Cắt mặt căn chỉnh (ArcFace): chỉ lông mày đến cằm, không tóc và tai
CROP_SIZE = 112

# Lọc chất lượng khung hình khi quay đăng ký 3 giây
MIN_FACE_PX = 80            # cạnh ngắn của bbox, tính bằng pixel
BLUR_MIN = 60.0             # phương sai Laplacian tối thiểu
BRIGHT_RANGE = (50.0, 210.0)  # khoảng trung bình xám hợp lệ
MAX_YAW_RATIO = 0.35        # lệch mũi so với trung điểm hai mắt, theo khoảng cách hai mắt
MAX_ROLL_DEG = 20.0         # góc nghiêng đường nối hai mắt

# Chống giả mạo (MiniFASNetV2, ONNX)
ANTI_SPOOF_SCALE = 2.7      # hệ số mở rộng bbox quanh tâm, theo cấu hình gốc của model
ANTI_SPOOF_SIZE = 80        # đầu vào model là 80x80
ANTI_SPOOF_MODEL = "2.7_80x80_MiniFASNetV2.onnx"  # đặt trong backend/ai/weights/
LIVENESS_MIN = 0.60         # xác suất lớp "thật" tối thiểu để coi là người thật

# Chống giả mạo theo thời gian (chuỗi khung của CÙNG một mặt, B4 CP-06)
LIVENESS_SEQ_MIN_FRAMES = 6    # ít hơn thì quay về kiểm tra một khung
LIVENESS_SEQ_MAX_FRAMES = 15   # nhiều hơn thì chỉ lấy các khung mới nhất
LIVENESS_SEQ_MOTION_MIN = 0.30  # năng lượng chuyển động trung bình (xám 0..255); CHƯA hiệu chỉnh bằng clip thật
