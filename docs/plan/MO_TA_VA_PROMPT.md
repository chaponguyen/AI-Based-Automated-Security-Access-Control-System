> **Lưu ý:** file này là bản cũ. Prompt đang dùng nằm ở `docs/prompts/<ID>.md` (đã có quy tắc checkpoint và chế độ chạy song song). Chỉ dùng file này để tra bảng mô tả công việc.

# Mô tả công việc và prompt cho AI

Dùng cùng `PHAN_CHIA_CONG_VIEC.md`. Mỗi việc có hai phần: bảng mô tả (để bạn biết việc đó làm gì, ra file nào) và prompt (dán vào công cụ).

**Cách ghép prompt:** `[PREFIX]` + nội dung của việc + `[SUFFIX]`. Thay `A?` và thư mục theo bảng ở mục 1.

## 1. Khung prompt chung

**PREFIX**
```
Đọc AGENTS.md, sau đó docs/context/PROJECT_BRIEF.md, DB_SCHEMA.md, API_CONTRACT.md,
DECISIONS_LOG.md và dòng cuối PROGRESS_LOG.md trước khi làm bất cứ việc gì.
Bạn là Agent A? ({vai trò}). Chỉ được sửa trong: {thư mục}.
Giữ nguyên tên hàm và chữ ký đã có trong các file khung.
```

**SUFFIX**
```
Khi xong:
1. Chạy phần kiểm tra đã nêu và dán kết quả thật. Không viết "đã chạy tốt" nếu chưa chạy.
2. Commit sau mỗi hàm hoàn chỉnh, định dạng "[module] mô tả ngắn - A?".
3. Thêm một mục vào cuối PROGRESS_LOG.md; ghi quyết định mới (nếu có) vào DECISIONS_LOG.md.
4. Viết docs/reports/<ID>_baocao.md (đã làm, chưa làm, file đã đổi) và
   docs/reports/<ID>_tuongtrinh.md (giải thích từng hàm, vì sao chọn cách này,
   3 câu hội đồng có thể hỏi kèm gợi ý trả lời).
Không tự chạy lệnh ghi vào database thật (alembic upgrade, xóa dữ liệu); để tôi chạy.
Thiếu thông tin hoặc thiếu file model thì dừng lại và hỏi, không tự chế.
```

| Agent | Vai trò | Thư mục |
|---|---|---|
| A1 | AI Engine | `backend/ai/` |
| A2 | Backend và DB | `backend/api/, backend/services/, backend/database/, backend/main.py, backend/migrations/` |
| A3 | Frontend | `frontend/src/` |
| A4 | STM32 | `embedded/` |
| A5 | ESP32-CAM | `esp32-cam/` |
| A6 | QA và tài liệu | `docs/reports/, tests/` |

## 2. Bảng mô tả công việc

