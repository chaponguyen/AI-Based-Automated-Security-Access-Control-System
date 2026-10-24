# TIẾN ĐỘ (mỗi Agent thêm một mục sau mỗi lần làm việc)

(Chưa có mục nào)
- 2026-10-24 19:33 [B11] CP-01 (backend/services/camera_service.py): Lop truu tuong FrameSource va LocalCamera mo bang cv2.CAP_DSHOW
- 2026-10-24 20:15 [B11] CP-02 (backend/services/camera_service.py): Luong nen daemon (_worker, start, stop) va tu mo lai khi mat ket noi (backoff 1s-10s)
- 2026-10-24 20:53 [B11] CP-03 (backend/services/camera_service.py; backend/services/ai_control.py): Bo dem vong 35 khung deque(maxlen=35), last_seconds, record(3.0) lay mau 10 fps (on_tick), module ai_control.py co paused
