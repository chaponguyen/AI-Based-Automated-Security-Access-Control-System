# Mô tả chi tiết công việc (đặc tả từng checkpoint)

Mỗi checkpoint ghi: **Làm** (việc cụ thể) · **Vào/ra** · **Biên** (trường hợp đặc biệt phải xử lý) · **Kiểm tra** (lệnh hoặc cách thử và kết quả mong đợi). Số checkpoint khớp với `docs/reports/<ID>.md`. Ngưỡng và số liệu ghi ở đây là **giá trị khởi đầu**, được chỉnh bằng thực nghiệm ở B10.

## 0. Quy ước chung cho mọi Agent

| Mục | Quy ước |
|---|---|
| Ảnh | `numpy.ndarray` uint8, BGR, HxWx3 (chuẩn OpenCV) |
| Bbox | `[x1, y1, x2, y2]` (số nguyên, pixel) |
| Landmark | `kps` mảng (5, 2): mắt trái, mắt phải, mũi, khóe miệng trái, khóe miệng phải (trái/phải theo góc nhìn của camera) |
| Embedding | `float32`, độ dài 512, **đã chuẩn hóa L2** |
| Ngưỡng | Đặt hết trong `backend/ai/config.py` (A1 tạo): `SIM_THRESHOLD=0.50`, `MIN_FACE_PX=80`, `BLUR_MIN=60`, `BRIGHT_RANGE=(50,210)`, `LIVENESS_MIN=0.60`, `MODEL_VERSION="buffalo_sc"`. Không ghi số cứng ở nơi khác |
| Mã `reason` | `ok`, `not_matched`, `spoof_detected`, `inactive_user`, `no_face`, `multiple_faces`, `low_quality` (chi tiết thêm ở trường `detail`) |
| Giờ | Giờ máy chủ (`datetime.now()`), loa và nhật ký dùng cùng một giá trị |
| Loa | Chỉ đọc chuỗi `spoken` bằng **giọng tiếng Việt thật**, đọc mạch lạc (không đánh vần); số đã đổi sang chữ. Không có giọng tiếng Việt thì không đọc. Chuỗi hiển thị là `display`. Xem B14 |
| Stream | Stream camera chỉ là người xem; AI và loa chạy bất kể có bật stream hay mở web hay không |
| Ghi log | Dùng module `logging`, không `print`. Không bao giờ ghi embedding hoặc ảnh vào log |
| Lỗi | Không nuốt lỗi âm thầm; hàm AI trả `None`/mã reason, tầng API đổi thành HTTP status. Vòng lặp nền không được chết vì một ngoại lệ |
| Đặt tên | Tên hàm, biến bằng tiếng Anh; chú thích ngắn bằng tiếng Việt |

---

## B1 — Cơ sở dữ liệu: 3 bảng + Alembic (A2)
Vào: `docs/context/DB_SCHEMA.md`. Ra: `backend/database/models.py` + migration. **Không chạy `alembic upgrade`.**

#### CP-01 Bảng `users`: id, full_name, age, apartment_number
- Làm: `class User(Base)`, `__tablename__ = "users"`. `id` Integer khóa chính tự tăng; `full_name` String(150) NOT NULL; `age` Integer NOT NULL; `apartment_number` String(20) NOT NULL, `index=True` (không unique vì một căn hộ nhiều người).
- Kiểm tra: `python -c "from database.models import User; print(list(User.__table__.columns.keys()))"` ra `['id','full_name','age','apartment_number']`.

#### CP-02 `users`: status, created_at, user_code
- Làm: `status` String(10) NOT NULL, `default="active"` và `server_default="active"`; `CheckConstraint("status in ('active','inactive')", name="ck_users_status")`; `created_at` DateTime `server_default=func.now()`. Thuộc tính Python `user_code` (property, không phải cột): `f"USR{id:06d}"`.
- Biên: `id` chưa có (đối tượng chưa lưu) thì `user_code` trả `None`.
- Kiểm tra: `User(id=7).user_code == "USR000007"`; `User().user_code is None`.

#### CP-03 Bảng `face_embeddings`: id, user_id, embedding
- Làm: `id` PK; `user_id` Integer FK `users.id`, `ondelete="CASCADE"`, NOT NULL, `index=True`; `embedding` `ARRAY(Float)` (từ `sqlalchemy` hoặc `sqlalchemy.dialects.postgresql`) NOT NULL.
- Kiểm tra: in tên cột; `FaceEmbedding.__table__.c.user_id.foreign_keys` có 1 phần tử.

#### CP-04 `face_embeddings`: quality, model_version, created_at, relationship
- Làm: `quality` Float nullable; `model_version` String(30) NOT NULL; `created_at` như trên. Thêm `User.embeddings = relationship("FaceEmbedding", cascade="all, delete-orphan", passive_deletes=True)`.
- Kiểm tra: `import database.models` không lỗi; in toàn bộ cột khớp `DB_SCHEMA.md`.

#### CP-05 Bảng `access_logs`
- Làm: `id`; `user_id` FK `users.id`, **nullable**, `ondelete="SET NULL"` (xóa cư dân vẫn giữ nhật ký); `similarity` Float; `liveness` Boolean; `decision` String(10) NOT NULL + `CheckConstraint("decision in ('granted','denied')")`; `reason` String(80); `timestamp` DateTime `server_default=func.now()`, `index=True`. Ghi dòng `ON DELETE SET NULL` vào `DB_SCHEMA.md`.
- Kiểm tra: in cột; `AccessLog.__table__.c.user_id.nullable is True`.

#### CP-06 Khởi tạo Alembic
- Làm: trong `backend/`: `alembic init migrations`. Sửa `alembic.ini` để `sqlalchemy.url` trống. Sửa `migrations/env.py`: thêm thư mục `backend` vào `sys.path`, `load_dotenv()`, `config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])`, `from database.models import *`, `target_metadata = Base.metadata`.
- Biên: thiếu `DATABASE_URL` thì báo lỗi rõ ràng, không dùng giá trị mặc định (tránh lặp lỗi rơi về SQLite như trước).
- Kiểm tra: `alembic heads` chạy không lỗi (chưa có migration thì không in gì).

#### CP-07 Sinh migration đầu tiên
- Làm: `alembic revision --autogenerate -m "tao 3 bang"`. Mở file sinh ra, đối chiếu từng cột với `DB_SCHEMA.md`.
- Biên: migration phải có đúng 3 `op.create_table`, có index `ix_users_apartment_number`, `ix_face_embeddings_user_id`, `ix_access_logs_timestamp`, 2 check constraint, `postgresql.ARRAY(sa.Float())`.
- Kiểm tra: đọc file; **dừng lại**, báo cho chủ dự án tự chạy `alembic upgrade head`.

---

## B2 — Phát hiện, cắt mặt, lọc chất lượng (A1)
Vào: model `buffalo_sc` đã tải (P0-3), ảnh test (P0-4). Ra: `backend/ai/detector.py`, `aligner.py`, `quality.py`, `config.py`.

#### CP-01 `detect_faces(image_bgr)`
- Làm: nạp `FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])` **một lần** (biến module, hàm `get_app()`), `prepare(ctx_id=-1, det_size=(640, 640))`. Chỉ phát hiện, không tính embedding: dùng `app.det_model.detect(img, max_num=0, metric="default")` (trả bboxes N×5 và kpss N×5×2; kiểm tra tên thuộc tính theo phiên bản insightface đang cài). Trả `list[dict(bbox, score, kps)]` sắp theo diện tích giảm dần.
- Biên: ảnh `None`/rỗng/không đúng 3 kênh trả `[]`; bỏ mặt có `score < 0.5`.
- Kiểm tra: ảnh có 1 mặt trả 1 phần tử; ảnh trống trả `[]`; gọi lần 2 không nạp lại model (đo thời gian).