| ID | Mô tả | Đầu vào | Đầu ra | Lưu ý chính |
|---|---|---|---|---|
| B1 | Cấu hình Alembic, sinh migration đầu tiên từ `models.py` | `models.py`, `.env` | `alembic.ini`, `backend/migrations/` | `env.py` đọc `DATABASE_URL`, tuyệt đối không có đường lui sang SQLite |
| B2 | Phát hiện mặt, cắt mặt chuẩn, lọc chất lượng khung | Ảnh BGR | `detector.py`, `aligner.py`, `quality.py` | Cắt chỉ gồm lông mày đến cằm; nạp model một lần |
| B3 | Tạo embedding và so khớp | Ảnh đã cắt 112x112 | `embedder.py`, `matcher.py`, script đo | Chuẩn hóa L2; mỗi người lấy trung bình top-3 độ giống |
| B4 | Chống giả mạo MiniFASNetV2 | Ảnh + bbox | `anti_spoof.py` | Dùng vùng cắt mở rộng riêng, khác vùng cắt nhận diện |
| B5 | Đăng ký cư dân từ đoạn quay 3 giây | Thông tin + khoảng 30 JPEG | `registration_service.py`, `POST /api/residents` | Một transaction; dưới 15 khung đạt thì 422 và không tạo user |
| B6 | Xác thực một ảnh, ra quyết định, ghi log | 1 JPEG | `decision.py`, `verification_service.py`, `POST /api/verify` | Mọi lượt đều ghi `access_logs`; `inactive` luôn bị từ chối |
| B7 | Các route còn lại và WebSocket | — | `residents.py`, `logs.py`, `ws.py` | Đúng `API_CONTRACT.md` |
| B8 | Trang Cư dân: form, quay 3 giây, danh sách, bật/tắt | Contract, bản demo | `Residents.jsx`, `useCamera.js`, `RecordProgress.jsx` | 10 khung/giây trong 3 giây; hiển thị lỗi 422 |
| B9 | Trang Xác thực, Tổng quan, Nhật ký | Contract, bản demo | 3 trang + `FaceBox`, `DoorStatus`, `LogTable` | Gửi tuần tự, không chồng yêu cầu |
| B10 | Script đo và báo cáo thực nghiệm | Bộ ảnh test | `tests/evaluate.py`, `ketqua_thuc_nghiem.md` | Không chỉnh ngưỡng âm thầm; báo cáo cả kết quả xấu |
| H1 | Publish MQTT từ backend | Quyết định granted/denied | `mqtt_service.py` | Lỗi MQTT không làm hỏng lượt xác thực |
| H3 | Firmware STM32: 4 task FreeRTOS | Payload JSON qua UART | `Tasks/*.c`, `MQTT/mqtt_client.*` | Bạn tạo trước project CubeMX; denied không chạm relay |
| H4 | ESP32 cầu nối WiFi, MQTT, UART | MQTT | `esp32-cam/src,network,mqtt` | Không dùng GPIO16 (PSRAM) cho UART |
| H6 | Fail-safe | — | sửa `Tasks/`, `esp32-cam/` | Mất liên lạc thì khóa giữ đóng |
| H7 | Kiểm thử đầu cuối web tới khóa | — | `h7_checklist.md` | Cả granted và denied |
| C1 | ESP32-CAM chụp và POST ảnh | Cảm biến/nút kích hoạt | `camera_handler.cpp` | Chỉ làm sau khi H4 ổn định |
| C2 | Đo lại với ảnh ESP32-CAM | Ảnh từ ESP32-CAM | bảng so sánh | Có thể cần chỉnh ngưỡng |

## 3. Prompt cho từng việc

### B1 — A2 — Migration
```
Nhiệm vụ B1. backend/database/models.py đã có 3 bảng đúng DB_SCHEMA.md.
1. Trong backend/, chạy "alembic init migrations", sửa migrations/env.py: lấy DATABASE_URL từ
   biến môi trường (python-dotenv), target_metadata = Base.metadata, import đủ 3 model.
   KHÔNG được có bất kỳ đường lui nào sang sqlite hoặc sqlalchemy.url mặc định trong alembic.ini.
   Nếu thiếu DATABASE_URL thì báo lỗi rõ ràng.
2. Sinh revision: alembic revision --autogenerate -m "initial tables".
3. Đọc file revision, xác nhận có đúng 3 bảng, khóa ngoại, ON DELETE CASCADE của face_embeddings,
   CHECK của users.status, kiểu ARRAY(Float).
Kiểm tra: python -c "from database.models import Base; print(list(Base.metadata.tables))"
Không chạy alembic upgrade.
```

### B2 — A1 — Phát hiện, cắt, lọc
```
Nhiệm vụ B2. Làm detector.py, aligner.py, quality.py trong backend/ai/.
- detector.py: dùng insightface FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"]),
  prepare(ctx_id=-1, det_size=(640,640)). Nạp một lần (singleton). detect_faces(image_bgr) trả
  list dict {bbox, kps (5 điểm), score}.
- aligner.py: crop_face dùng insightface.utils.face_align.norm_crop(image, kps, 112) để lấy vùng
  mặt căn chỉnh. tight_box(kps) trả khung hiển thị tính từ landmark (lông mày đến cằm), hệ số để
  thành hằng số có tên.
- quality.py: frame_quality trả {ok, score, reason}. Loại khung khi: không đúng 1 mặt, mặt quá nhỏ,
  mờ (phương sai Laplacian của vùng mặt), quá tối hoặc cháy sáng, nghiêng quá mức (ước lượng từ
  vị trí mũi so với hai mắt). Mọi ngưỡng là hằng số đặt tên ở đầu file.
Yêu cầu quan trọng: ảnh cắt đưa vào nhận diện không được chứa tóc và tai. Nếu norm_crop còn lấy
dư phần trán hoặc tóc, nói rõ và đề xuất cách siết nhưng không đổi kích thước 112x112.
Kiểm tra: viết script nhỏ chạy trên ảnh trong test_data/, lưu ảnh cắt ra test_output/ cho tôi xem
bằng mắt; in số khung bị loại theo từng lý do.
```

