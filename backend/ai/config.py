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

# So khớp khuôn mặt (B3): cosine trên embedding đã chuẩn hóa L2.
# Hiệu chỉnh 2026-10-26 trên 10 selfie + 8 ảnh webcam của chủ dự án và 4 người lạ:
# điểm best_match (top-3) cùng người 0,5447..0,8444; người lạ -0,1154..0,1125.
# Chọn 0,40 giữa khoảng tách, lệch 0,1447 so với cùng người thấp nhất và 0,2875 so với
# người lạ cao nhất (ưu tiên an ninh hơn tiện lợi). Dữ liệu nhỏ, xem docs/reports/B3.md.
SIM_THRESHOLD = 0.40

# Chống giả mạo (MiniFASNetV2, ONNX)
ANTI_SPOOF_SCALE = 2.7      # hệ số mở rộng bbox quanh tâm, theo cấu hình gốc của model
ANTI_SPOOF_SIZE = 80        # đầu vào model là 80x80
ANTI_SPOOF_MODEL = "2.7_80x80_MiniFASNetV2.onnx"  # đặt trong backend/ai/weights/
LIVENESS_MIN = 0.60         # xác suất lớp "thật" tối thiểu để coi là người thật

# Chống giả mạo theo thời gian (chuỗi khung của CÙNG một mặt, B4 CP-06)
# Luật chốt 2026-10-25: cửa sổ 15 khung, tỷ lệ khung đạt >= 87%, độ lệch chuẩn <= 0,11.
# Hiệu chỉnh trên 1 clip thật + 1 clip giả, kiểm định trên 3 + 3 clip mới (0/146 cửa sổ giả
# lọt, 211/226 cửa sổ thật qua). Biên hẹp (0,0083) nên CHỈ đạt cho demo, chưa kiểm định rộng.
# Mỗi tham số là một hằng riêng để chỉnh ngay tại buổi demo nếu cần.
LIVENESS_SEQ_MIN_FRAMES = 6    # ít hơn thì quay về kiểm tra một khung (mới thấy mặt)
LIVENESS_SEQ_FRAMES = 15       # độ dài cửa sổ quyết định: 15 khung ~ 1,5 giây ở 10 khung/giây
LIVENESS_SEQ_FRAC_MIN = 0.87   # tỷ lệ khung có điểm >= LIVENESS_MIN phải đạt tối thiểu
LIVENESS_SEQ_STD_MAX = 0.11    # độ lệch chuẩn điểm trong cửa sổ phải <= mức này