#### CP-02 `crop_face(image_bgr, kps)`
- Làm: `from insightface.utils import face_align`; `face_align.norm_crop(image_bgr, landmark=np.array(kps, dtype=np.float32), image_size=112)` trả ảnh 112×112 BGR đã căn chỉnh. Đây là vùng đưa vào nhận diện: chỉ gồm lông mày đến cằm.
- Biên: `kps` sai hình dạng thì ném `ValueError`.
- Kiểm tra: ảnh trả về shape `(112,112,3)`; lưu ra file, nhìn bằng mắt.

#### CP-03 `tight_box(kps)`
- Làm: khung hiển thị trên UI/stream, tính từ landmark. `d` = khoảng cách hai mắt; `cx` = trung bình x hai mắt; `eye_y`, `mouth_y` = trung bình y. `x1=cx-0.95d`, `x2=cx+0.95d`, `y1=eye_y-0.55d`, `y2=mouth_y+0.55d`. Đặt 4 hệ số này thành hằng số đầu file để chỉnh.
- Biên: kẹp vào trong ảnh nếu có kích thước ảnh truyền vào.
- Kiểm tra: vẽ khung lên 10 ảnh test; khung ôm từ lông mày đến cằm, không có tóc và tai. Chưa đạt thì chỉnh hệ số.

#### CP-04 `frame_quality`: số mặt và kích thước
- Làm: `frame_quality(image_bgr, faces, allow_multiple=False)` trả `{"ok","score","reason","detail"}`. 0 mặt → `no_face`. Nhiều mặt và `allow_multiple=False` → `multiple_faces`. Cạnh ngắn của bbox `< MIN_FACE_PX` → `low_quality`, `detail="too_small"`.
- Kiểm tra: ảnh 2 người, ảnh không mặt, ảnh mặt nhỏ: mỗi ảnh ra đúng reason.

#### CP-05 `frame_quality`: độ mờ và độ sáng
- Làm: lấy vùng `tight_box`, chuyển xám, resize về 112; độ mờ = `cv2.Laplacian(gray, cv2.CV_64F).var()`, `< BLUR_MIN` → `blurry`. Độ sáng = trung bình xám, ngoài `BRIGHT_RANGE` → `too_dark`/`too_bright`.
- Kiểm tra: làm mờ một ảnh bằng `cv2.GaussianBlur` thì bị loại; giảm sáng ảnh thì bị loại.

#### CP-06 `frame_quality`: góc nghiêng thô và điểm tổng hợp
- Làm: `yaw_ratio = (nose_x - eye_mid_x) / d`, `|yaw_ratio| > 0.35` → `off_angle`; roll = góc đường nối hai mắt, `> 20°` → `off_angle`. `score` 0..1 = 0,4·độ nét (chuẩn hóa theo `BLUR_MIN`·3, kẹp 1) + 0,2·kích thước + 0,2·độ sáng + 0,2·độ thẳng. Chỉ có 5 landmark nên đây chỉ là ước lượng thô.
- Kiểm tra: in `score` của 10 ảnh; ảnh nhìn thẳng, rõ cho điểm cao hơn ảnh nghiêng, mờ.

#### CP-07 Script thử pipeline
- Làm: `scripts/try_face_pipeline.py`: đọc `test_data/`, với mỗi ảnh in bảng (số mặt, score, reason), lưu ảnh cắt vào `out/crops/` và ảnh có khung + landmark vào `out/overlay/`. `out/` không commit.
- Kiểm tra: chủ dự án xem `out/crops/`: **không thấy tóc và tai**; xem `out/overlay/`: khung ôm đúng mặt.

---

## B3 — Embedding và so khớp (A1)

#### CP-01 `get_embedding(aligned_112)`
- Làm: `app.models["recognition"].get_feat(img)` (kiểm tra tên theo phiên bản), làm phẳng thành `(512,)`, chuẩn hóa L2, ép `float32`. Thêm `get_embeddings(list)` cho đăng ký (20 khung).
- Biên: đầu vào không phải 112×112×3 thì ném `ValueError`; vector toàn 0 thì trả `None`.
- Kiểm tra: `np.linalg.norm(e)` bằng 1 (sai số 1e-5); cùng một ảnh gọi hai lần cho vector giống nhau.

#### CP-02 Hàm cosine
- Làm: `cosine(a, b)` = tích vô hướng sau khi bảo đảm chuẩn hóa, trả float.
- Kiểm tra: `cosine(e, e) == 1.0`; hai vector trực giao trả 0.

#### CP-03 `best_match(embedding, gallery)`
- Làm: `gallery` là `{user_id: ndarray (n,512)}`. Với mỗi người: `sims = G @ e`, lấy trung bình `k=3` giá trị lớn nhất (nếu có ít hơn 3 thì lấy hết). Trả `(user_id, similarity)` của người cao nhất nếu `>= SIM_THRESHOLD`, ngược lại `(None, similarity_cao_nhất)` (vẫn trả điểm để ghi log). Gallery rỗng trả `(None, 0.0)`.
- Biên: vector `e` là `None` trả `(None, 0.0)`.
- Kiểm tra: gallery giả 3 người: vector gần người nào thì ra người đó; vector ngẫu nhiên ra `None`.

#### CP-04 Script đo cùng người và khác người
- Làm: `scripts/measure_pairs.py`: với `test_data/people/<tên>/`, tính độ giống mọi cặp cùng người và khác người, ghi `docs/reports/B3_pairs.csv`, in tóm tắt (trung bình, nhỏ nhất, lớn nhất mỗi nhóm) và gợi ý ngưỡng ở giữa `min(cùng người)` và `max(khác người)` nếu tách được.
- Kiểm tra: có file CSV và bảng tóm tắt dán vào `docs/reports/B3.md`.

---

## B4 — Chống giả mạo khuôn mặt (A1)
Vào: file MiniFASNetV2 `.onnx` trong `backend/ai/weights/`. Ra: `backend/ai/anti_spoof.py`.

#### CP-01 Nạp model
- Làm: `onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])` một lần. Nguồn model: repo minivision-ai/Silent-Face-Anti-Spoofing, file `resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth` (tên file cho biết hệ số cắt 2.7 và đầu vào 80×80). Repo gốc chỉ có `.pth`, nên viết `scripts/export_antispoof_onnx.py`: lấy mã lớp mạng MiniFASNetV2 từ repo gốc (thư mục `src/model_lib`, **xác minh đường dẫn**), nạp trọng số `.pth`, `torch.onnx.export` với đầu vào 1×3×80×80, rồi so kết quả ONNX với PyTorch trên 5 ảnh (sai lệch nhỏ). Script cần `torch` nên chỉ chạy một lần, **không thêm torch vào `requirements.txt`**; ghi lại cách làm vào báo cáo B4.
- Biên: thiếu file thì ném lỗi rõ ràng, **dừng và báo chủ dự án tải**, không tự tạo model.
- Kiểm tra: in tên và shape đầu vào, đầu ra của model.

#### CP-02 Vùng cắt mở rộng
- Làm: từ bbox, mở rộng theo hệ số `SCALE = 2.7` (cấu hình của repo gốc cho MiniFASNetV2, **đối chiếu lại với repo gốc**) quanh tâm bbox, dời khung vào trong ảnh nếu tràn, rồi resize 80×80. Đây là vùng **khác** vùng cắt nhận diện.
- Kiểm tra: lưu vùng cắt của 5 ảnh, thấy cả vai và nền quanh mặt.