### B3 — A1 — Embedding và so khớp
```
Nhiệm vụ B3. Làm embedder.py và matcher.py.
- get_embedding(aligned_112): dùng model nhận diện của buffalo_sc, trả vector 512 chiều đã chuẩn hóa L2.
- best_match(embedding, gallery): gallery là {user_id: [embedding,...]}. Với mỗi người lấy trung bình
  top-3 độ giống cosine; trả (user_id hoặc None, similarity). SIM_THRESHOLD là hằng số.
- Viết tests/eval_similarity.py: với test_data/ (mỗi người một thư mục), tính phân bố độ giống
  cùng người và khác người, rồi FAR/FRR tại các ngưỡng 0.30 đến 0.70 bước 0.05. Xuất bảng markdown.
Không chọn ngưỡng cuối cùng; chỉ báo cáo số liệu và nêu ngưỡng đề xuất kèm lý do.
```

### B4 — A1 — Chống giả mạo
```
Nhiệm vụ B4. Làm anti_spoof.py bằng MiniFASNetV2 bản ONNX tại backend/ai/weights/.
1. Tìm cấu hình tiền xử lý đúng của model (kích thước đầu vào, hệ số mở rộng vùng cắt quanh mặt,
   thứ tự kênh màu, lớp nào là "thật"). Ghi nguồn tham khảo vào đầu file. Nếu không chắc,
   dừng lại và hỏi tôi thay vì đoán.
2. check_liveness(image_bgr, bbox) trả (is_real, score). Vùng cắt mở rộng này KHÁC vùng cắt nhận diện.
3. Chạy trên ảnh thật và ảnh chụp lại từ màn hình điện thoại trong test_data/, báo tỷ lệ phát hiện
   đúng và tỷ lệ báo nhầm, kèm điểm số từng ảnh.
```

### B5 — A2 — Đăng ký cư dân
```
Nhiệm vụ B5. Làm registration_service.py và POST /api/residents theo API_CONTRACT.md.
- Nhận multipart: full_name, age (1 đến 120), apartment_number, frames[] (tối đa 60 ảnh, mỗi ảnh
  tối đa 1 MB).
- Với mỗi khung: decode (cv2.imdecode) -> detect -> quality. Chọn tối đa MAX_KEEP=20 khung điểm cao
  nhất, tạo embedding từ vùng cắt chuẩn, lưu FaceEmbedding kèm quality và model_version.
- Dưới MIN_GOOD_FRAMES=15 khung đạt: trả 422 {reason:"not_enough_quality_frames", good, required}
  và KHÔNG tạo user. Toàn bộ User + FaceEmbedding trong một transaction, lỗi thì rollback.
- Route viết dạng def thường (không async) để xử lý nặng không chặn event loop.
Kiểm tra: script gửi 30 ảnh test (thật) và 30 ảnh toàn đen; xác nhận trường hợp đầu tạo user,
trường hợp sau trả 422 và bảng users không tăng.
```

### B6 — A2 — Xác thực
```
Nhiệm vụ B6. Làm decision.py, verification_service.py, POST /api/verify.
Thứ tự: không có mặt (no_face) -> hơn một mặt (multiple_faces) -> chất lượng thấp (low_quality)
-> chống giả mạo không đạt (spoof_detected) -> không khớp (not_matched) -> user inactive
(inactive_user) -> granted (ok). Trả {user, similarity, liveness, decision, reason, box, crop_b64}
với crop_b64 là ảnh vùng cắt nhận diện (PNG base64, nhỏ).
Mọi lượt đều ghi access_logs (user_id NULL khi không khớp). Sau khi ghi, đẩy sự kiện lên WebSocket.
Gallery embedding nạp từ DB; có cách làm mới khi thêm cư dân (cache đơn giản, không cần Redis).
Kiểm tra: 5 tình huống (cư dân active, cư dân inactive, người lạ, ảnh giả, ảnh không có mặt),
dán JSON trả về của từng ca.
```

