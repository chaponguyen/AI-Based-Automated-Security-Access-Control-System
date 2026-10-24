# TIẾN ĐỘ (mỗi Agent thêm một mục sau mỗi lần làm việc)

(Chưa có mục nào)
- 2026-10-24 19:33 [B11] CP-01 (backend/services/camera_service.py): Lop truu tuong FrameSource va LocalCamera mo bang cv2.CAP_DSHOW
- 2026-10-24 20:15 [B11] CP-02 (backend/services/camera_service.py): Luong nen daemon (_worker, start, stop) va tu mo lai khi mat ket noi (backoff 1s-10s)
- 2026-10-24 20:53 [B11] CP-03 (backend/services/camera_service.py; backend/services/ai_control.py): Bo dem vong 35 khung deque(maxlen=35), last_seconds, record(3.0) lay mau 10 fps (on_tick), module ai_control.py co paused
- 2026-10-24 20:58 [B11] CP-04 (backend/api/camera.py; backend/main.py): Tao endpoint GET /api/camera/status (CameraStatusResponse) va dang ky router vao main.py
- 2026-10-24 21:01 [B11] CP-05 (backend/.env.example; backend/services/camera_service.py): Chu thich .env.example, load_dotenv, _parse_int_env va _parse_str_env kiem tra kieu, ho tro local index va URL stream
- 2026-10-24 21:09 [B11] CP-06 (backend/main.py): Trien khai lifespan (khoi dong camera, nap an toan model AI, giai phong khi tat), CORS 5173, GET /api/health dong
- 2026-10-24 21:15 [B13] CP-01 (backend/services/stream_service.py; backend/api/stream.py; backend/main.py): Async generator generate_mjpeg_stream, endpoint GET /api/stream (MJPEG) va GET /api/stream/snapshot, dang ky main.py
- 2026-10-24 21:17 [B13] CP-02 (backend/services/stream_service.py): Dem nguoi xem camera.change_viewers(+1) khi vao stream va (-1) trong finally; chi ma hoa khi co viewers > 0
- 2026-10-24 21:53 [B13] CP-04 (backend/services/stream_service.py): Kiểm tra request.is_disconnected() và xử lý ngắt kết nối trong generate_mjpeg_stream; thêm stub draw_overlay cho CP-03
- 2026-10-24 21:56 [B13] CP-05 (backend/api/stream.py; backend/services/stream_service.py): Xác thực tính độc lập của stream và AI: chỉ mã hóa khi có viewers, endpoint GET /api/stream/snapshot không tăng viewers
- 2026-10-24 22:04 [B11] (backend/services/camera_service.py): Nghiệm thu an toàn luồng (threading.Lock): bộ đệm vòng _buffer và record() chạy song song tải cao không lỗi, không deadlock
- 2026-10-24 22:26 [B1] CP-01 (backend/database/models.py; backend/database/database.py): Bảng users: id (PK autoincrement), full_name String(150), age Integer, apartment_number String(20) có index
- 2026-10-24 22:28 [B1] CP-02 (backend/database/models.py): Bảng users: status String(10) (default/server_default active), created_at DateTime, CheckConstraint ck_users_status, property user_code
- 2026-10-24 22:30 [B1] CP-03 (backend/database/models.py): Bảng face_embeddings: id (PK autoincrement), user_id Integer (FK users.id ondelete CASCADE index), embedding ARRAY(Float) NOT NULL