#### CP-03 Tiền xử lý và suy luận
- Làm: BGR→tensor 1×3×80×80 float32. Cách chuẩn hóa phải giống lúc huấn luyện (repo gốc không chia 255, **xác minh**). Chạy `session.run`, softmax đầu ra 3 lớp, lấy xác suất lớp "thật" (lớp 1 theo repo gốc, **xác minh**).
- Kiểm tra: 1 ảnh thật trả điểm cao hơn 1 ảnh chụp lại từ màn hình điện thoại.

#### CP-04 `check_liveness(image_bgr, bbox)`
- Làm: trả `(is_real, score)`, `is_real = score >= LIVENESS_MIN`. Với nhiều mặt, gọi riêng cho từng bbox.
- Biên: bbox không hợp lệ trả `(False, 0.0)` và ghi log cảnh báo.
- Kiểm tra: chạy trên cả thư mục ảnh thật và ảnh giả, in bảng.

#### CP-05 Đo trên ảnh thật và ảnh giả
- Làm: script đo tỷ lệ ảnh giả bị chặn (1 − APCER) và ảnh thật bị chặn nhầm (BPCER) ở các ngưỡng 0,4 đến 0,8, kèm thời gian trung bình mỗi lần.
- Kiểm tra: bảng trong `docs/reports/B4.md`; nêu rõ ảnh giả nào lọt qua.

---

## B11 — Camera chạy nền trong backend (A2)
Trên Windows một camera chỉ một chương trình mở được, nên **trình duyệt không mở camera**; mọi thứ đi qua backend.

#### CP-01 `FrameSource` và `LocalCamera`
- Làm: lớp trừu tượng `FrameSource` (`latest()`, `last_seconds(sec)`, `record(sec, on_tick)`, `status()`). `LocalCamera(index)` dùng `cv2.VideoCapture(index, cv2.CAP_DSHOW)` (nhanh hơn trên Windows), đặt độ phân giải từ `.env` (`CAMERA_W`, `CAMERA_H`, mặc định 1280×720).
- Kiểm tra: đọc 100 khung, in fps thực tế.

#### CP-02 Luồng nền và tự mở lại
- Làm: luồng `daemon` khởi động trong `lifespan` của FastAPI, dừng sạch khi tắt. `read()` thất bại thì giải phóng, chờ 1 giây tăng dần tới 10 giây, mở lại; trong lúc mất camera `status.running=False`.
- Biên: không có camera lúc khởi động thì backend vẫn lên, báo `running=False`. Chạy `uvicorn` **một worker** và **không dùng `--reload`** khi dùng camera (tiến trình cũ có thể còn giữ camera, tiến trình mới mở không được). Khi tắt backend (`lifespan` shutdown) phải gọi `release()`.
- Kiểm tra: rút và cắm lại camera, `status` đổi `False` rồi `True`, không cần khởi động lại backend.

#### CP-03 Bộ đệm vòng và `record`
- Làm: giữ `latest` (khung mới nhất kèm thời điểm) và bộ đệm lấy mẫu 10 khung/giây trong 3,5 giây (khoảng 35 khung; ước lượng bộ nhớ ở 720p ≈ 95 MB, ghi vào báo cáo). `record(3.0, on_tick)` thu **khung mới** trong 3 giây tiếp theo, gọi `on_tick(t_ms, got)` mỗi khung, trả list khung (khoảng 30).
- Cờ tạm dừng AI: tạo ở đây `backend/services/ai_control.py` với `paused = threading.Event()`, để B5 dùng được trước khi B12 xong; B12 đọc cờ này mỗi vòng, đang `paused` thì không xử lý.
- Kiểm tra: `record(3.0)` trả 25 đến 32 khung; bộ nhớ không tăng sau 10 lần gọi.

#### CP-04 `GET /api/camera/status`
- Làm: trả `{running, fps, width, height, viewers}` (`viewers` do B13 cập nhật).
- Kiểm tra: `/docs` gọi thử; khớp `API_CONTRACT.md`.

#### CP-05 Cấu hình camera trong `.env`
- Làm: thêm vào `backend/.env.example`: `CAMERA_SOURCE=local` (hoặc `http://<ip>:81/stream` ở giai đoạn 3), `CAMERA_INDEX=0`, `CAMERA_W=1280`, `CAMERA_H=720`, `AI_FPS=6`, `AI_FPS_IDLE=3`, `STREAM_MAX_FPS=12`, `STREAM_WIDTH=960`, `STREAM_JPEG_QUALITY=70`. Đọc bằng `os.getenv` có giá trị mặc định ghi sẵn trong code; thiếu hoặc sai kiểu thì báo lỗi rõ ràng khi khởi động.
- Kiểm tra: đổi `CAMERA_INDEX` sang số không có camera thì backend vẫn lên, `status.running=False`.

#### CP-06 `main.py`: lifespan, CORS, health
- Làm: dùng `lifespan` của FastAPI: khi khởi động theo thứ tự (1) tạo `LocalCamera` và chạy luồng nền, (2) nạp sẵn model (`get_app()` của detector, embedder, anti_spoof) để lượt xác thực đầu tiên không bị chậm, (3) nạp `GalleryCache` (B6), (4) khởi động vòng lặp B12 nếu đã có; khi tắt thì dừng ngược lại và `release()` camera. CORS cho `http://localhost:5173` và `http://127.0.0.1:5173`. `GET /api/health` trả `{status, camera: running, ai: running}`.
- Biên: bước nào lỗi thì ghi log và các bước còn lại vẫn chạy (không có camera hoặc chưa có model thì backend vẫn lên, health báo rõ phần nào không chạy).
- Kiểm tra: bật backend rồi gọi `/api/health` ngay, thấy `camera` và `ai` đúng trạng thái; tắt backend thì đèn camera tắt.

---

## B12 — Tự động xác thực khi có người đứng trước camera (A2)
Chạy nền khi backend chạy, **không cần mở web, không cần bật stream**.

#### CP-01 Vòng lặp nền
- Làm: luồng này khởi động trong `lifespan` ngay khi backend lên (sau khi nạp model và gallery), dừng sạch khi tắt, **không phụ thuộc có trình duyệt nào kết nối hay không**. Mỗi lượt xử lý tự tạo `SessionLocal()` riêng và đóng trong `finally` (luồng nền không dùng `get_db` của request). Luồng riêng gọi `camera.latest()` tối đa `AI_FPS=6` lần/giây (bỏ qua khung đã xử lý rồi, so thời điểm). Có khung thì `detect_faces`; không có mặt thì xóa trạng thái theo dõi. Sau 5 giây không có mặt, hạ xuống 3 lần/giây để tiết kiệm CPU. Mọi ngoại lệ trong vòng lặp được log và vòng lặp **tiếp tục chạy**.
- Kiểm tra: để camera nhìn tường, CPU thấp; nêu số đo trong báo cáo.

#### CP-02 Điều kiện kích hoạt
- Làm: theo dõi mặt giữa các khung bằng IoU > 0,5. Một mặt chỉ được xác thực khi: cạnh ngắn bbox `>= MIN_FACE_PX` (có thể đặt lớn hơn cho xác thực, ví dụ 110), `frame_quality` đạt, và đã xuất hiện ổn định liên tiếp `N=3` khung (khoảng nửa giây). Đứng xa hoặc đi ngang quá nhanh thì không kích.
- Kiểm tra: đi ngang nhanh không có sự kiện; đứng yên trước camera có sự kiện sau khoảng nửa giây.