### B7 — A2 — Route còn lại
```
Nhiệm vụ B7. Làm GET /api/residents (kèm số khung đã lưu), PATCH /api/residents/{id}/status
(chỉ nhận active hoặc inactive), GET /api/logs (lọc decision, q theo tên, from, to) và
WS /ws/dashboard (quản lý danh sách kết nối, broadcast sự kiện access_result và door_state).
Đúng từng trường trong API_CONTRACT.md. Kiểm tra từng route trên /docs và dán kết quả.
```

### B8 — A3 — Trang Cư dân
```
Nhiệm vụ B8. Làm trang Residents.jsx theo bản demo docs/demo/smart-access-demo.html (chỉ lấy bố cục
và luồng, viết lại bằng React).
- Form họ tên, tuổi, căn hộ + khung camera. Nút "Quay 3 giây và lưu cư dân" chỉ bật khi form hợp lệ.
- useCamera.js: getUserMedia, hàm recordFrames(3, 10) chụp 10 ảnh/giây vào canvas, trả mảng Blob JPEG
  (rộng tối đa 640px, chất lượng 0.9). Dừng stream khi rời trang.
- RecordProgress: thanh tiến độ 3 giây và số khung đã thu.
- Gửi FormData (frames[]) tới POST /api/residents. Lỗi 422 hiển thị rõ "chỉ n/15 khung đủ chất lượng,
  hãy quay lại, nhìn thẳng và đủ sáng". Thành công thì tải lại danh sách.
- Danh sách cư dân + nút bật/tắt gọi PATCH.
- Xử lý: từ chối quyền camera, không có camera.
Nếu backend chưa chạy, dùng dữ liệu giả bật bằng biến VITE_USE_MOCK=true. Không dùng localStorage.
```

### B9 — A3 — Xác thực, Tổng quan, Nhật ký
```
Nhiệm vụ B9. Làm Verify.jsx, Dashboard.jsx, AccessLogs.jsx và các component FaceBox, DoorStatus, LogTable.
- Verify: nút Bắt đầu/Dừng; khi chạy, mỗi 1 giây chụp 1 khung gửi POST /api/verify, chỉ gửi khi yêu
  cầu trước đã xong. Hiển thị khung mặt (box), ảnh vùng cắt từ crop_b64, kết quả từng bước và lý do
  bằng tiếng Việt theo mã reason.
- Dashboard: số liệu trong ngày, hoạt động gần đây, trạng thái cửa qua WebSocket (ghi rõ "Mô phỏng"
  khi chưa có phần cứng), tự kết nối lại khi mất WebSocket.
- AccessLogs: bảng, lọc theo tên và kết quả, gọi GET /api/logs.
Giao diện dùng cùng phong cách bản demo.
```

### B10 — A6 — Đo thực nghiệm
```
Nhiệm vụ B10 (bạn không sửa code nghiệp vụ). Viết tests/evaluate.py chạy trên test_data/ và
xuất docs/reports/ketqua_thuc_nghiem.md cùng CSV:
- Nhận diện: accuracy, precision, recall, FAR, FRR ở ngưỡng hiện tại và bảng quét ngưỡng.
- Chống giả mạo: tỷ lệ phát hiện ảnh giả và tỷ lệ báo nhầm người thật.
- Hệ thống: tỷ lệ granted đúng, từ chối nhầm cư dân hợp lệ, lọt người lạ.
- Thời gian: trung bình và phân vị 95 của từng bước (detect, crop, embedding, anti-spoof, tổng).
- Phân tích lỗi: liệt kê ca sai và nguyên nhân có thể (ánh sáng, góc, kính).
Ghi rõ số ảnh, số người, điều kiện chụp. Báo cáo cả kết quả xấu, không làm đẹp số liệu.
```

