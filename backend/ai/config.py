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