#### CP-03 Xác thực và phát sự kiện
- Làm: với mỗi mặt đủ điều kiện gọi `verify_face` (B6), giữ 5 kết quả gần nhất của mỗi mặt đang theo dõi. **Granted** khi 2 kết quả liên tiếp cùng một cư dân đều đạt. Ghi `access_logs` bằng `record_access` (B6), dựng `announcement` (B14 CP-05: `display` và `spoken`) bằng cùng một thời điểm đã ghi log, rồi phát sự kiện `access_result {user, decision, reason, similarity, box, announcement, timestamp}` qua callback `on_event` (loa nhận, WebSocket nhận). Hai nơi nhận độc lập: loa lỗi không làm mất sự kiện WebSocket và ngược lại.
- Biên: cư dân `inactive` nhận diện ổn định thì phát sự kiện `inactive_user`.
- Kiểm tra: một người đứng trước camera tạo đúng 1 dòng log (không phải một dòng mỗi khung).

#### CP-04 Chống lặp
- Làm: cư dân granted: không báo lại trong 60 giây (khóa theo `user_id`). Người lạ: cảnh báo khi ít nhất 3 trên 5 kết quả gần nhất là từ chối (`not_matched` hoặc `spoof_detected`), sau đó nghỉ 15 giây. Hằng số đặt đầu file.
- Kiểm tra: đứng yên 30 giây chỉ có vài lần báo, không liên tục.

#### CP-05 Nhiều mặt trong một khung
- Làm: xử lý độc lập từng mặt. Có người lạ trong khung thì **vẫn cảnh báo** dù có cư dân đi cùng (quyết định chủ dự án có thể đổi; ghi vào `DECISIONS_LOG.md`). Khi cả hai sự kiện cùng lúc, cảnh báo người lạ được ưu tiên đọc trước. Khi B5 đang quay đăng ký, vòng lặp tạm dừng (cờ `ai_control.paused` do B11 tạo).
- Kiểm tra: hai người trước camera (một cư dân, một người lạ) ra 2 sự kiện đúng loại.

#### CP-06 Báo trạng thái AI lên web
- Làm: phát `ai_status {running, fps, tracking, last_event_at}` qua WebSocket mỗi 2 giây và mỗi khi đổi trạng thái (đang chờ, đang theo dõi mặt, tạm dừng do đăng ký). Web dùng để hiện chip "AI đang chạy" kể cả khi stream tắt.
- Kiểm tra: tắt stream, chip AI vẫn xanh; đăng ký cư dân thì chip chuyển "tạm dừng", xong thì chạy lại.

#### CP-07 Kịch bản nghiệm thu không cần web
- Làm: viết kịch bản 4 trạng thái và chạy lần lượt: (1) web đóng, stream tắt; (2) web mở, stream tắt; (3) web mở, stream bật; (4) web mở rồi đóng tab giữa chừng. Ở cả 4 trạng thái: cư dân đứng trước camera phải ra đúng 1 dòng `access_logs` và loa đọc đúng; người lạ phải ra cảnh báo và loa đọc đúng.
- Kiểm tra: bảng 4 dòng × 2 tình huống trong `docs/reports/B12.md`, đo độ trễ từ lúc mặt ổn định đến lúc loa bắt đầu đọc (mục tiêu khởi đầu: dưới 2 giây, chỉnh theo số đo).

---

## B13 — Stream camera khi có người xem (A2)

#### CP-01 `GET /api/stream` (MJPEG)
- Làm: `StreamingResponse` với `media_type="multipart/x-mixed-replace; boundary=frame"`. Mỗi phần: `--frame\r\nContent-Type: image/jpeg\r\nContent-Length: N\r\n\r\n` + bytes JPEG + `\r\n`. Dùng generator bất đồng bộ.
- Kiểm tra: `<img src="http://localhost:8000/api/stream">` hiện hình.

#### CP-02 Đếm người xem, không xem thì không mã hóa
- Làm: tăng `viewers` khi bắt đầu, giảm trong `finally`. Chỉ `cv2.imencode` (chất lượng 70, resize chiều ngang 960, tối đa 12 khung/giây) khi trong generator, tức là có ít nhất một người xem.
- Kiểm tra: đóng tab thì `viewers` về 0 và CPU giảm; AI vẫn chạy.

#### CP-03 Vẽ khung và nhãn khi đang stream
- Làm: lấy kết quả mới nhất từ B12 (danh sách bbox, tên hoặc "Không xác định", màu xanh/đỏ). Vẽ `tight_box` và 5 landmark bằng OpenCV.
- Kiểm tra: người lạ khung đỏ, cư dân khung xanh kèm tên.

#### CP-04 Đóng kết nối thì dừng
- Làm: dùng `await request.is_disconnected()` trong vòng lặp; khi đóng, thoát generator.
- Kiểm tra: mở và đóng stream 10 lần, `viewers` về 0, bộ nhớ không tăng.

#### CP-05 Bật/tắt stream không ảnh hưởng AI
- Làm: không có "công tắc bật AI" gắn với stream. Vòng lặp B12 chỉ đọc `camera.latest()`, còn stream chỉ là người xem khung đó. Nút "Xem trực tiếp" trên web chỉ mở hoặc đóng kết nối `/api/stream`. Khi stream tắt, `cv2.imencode` không chạy (tiết kiệm CPU). Thêm `GET /api/stream/snapshot` trả 1 ảnh JPEG của khung mới nhất (để web hiện ảnh tĩnh khi chưa bật stream; không tăng `viewers`).
- Kiểm tra: đo CPU ở 3 trạng thái (không người xem, 1 người xem, 3 người xem) và ghi vào báo cáo; ở mọi trạng thái, đưa mặt vào vẫn có `access_result` và loa.

---

## B14 — Thông báo bằng loa: đọc tiếng Việt mạch lạc (A2)
**Quyết định của chủ dự án:** loa đọc **tiếng Việt mạch lạc, không đánh vần chữ cái**. Vấn đề thường gặp là giọng không phải tiếng Việt đọc văn bản tiếng Việt thì đánh vần hoặc đọc sai. Quy tắc: **chỉ dùng giọng tiếng Việt thật; không có giọng tiếng Việt thì không đọc** (hiện trên web và phát tiếng bíp). Tên người đọc nguyên chữ có dấu (không tách từng chữ). Chỉ số (giờ, phút, số phòng) phải được đổi sang **chữ tiếng Việt** trước khi đưa vào engine, để engine không tự đọc chữ số.

**Hai chuỗi cho mỗi sự kiện:** `display` (hiện trên web, ghi nhật ký, giờ dạng `09:35`) và `spoken` (đã đổi số sang chữ, chỉ dành cho loa). Cùng một dữ liệu, cùng một thời điểm.

**Cấu hình** (`backend/services/speaker_config.py` hoặc `.env`): `SPEAK_ENABLED=true`, `SPEAK_ENGINE=` (`sapi` | `piper` | `edge`), `SPEAK_VOICE_ID=`, `SPEAK_RATE=170`, `SPEAK_VOLUME=1.0`, `ALERT_REPEAT=2` (số lần đọc câu cảnh báo người lạ), `DEDUP_SECONDS=5`, `ROOM_READ_MODE=floor_room` (hoặc `digits`).