### H1 — A2 — MQTT phía backend
```
Nhiệm vụ H1. Làm services/mqtt_service.py dùng paho-mqtt 2.x (CallbackAPIVersion.VERSION2).
Đọc host/port từ .env. Kết nối một lần khi khởi động, tự nối lại. publish_decision(decision) gửi
{"decision": "granted"|"denied"} tới door/access/decision với QoS 1. Lỗi MQTT chỉ ghi log,
không làm hỏng lượt xác thực. Gọi hàm này sau khi ghi access_logs trong verification_service.
Kiểm tra: dùng mosquitto_sub -t door/access/decision -v, dán kết quả khi gọi /api/verify.
```

### H3 — A4 — Firmware STM32
```
Nhiệm vụ H3. Project STM32CubeIDE (STM32F103C8T6, FreeRTOS CMSIS_V2, UART, GPIO) tôi đã tạo trong
embedded/stm32-security-lock/. Bạn viết 4 task trong Tasks/ và MQTT/mqtt_client.*.
- Chân GPIO: đặt macro trong main.h cho Relay, LED xanh, LED đỏ, Buzzer, Reed; mức tích cực của
  relay là macro RELAY_ACTIVE_LEVEL (module relay có thể tích cực mức thấp). Hỏi tôi nếu chưa rõ chân.
- mqtt_task: nhận từng dòng JSON kết thúc bằng '\n' qua UART (ngắt hoặc DMA, bộ đệm vòng, không
  cấp phát động), Parse_Decision, gửi vào queue. Dữ liệu không nhận ra thì bỏ qua, không mở khóa.
- door_task: granted -> LED xanh + relay mở, đặt timer một lần 10 giây rồi đóng relay và tắt LED
  (nhận lệnh granted mới thì làm mới timer). denied -> LED đỏ + buzzer khoảng 2 giây, KHÔNG chạm relay.
- sensor_task: đọc reed có chống dội (3 lần liên tiếp cách 20 ms). Cửa mở khi khóa đang đóng, hoặc
  mở quá 10 giây sau khi khóa đã đóng lại, thì phát cảnh báo.
- status_task: mỗi 5 giây gửi {"lock":..., "door":...}\n qua UART.
STM32F103C8T6 chỉ có 20 KB RAM: ghi rõ kích thước stack từng task và lý do. Tôi sẽ build trong CubeIDE;
nếu không chạy được lệnh build thì nói rõ là chưa biên dịch.
```

### H4 — A5 — ESP32 cầu nối
```
Nhiệm vụ H4 (giai đoạn 2, CHƯA dùng camera). Viết esp32-cam/src/main.cpp, network/wifi_manager.cpp,
mqtt/mqtt_handler.cpp dùng PlatformIO + PubSubClient.
- WiFi: SSID/mật khẩu đọc từ src/wifi_config.h (đã nằm trong .gitignore), tự nối lại không chặn loop.
- MQTT: nối lại có backoff; subscribe door/access/decision; khi nhận, ghi nguyên payload + '\n'
  xuống UART nối STM32. Publish esp32cam/status (retained) và đặt Last Will là {"online":false}.
- UART tới STM32: dùng GPIO14 (TX) và GPIO13 (RX), 115200. KHÔNG dùng GPIO16 (nối PSRAM trên
  ESP32-CAM) và tránh GPIO0/2/12/15 (strapping). Kiểm tra lại với sơ đồ board và nói nếu khác.
- Đọc dòng trạng thái từ STM32 qua UART rồi publish lên door/status.
Kiểm tra: mosquitto_pub gửi {"decision":"granted"}, xem Serial Monitor ESP32 và dòng UART đầu ra.
```