#### CP-01 Dò giọng đọc tiếng Việt
- Làm: `scripts/tts_probe.py` liệt kê giọng của máy (pyttsx3/SAPI5: `engine.getProperty("voices")`, nhận biết tiếng Việt qua `id`/`name` chứa `vi-VN`, `viVN` hoặc `Vietnam`; thuộc tính `languages` trên SAPI5 thường rỗng nên không dựa vào nó). Đọc thử câu `"Xin chào, đây là thử nghiệm loa thông báo."` bằng từng giọng tiếng Việt tìm được.
- Phương án khi máy không có giọng tiếng Việt, theo thứ tự: (1) cài gói tiếng Việt của Windows (Settings → Time & language → Language & region → Vietnamese → Text-to-speech); lưu ý có giọng cài rồi nhưng `pyttsx3` vẫn không thấy (giọng loại OneCore), khi đó sang (2); (2) Piper chạy offline với giọng tiếng Việt (tải mô hình `.onnx` và `.json` vào `backend/ai/weights/tts/`, **kiểm tra tên giọng có thật trong danh sách của Piper**); (3) edge-tts (chất lượng tốt nhưng cần Internet, không dùng khi mất mạng). Khuyến nghị dùng (2) cho hệ thống an ninh vì chạy được khi mất mạng.
- Kiểm tra: chủ dự án nghe và chọn giọng; ghi vào `.env` (`SPEAK_ENGINE`, `SPEAK_VOICE_ID`) và `DECISIONS_LOG.md`.

#### CP-02 `so_sang_chu(n)`: số thành chữ
- Làm: đổi 0 đến 99 thành chữ tiếng Việt. Quy tắc: 0 là "không"; 5 là "năm" nhưng sau hàng chục (kể cả 15) là "lăm"; 1 sau hàng chục từ 20 trở lên là "mốt"; 10 là "mười"; 11 đến 19 là "mười một, mười hai, …, mười lăm, …"; 20 là "hai mươi".
- Bộ test bắt buộc: 0→không, 1→một, 5→năm, 10→mười, 11→mười một, 15→mười lăm, 20→hai mươi, 21→hai mươi mốt, 25→hai mươi lăm, 30→ba mươi, 35→ba mươi lăm, 41→bốn mươi mốt, 45→bốn mươi lăm, 55→năm mươi lăm, 59→năm mươi chín, 99→chín mươi chín.
- Kiểm tra: test tự động chạy đủ bộ trên.

#### CP-03 `doc_gio(dt)`: giờ và phút bằng chữ
- Làm: giờ dạng 24 giờ lấy từ `datetime` mà backend dùng để ghi nhật ký. Câu: `"{giờ} giờ {phút} phút"` với giờ, phút qua `so_sang_chu`. Phút = 0 thì nói "đúng": `"chín giờ đúng"`. Giờ 0 đọc "không giờ". Phút 1 đến 9 đọc "linh": `09:05` → "chín giờ linh năm phút" (chủ dự án có thể đổi sang "không năm phút", ghi `DECISIONS_LOG.md`).
- Kiểm tra: test `00:00`, `09:05`, `09:35`, `12:30`, `23:59`.

#### CP-04 `doc_can_ho(code)` và `doc_ten(name)`
- `doc_can_ho`: chữ cái khối nhà (nếu có) đọc theo tên chữ cái tiếng Việt (A→"a", B→"bê", C→"xê", D→"đê", …, bảng đầy đủ A–Z trong code), dấu `-`, `/`, `.` bỏ. Phần số đọc theo `ROOM_READ_MODE`: `floor_room` (mặc định): hai chữ số cuối là số phòng, phần trước là tầng, mỗi phần qua `so_sang_chu`, số phòng dưới 10 đọc kèm "không". Ví dụ `A-1203` → "a, mười hai không ba"; `B-0807` → "bê, tám không bảy"; `C-502` → "xê, năm không hai". `digits`: đọc từng chữ số ("một hai không ba").
- `doc_ten`: bỏ ký tự lạ và chữ số, giữ nguyên chữ có dấu, chuyển TOÀN CHỮ HOA thành dạng chữ thường (engine hay đánh vần chữ viết hoa hết). Không bao giờ tách tên thành từng chữ cái.
- Biên: mã căn hộ rỗng thì bỏ cụm "ở phòng …"; mã có dạng lạ (không có số) thì đọc nguyên chuỗi đã bỏ ký tự đặc biệt.
- Kiểm tra: test các mã `A-1203`, `B-0807`, `C-0502`, `1203`; chủ dự án quyết định đọc theo tầng và phòng hay từng chữ số, ghi `DECISIONS_LOG.md`.

#### CP-05 `announcement(result, when)`: dựng hai chuỗi
- Làm: trả `{"display", "spoken", "kind"}`. `{tên}` = `full_name` (CSDL không có trường username riêng).
  - **Granted:** `display = "{tên} ở phòng {căn hộ} đã vào chung cư lúc {HH}:{MM}."` ; `spoken = "{tên} ở phòng {doc_can_ho} đã vào chung cư lúc {doc_gio}."` Ví dụ: "Nguyễn Văn An ở phòng a, mười hai không ba đã vào chung cư lúc chín giờ ba mươi lăm phút."
  - **Người lạ** (`not_matched` hoặc `spoof_detected`): `"Có người lạ đang ở ngoài chung cư, nhân viên an ninh cần ra gấp."` (cả `display` và `spoken`), `kind="stranger"`.
  - **Inactive:** `"Cư dân {tên} ở phòng {căn hộ} đang bị tạm khóa quyền ra vào, vui lòng liên hệ ban quản lý."` (chủ dự án xác nhận nội dung câu).
- Biên: thiếu `apartment_number` thì bỏ cụm "ở phòng …".
- Kiểm tra: test so khớp chuỗi cho cả ba mẫu.

#### CP-06 `speak(text)` chỉ dùng giọng tiếng Việt
- Làm: nạp engine và giọng đã chọn ở CP-01. Câu người lạ phát trước 3 tiếng bíp ngắn, rồi đọc `ALERT_REPEAT` lần. Không có giọng tiếng Việt thì **không phát giọng khác**: ghi log `speaker_unavailable`, phát tiếng bíp (`winsound.Beep`), vẫn hiện câu `display` trên web, trả `False`.
- Biên: engine lỗi giữa chừng thì khởi tạo lại một lần rồi mới bỏ qua. Chỉ luồng loa được gọi engine (xem CP-07).
- Kiểm tra: tạm đổi cấu hình thành giọng không có thì im lặng chứ không đọc sai.

#### CP-07 Hàng đợi một luồng
- Làm: `queue.PriorityQueue` và một luồng đọc. Cảnh báo người lạ ưu tiên hơn thông báo cư dân; không đọc chồng; không chặn vòng lặp AI (B12 chỉ đưa vào hàng đợi). Câu giống hệt vừa đọc trong `DEDUP_SECONDS` giây thì bỏ. Hàng đợi tối đa 5 mục; đầy thì bỏ mục ưu tiên thấp nhất cũ nhất. `set_muted(True)` dừng đọc ngay và xóa hàng đợi.
- Kiểm tra: hai sự kiện sát nhau đọc lần lượt, cảnh báo đọc trước.

#### CP-08 Nối với sự kiện và các route
- Làm: đăng ký `speaker_service` nhận sự kiện `access_result` từ B12. Route: `POST /api/speaker/test {text}` (phát câu bất kỳ qua cùng đường đọc), `POST /api/speaker/mute {muted}` (nút "Tắt loa"), `GET /api/speaker/status` trả `{enabled, muted, voice, queue}`. Sự kiện WebSocket `access_result` có thêm `announcement.display` và `announcement.spoken`.
- Kiểm tra: bấm thử trên `/docs` nghe được; **không mở web, không bật stream**, chỉ chạy backend mà đưa mặt vào vẫn có tiếng.

#### CP-09 Nghiệm thu bằng tai
- Làm: đọc 10 câu mẫu (tên có dấu như Nguyễn Văn An, Trần Thị Bình, Lê Minh Châu, Phạm Gia Huy, Đặng Thị Hồng Nhung; căn hộ A-1203, B-0807; giờ 0:00, 9:05, 9:35, 12:30, 23:59; câu người lạ), lưu mỗi câu thành `.wav` nếu engine hỗ trợ. Đo thời gian đọc câu dài nhất.
- Kiểm tra: chủ dự án nghe, tick từng câu "mạch lạc" hoặc "chưa đạt, vì sao" (đánh vần, đọc sai thanh, đọc số bằng ngôn ngữ khác); chưa đạt thì chỉnh CP-01 đến CP-05.

---

## B5 — Đăng ký cư dân kèm khuôn mặt (A2)

#### CP-01 Route `POST /api/residents`
- Làm: nhận form `full_name` (2 đến 150 ký tự sau khi bỏ khoảng trắng), `age` (1 đến 120), `apartment_number` (1 đến 20 ký tự, chữ, số, `- / .`). Không còn `frames[]`. Lỗi nhập trả 422 mặc định của FastAPI.
- Biên: hai yêu cầu đăng ký cùng lúc thì yêu cầu sau nhận 409 `{"reason":"registration_in_progress"}` (dùng khóa `threading.Lock`).
- Kiểm tra: `/docs` hiện route; thử dữ liệu sai.

#### CP-02 Quay 3 giây từ camera backend
- Làm: bật cờ `ai_control.paused` (B11), gọi `camera.record(3.0, on_tick)`; mỗi tick tính nhanh `detect_faces` + `frame_quality` cho khung đó và phát `record_progress {t_ms, got, kept}` qua WebSocket. Tắt cờ `paused` trong `finally`.
- Kiểm tra: chạy thật, thấy tiến độ tăng trong 3 giây; sau đó B12 chạy lại.

#### CP-03 Lọc và chọn khung
- Làm: `register_resident(db, info, frames)` (hàm thuần, nhận frames để kiểm thử không cần camera): mỗi khung phải đúng 1 mặt và `frame_quality.ok`. Cần tối thiểu `MIN_GOOD_FRAMES=15`; giữ tối đa `MAX_KEEP=20` khung điểm cao nhất.
- Kiểm tra: đưa 12 khung tốt thì lỗi; 25 khung tốt thì giữ đúng 20.

#### CP-04 Lưu trong một transaction
- Làm: tạo embedding (B3) cho các khung giữ lại, rồi trong một transaction: thêm `User`, `flush()` lấy `id`, thêm các `FaceEmbedding` (kèm `quality`, `model_version`), `commit()`. Lỗi thì `rollback()` toàn bộ. Sau khi lưu, nạp lại bộ nhớ gallery (B6).
- Kiểm tra: giả lập lỗi ở embedding thứ 10 thì bảng `users` không có dòng mới.

#### CP-05 Phản hồi đúng hợp đồng
- Làm: thành công trả 201 `{id, user_code, frames_kept}`; thiếu khung trả 422 `{"reason":"not_enough_quality_frames","good":n,"required":15}`. Cập nhật `API_CONTRACT.md` nếu đổi gì.
- Kiểm tra: `curl -X POST .../api/residents -F full_name=... -F age=30 -F apartment_number=A-1203` trong cả hai trường hợp.

#### CP-06 Kiểm thử
- Làm: test với frames lấy từ `test_data/` (đủ và thiếu khung), ghi kết quả và số dòng `face_embeddings` vào báo cáo.
- Kiểm tra: khớp tiêu chí xong của B5.

---

## B6 — Xác thực và quyết định (A2)

#### CP-01 `decide(similarity, liveness, user)`
- Làm: thứ tự kiểm tra: `liveness` sai → `("denied","spoof_detected")`; `user` là `None` → `("denied","not_matched")`; `user.status != "active"` → `("denied","inactive_user")`; còn lại `("granted","ok")`.
- Kiểm tra: bảng chân trị 4 hàng chạy đúng.

#### CP-02 Gallery trong bộ nhớ
- Làm: `GalleryCache`: nạp mọi `face_embeddings` thành `{user_id: ndarray (n,512)}` kèm thông tin người (tên, căn hộ, status). **Giữ cả cư dân inactive** để nhận ra họ. `reload(db)` gọi lúc khởi động, sau B5 thành công, sau PATCH trạng thái.
- Kiểm tra: in số người và số vector.

#### CP-03 `verify_face(db, image, face)` và `verify_image(db, image)`
- Làm: cho một mặt: `check_liveness` trước (nếu giả thì bỏ qua embedding cho nhanh) → `crop_face` → `get_embedding` → `best_match` → `decide`. Đo thời gian từng bước (`ms`). `verify_image` xử lý mặt lớn nhất và trả thêm `faces` (số mặt phát hiện được).
- Biên: không có mặt thì trả `decision="denied"`, `reason="no_face"`, **không ghi log** (tránh nhiễu).
- Kiểm tra: chạy 1 ảnh cư dân, in kết quả.

#### CP-04 Ghi `access_logs`
- Làm: `record_access(db, result)` ghi một dòng cho mỗi quyết định thật (cả granted và denied). Dùng chung cho `/api/verify` và B12.
- Kiểm tra: đếm dòng log sau 4 lần thử.

#### CP-05 `POST /api/verify`
- Làm: nhận `image` (multipart, JPEG/PNG; giải mã bằng `cv2.imdecode`, ảnh hỏng trả 400). Trả `{user, similarity, liveness, decision, reason, box, crop_b64, faces, ms}` với `box = tight_box`, `crop_b64` = ảnh 112×112 mã hóa JPEG base64 để UI hiện vùng cắt.
- Kiểm tra: khớp bảng trong `API_CONTRACT.md`.

#### CP-06 Kiểm thử bốn tình huống
- Làm: cư dân hợp lệ → granted/ok; người lạ → denied/not_matched; ảnh chụp từ màn hình → denied/spoof_detected; cư dân bị tắt → denied/inactive_user. Ghi vào báo cáo.
- Kiểm tra: 4 dòng log đúng.

---

## B7 — Các route còn lại và WebSocket (A2)

#### CP-01 `GET /api/residents`
- Làm: trả `[{id, user_code, full_name, age, apartment_number, status, frames}]` với `frames` = số dòng `face_embeddings` (truy vấn gộp, không N+1).
- Kiểm tra: `/docs`.

#### CP-02 `PATCH /api/residents/{id}/status`
- Làm: nhận `{"status":"active"|"inactive"}`, giá trị khác trả 422, không có id trả 404. Cập nhật gallery trong bộ nhớ.
- Kiểm tra: tắt một cư dân rồi xác thực thì ra `inactive_user`.

#### CP-03 `GET /api/logs`
- Làm: lọc `decision` (granted/denied), `q` (tìm theo tên, không phân biệt hoa thường), `from`/`to` (ISO 8601), `limit` mặc định 200 tối đa 1000, sắp xếp mới nhất trước; người không xác định hiện "Không xác định".
- Kiểm tra: từng bộ lọc cho kết quả đúng.

#### CP-04 `WS /ws/dashboard` và broadcast
- Làm: bộ quản lý kết nối; `broadcast(event, data)` gọi được **từ luồng nền** bằng `asyncio.run_coroutine_threadsafe` với event loop lưu lúc khởi động. Ping mỗi 20 giây; khi kết nối gửi ngay `camera_status`. Các sự kiện theo `API_CONTRACT.md`.
- Kiểm tra: mở 2 kết nối thử, đưa mặt vào thì cả hai nhận `access_result`.

---

## B8 — Trang Cư dân và Tổng quan thời gian thực (A3)
Bố cục tham khảo `docs/demo/smart-access-demo.html` (chỉ để tham khảo, không bắt buộc giống). Địa chỉ backend lấy từ `VITE_API_URL`. Thông báo lỗi tiếng Việt, đổi từ mã `reason`.