### H6 — A4 + A5 — Fail-safe
```
Nhiệm vụ H6 (làm ở cả hai thư mục; A4 sửa embedded/, A5 sửa esp32-cam/, tôi sẽ chạy hai phiên riêng).
Quy tắc: mất liên lạc thì khóa giữ đóng, không bao giờ báo thành công giả.
- ESP32 gửi {"hb":1}\n mỗi 5 giây xuống STM32. STM32 quá 15 giây không có dòng hợp lệ nào thì: ép
  relay tắt, LED đỏ nhấp nháy chậm, gửi cờ lỗi ở status. Có lại tín hiệu thì tự trở về bình thường.
- Bật IWDG trên STM32 và làm mới trong vòng lặp giám sát.
- ESP32: mất MQTT thì không nhận lệnh cũ khi nối lại (bỏ qua message có retained = true trên
  door/access/decision).
Kiểm tra: mô tả và dán kết quả ba ca: rút WiFi, tắt broker, rút dây UART khi khóa đang mở.
```

### H7 — A6 — Kiểm thử đầu cuối
```
Nhiệm vụ H7 (không sửa code nghiệp vụ). Tạo docs/reports/h7_checklist.md: bảng các ca từ web đến khóa
(cư dân active, người lạ, ảnh giả, cư dân inactive, mất WiFi, tắt broker, cửa mở quá giờ), mỗi ca có
bước thực hiện, kết quả mong đợi, cột kết quả thật và ghi chú cho tôi điền. Với ca nào đọc được từ
log backend thì ghi lệnh lấy log tương ứng.
```

### C1 — A5 — Camera ESP32-CAM
```
Nhiệm vụ C1 (chỉ làm khi H4 đã chạy ổn). Viết camera/camera_handler.cpp.
- Khởi tạo camera AI-Thinker bằng esp_camera với sơ đồ chân chuẩn (CAMERA_MODEL_AI_THINKER trong
  ví dụ CameraWebServer của Espressif), JPEG, khung VGA, chất lượng khoảng 12.
- Kích hoạt chụp khi có tín hiệu ở một GPIO cấu hình được, hoặc mỗi N giây (cấu hình bằng macro).
- Gửi POST multipart (field "image") tới http://<IP laptop>:8000/api/verify bằng HTTPClient; không chồng
  yêu cầu; hết thời gian chờ thì bỏ khung đó. Quyết định MQTT do backend gửi, ESP32 không cần xử lý kết quả.
- Giải phóng bộ đệm khung (esp_camera_fb_return) sau mỗi lần dùng.
Tránh xung đột chân: camera chiếm nhiều GPIO, UART tới STM32 vẫn là GPIO14/13.
```

### C2 — A6 + A1 — Đo lại với ESP32-CAM
```
Nhiệm vụ C2. Tôi cung cấp thư mục test_data_esp32/ (ảnh chụp bằng ESP32-CAM cùng những người đã đăng ký
bằng webcam). Chạy lại tests/evaluate.py, lập bảng so sánh webcam và ESP32-CAM (độ giống trung bình,
FAR, FRR, tỷ lệ khung bị loại ở bước chất lượng). Đề xuất có nên chỉnh ngưỡng cho nguồn ESP32-CAM không,
kèm số liệu; không tự đổi ngưỡng trong code.
```

## 4. Prompt dùng khi gặp sự cố

**Phiên bị ngắt giữa chừng**
```
Đọc AGENTS.md, rồi chạy git status, git diff và đọc dòng cuối PROGRESS_LOG.md. Cho tôi biết việc <ID>
đã làm tới đâu, rồi làm tiếp phần còn thiếu. Không viết lại những gì đã có.
```

**Agent báo xong nhưng chưa kiểm chứng**
```
Bạn chưa dán kết quả chạy thật của phần kiểm tra. Hãy chạy lại, dán nguyên văn đầu ra, và nói rõ
phần nào bạn chưa chạy được và vì sao.
```

**Agent sửa ngoài phạm vi**
```
Bạn vừa sửa file ngoài thư mục được phép. Hoàn tác các thay đổi đó bằng git, rồi nêu thay đổi
bạn muốn đề xuất cho Agent phụ trách thư mục kia dưới dạng ghi chú, không tự sửa.
```

**Bạn chưa hiểu code Agent viết (trước khi sang việc sau)**
```
Giải thích lại <ID> như dạy một sinh viên năm cuối: luồng dữ liệu từ đầu vào đến đầu ra, từng hàm làm
gì, chỗ nào dễ sai, và 3 câu hỏi hội đồng có thể hỏi về phần này.
```