#### CP-01 `useDashboardSocket`
- Làm: xóa `hooks/useCamera.js` và `components/CameraView.jsx` của khung cũ (dùng `getUserMedia` sẽ tranh camera với backend), thay bằng hook này và `LiveStream` (CP-02). Hook kết nối `/ws/dashboard`, tự nối lại (chờ 1 giây tăng dần tới 10 giây), trả `{connected, lastResult, cameraStatus, recording}`.
- Kiểm tra: tắt rồi bật backend, giao diện tự kết nối lại.

#### CP-02 `LiveStream`
- Làm: thẻ `<img>` trỏ `/api/stream` **chỉ khi bật**. Mặc định **tắt** mỗi lần mở trang (`enabled=false`), khung hiện dòng "Stream đang tắt, AI vẫn chạy"; bật bằng nút "Xem trực tiếp". Khi bật mà camera `running=false` thì hiện "Camera chưa sẵn sàng". tắt hoặc rời trang thì đặt `src=""` để đóng kết nối.
- Kiểm tra: tab Network không còn request stream sau khi tắt.

#### CP-03 Dashboard
- Làm: chip trạng thái camera, AI, stream, loa; số liệu trong ngày; sự kiện mới nhất kèm câu `display` (có dấu) và dòng nhỏ hiển thị chuỗi `spoken` đã đọc; nút "Xem trực tiếp" (bật/tắt `<img>` stream, chip camera và AI giữ nguyên khi tắt) và nút "Tắt loa" (gọi `POST /api/speaker/mute`); danh sách hoạt động gần đây.
- Kiểm tra: đưa mặt vào, Dashboard tự cập nhật không tải lại trang.

#### CP-04 Form cư dân
- Làm: họ tên, tuổi, căn hộ, kiểm tra nhập ở phía giao diện trước khi gửi; chặn gửi đôi khi đang quay.
- Kiểm tra: bỏ trống thì báo lỗi, không gọi API.

#### CP-05 Nút Quay 3 giây
- Làm: gọi `POST /api/residents`; trong lúc chờ hiện `RecordProgress` (thanh 3 giây, số khung thu được và giữ lại, từ `record_progress`); xử lý 201 (làm mới danh sách), 422 `not_enough_quality_frames` (báo "chỉ thu được n/15 khung đạt, hãy nhìn thẳng và đủ sáng rồi thử lại"), 409.
- Kiểm tra: thử cả hai trường hợp; có thể dùng mock khi backend chưa xong.

#### CP-06 Danh sách cư dân
- Làm: bảng mã, tên, tuổi, căn hộ, số khung, trạng thái; nút Tắt/Bật gọi PATCH.
- Kiểm tra: tắt một người thì chip đổi màu ngay.

---

## B9 — Trang Xác thực và Nhật ký (A3)

#### CP-01 `api.js` và `websocket.js`
- Làm: một instance axios có `baseURL`, xử lý lỗi mạng chung; hàm cho từng route.
- Kiểm tra: gọi `/api/health`.

#### CP-02 Trang Xác thực
- Làm: hiện stream và kết quả từng người theo sự kiện `access_result` (không có nút chụp, vì xác thực chạy tự động).
- Kiểm tra: đưa mặt vào thì kết quả hiện sau khoảng 1 giây.

#### CP-03 Khung mặt và vùng cắt
- Làm: `FaceBox` vẽ khung và 5 landmark từ `box`; ô nhỏ hiện `crop_b64` ghi chú "vùng đưa vào nhận diện (chỉ mặt)".
- Kiểm tra: ô vùng cắt không thấy tóc và tai.

#### CP-04 Câu loa đã đọc
- Làm: hiện `announcement.display` kèm giờ cho mỗi sự kiện, màu xanh cho granted, đỏ cho denied; bên dưới là `announcement.spoken` chữ nhỏ xám (để kiểm tra loa đọc gì, số đã đổi sang chữ).
- Kiểm tra: khớp câu mẫu ở B14 CP-05.

#### CP-05 `DoorStatus` (giai đoạn 2)
- Làm: hiển thị Đã khóa/Đang mở và đếm ngược 10 giây từ sự kiện `door_state`; khi chưa có giai đoạn 2 thì ẩn.
- Kiểm tra: mô phỏng sự kiện bằng dữ liệu giả.

#### CP-06 Trang Nhật ký
- Làm: bảng thời gian, tên, độ giống, chống giả mạo, kết quả, lý do; lọc theo tên và kết quả (gọi `/api/logs` với tham số lọc, có debounce 300 ms).
- Kiểm tra: lọc đúng.

---

## B10 — Kiểm thử tích hợp và đo số liệu (A6 + bạn)
Bố cục `test_data/` (không commit): `people/<tên>/*.jpg` (ít nhất 3 người, mỗi người 10 ảnh trở lên), `strangers/*.jpg`, `spoof/*.jpg` (ảnh chụp lại từ màn hình điện thoại và ảnh in).

#### CP-01 Chuẩn hóa bộ test và kịch bản
- Làm: liệt kê số ảnh từng nhóm, chia mỗi người một nửa để đăng ký (qua `register_resident`) và một nửa để thử; viết kịch bản bằng văn bản.
- Kiểm tra: bảng số lượng ảnh trong báo cáo.

#### CP-02 Đo độ chính xác theo ngưỡng
- Làm: script quét `SIM_THRESHOLD` từ 0,30 đến 0,70 bước 0,02; tính FAR = (người lạ được cho vào)/(lượt người lạ), FRR = (cư dân bị từ chối)/(lượt cư dân), accuracy, và điểm EER.
- Kiểm tra: bảng và biểu đồ FAR/FRR; đề xuất ngưỡng.

#### CP-03 Đo thời gian xử lý
- Làm: 100 lượt mỗi bước (phát hiện, liveness, embedding, so khớp, tổng) trên laptop, báo trung bình và p95.
- Kiểm tra: bảng thời gian; ghi cấu hình máy.

#### CP-04 Đo chống giả mạo
- Làm: tính APCER (ảnh giả được chấp nhận) và BPCER (ảnh thật bị chặn) theo `LIVENESS_MIN`.
- Kiểm tra: bảng và danh sách ảnh giả lọt qua.

#### CP-05 Tổng hợp
- Làm: bảng tổng hợp, ngưỡng đề xuất, giới hạn quan sát được (ánh sáng, kính, góc nghiêng, song sinh nếu có).
- Kiểm tra: dùng được làm Chương 3.

#### CP-06 Nghiệm thu thời gian thực end-to-end
- Làm: chạy kịch bản B12 CP-07 trên máy thật với ít nhất 3 người, mỗi người 5 lượt đi vào (đi bình thường, đứng chờ, đeo kính) và 5 lượt người lạ. Đo: độ trễ mặt ổn định → loa đọc (trung bình, p95), số cảnh báo giả (cư dân bị báo là người lạ), số bỏ sót (người lạ không cảnh báo), số lần báo lặp bất thường.
- Kiểm tra: bảng số liệu và nhận xét đưa vào Chương 3.

---

## H1 — MQTT phía Backend (A2)

#### CP-01 `publish_decision`
- Làm: `paho-mqtt` (`loop_start()`, tự nối lại), đọc `MQTT_BROKER_HOST/PORT` từ `.env`; topic `door/access/decision`, payload `{"decision":"granted"}` hoặc `{"decision":"denied"}`, QoS 1, không retain. Trả `bool`.
- Biên: broker chết thì ghi log và trả `False`, **không làm hỏng việc ghi nhật ký**.
- Kiểm tra: `mosquitto_sub -t "door/#" -v` thấy tin. (Mosquitto cấu hình `allow_anonymous true` chỉ để thử trong mạng nội bộ.)

#### CP-02 Gọi sau khi ghi log
- Làm: gọi trong `record_access` cho cả granted và denied. Quy tắc nhiều mặt cho cửa: có ít nhất một granted trong cùng khung thì publish granted.
- Kiểm tra: cả hai nhánh đều có tin.

---

## H3 — FreeRTOS cho STM32F103C8T6 (A4)
Tài nguyên hạn chế (SRAM khoảng 20 KB): heap FreeRTOS vài KB, stack mỗi task 128 đến 256 từ. Mặc định an toàn: **relay tắt khi khởi động**.

#### CP-01 Parse lệnh và `mqtt_task`
- Làm: UART nhận dòng kết thúc `\n` từ ESP32 (115200 8N1, ngắt hoặc DMA, bộ đệm 96 byte). `Parse_Decision` tìm `"granted"` hoặc `"denied"`, trả `DECISION_UNKNOWN` nếu không rõ. Đưa vào `Queue` độ sâu 4.
- Biên: dòng quá dài hoặc lạ thì bỏ, không đổi trạng thái khóa.
- Kiểm tra: gõ chuỗi mẫu qua USB-TTL.

#### CP-02 `door_task` nhánh granted
- Làm: LED xanh bật, relay bật (mức tác động là macro `RELAY_ACTIVE_LEVEL`, nhiều module relay kích mức thấp), khởi động `xTimerCreate(..., pdMS_TO_TICKS(10000), pdFALSE, ...)`; hết giờ thì relay tắt, LED tắt. Granted tới lúc đang mở thì đặt lại timer.
- Kiểm tra: đo 10 giây bằng đồng hồ.

#### CP-03 `door_task` nhánh denied
- Làm: LED đỏ bật, còi kêu 3 tiếng (200 ms bật, 200 ms tắt), **không chạm relay**. Denied không rút ngắn thời gian mở đang có.
- Kiểm tra: relay giữ nguyên trạng thái.

#### CP-04 `sensor_task`
- Làm: đọc reed switch (kéo lên, chống dội: lấy mẫu 20 ms, đổi trạng thái khi 3 mẫu liên tiếp giống nhau). Cửa mở khi khóa đang đóng thì báo bất thường; cửa mở quá 30 giây sau granted thì cảnh báo.
- Kiểm tra: đóng mở bằng tay, trạng thái đổi đúng, không nhảy.

#### CP-05 `status_task`
- Làm: mỗi 5 giây gửi `{"lock":"locked","door":"closed"}\n` xuống UART; bật IWDG khoảng 2 giây và nạp trong task này.
- Kiểm tra: thấy gói trạng thái trên UART; treo task thử thì chip tự khởi động lại và khóa đóng.

---

## H4 — ESP32: WiFi, MQTT, UART (A5)

#### CP-01 WiFi
- Làm: thông tin WiFi trong `wifi_config.h` (không commit); `WiFi.begin`, tự nối lại khi mất, báo trạng thái.
- Kiểm tra: tắt rồi bật router, ESP32 tự nối lại.

#### CP-02 Subscribe MQTT
- Làm: `PubSubClient` kết nối broker, subscribe `door/access/decision`, hàm `reconnect()` có chờ tăng dần; đặt Last Will cho `esp32cam/status` `{"online":false}`; publish `esp32cam/status` mỗi 10 giây (IP, RSSI).
- Kiểm tra: `mosquitto_pub` gửi lệnh, ESP32 in ra serial.

#### CP-03 Chuyển tiếp qua UART
- Làm: `Serial2.begin(115200, SERIAL_8N1, RX_PIN, TX_PIN)` (chọn chân khả dụng trên ESP32-CAM, tránh chân dùng cho flash/boot, kiểm tra sơ đồ chân), `Serial2.println(payload)` cho từng tin nhận được; dòng nhận từ STM32 thì publish lên `door/status`. Hai bên cùng mức 3,3 V.
- Kiểm tra: lệnh từ laptop tới STM32 thành công, trạng thái từ STM32 về tới broker.

---

## H6 — Fail-safe (A4 + A5)

#### CP-01 Phát hiện mất kết nối
- Làm: ESP32 gửi `{"hb":1}` xuống STM32 mỗi 2 giây khi MQTT còn sống; mất MQTT quá 10 giây thì ngừng gửi. STM32 không nhận dòng hợp lệ nào trong 10 giây thì vào trạng thái FAULT.
- Kiểm tra: rút WiFi, sau 10 giây STM32 báo FAULT.

#### CP-02 Hành vi khi lỗi
- Làm: FAULT: relay tắt (khóa đóng), LED đỏ nhấp nháy chậm, trạng thái báo `fault`; có lệnh hợp lệ trở lại thì thoát FAULT. Backend không nhận `door/status` quá 15 giây thì phát `door_state` lỗi lên Dashboard.
- Kiểm tra: rút WiFi khi đang chạy, khóa vẫn đóng, Dashboard báo lỗi.

---

## C1 — ESP32-CAM phát stream MJPEG (A5)
Backend vẫn là chủ camera; ESP32-CAM chỉ là nguồn hình.

#### CP-01 Khởi tạo OV2640
- Làm: cấu hình chân theo AI-Thinker, `frame_size=FRAMESIZE_VGA`, `jpeg_quality` 10 đến 12, `fb_count=2` (cần PSRAM), `grab_mode=CAMERA_GRAB_LATEST`.
- Kiểm tra: chụp và xem được 1 ảnh.

#### CP-02 Máy chủ MJPEG
- Làm: HTTP server cổng 81, đường dẫn `/stream`, `multipart/x-mixed-replace`.
- Kiểm tra: mở bằng trình duyệt hoặc VLC.

#### CP-03 Ổn định 30 phút
- Làm: chạy liên tục, tự nối lại WiFi, log fps và bộ nhớ trống mỗi phút.
- Kiểm tra: không treo, không rò bộ nhớ.

## C2 — RemoteCamera trong backend (A2)

#### CP-01 `RemoteCamera`
- Làm: `FrameSource` đọc `cv2.VideoCapture("http://<ip>:81/stream")`, tự nối lại khi mất, cùng giao diện với `LocalCamera`.
- Kiểm tra: rút điện ESP32 cắm lại, backend tự lấy lại hình.

#### CP-02 Chọn nguồn bằng `.env`
- Làm: `CAMERA_SOURCE=local` hoặc URL; thêm vào `.env.example`.
- Kiểm tra: đổi nguồn không phải sửa code.

#### CP-03 Chạy toàn luồng với ESP32-CAM
- Làm: nhận diện nền, stream, loa chạy nguyên; đo độ trễ từ lúc đưa mặt vào đến lúc loa đọc và mức dùng CPU.
- Kiểm tra: bảng đo trong báo cáo.

## C3 — Đo lại với ESP32-CAM (A1)

#### CP-01 Thu bộ ảnh từ ESP32-CAM
- Làm: ảnh ở đúng vị trí cổng, nhiều điều kiện ánh sáng, cùng những người trong bộ test webcam.
- Kiểm tra: đếm ảnh.

#### CP-02 Đo lại
- Làm: lặp B10 CP-02 và CP-04 với ảnh ESP32-CAM.
- Kiểm tra: bảng so sánh webcam và ESP32-CAM.

#### CP-03 Đề xuất ngưỡng mới
- Làm: chọn `SIM_THRESHOLD` và `LIVENESS_MIN` cho từng nguồn nếu cần, ghi lý do.
- Kiểm tra: cập nhật `DECISIONS_LOG.md`.