# Phân chia công việc

## 1. Người thực hiện

| Vai trò | Công cụ gợi ý | Phạm vi |
|---|---|---|
| **Bạn (điều phối)** | — | Cài môi trường, mua phần cứng, chuẩn bị ảnh test, chạy migration, đọc bản tường trình, đo số liệu, viết báo cáo, **nghe thử loa, chọn giọng tiếng Việt (B14)** |
| **A1 — AI Engine** | OpenCode (Nemotron 3 Ultra) | `backend/ai/` |
| **A2 — Backend và DB** | Codex CLI | `backend/api/`, `services/` (gồm camera nền, vòng lặp xác thực tự động, stream, loa), `database/` |
| **A3 — Frontend** | Cline (DeepSeek V4 Flash) | `frontend/src/` |
| **A4 — STM32** (giai đoạn 2) | Antigravity | `embedded/` |
| **A5 — ESP32-CAM** (giai đoạn 2–3) | Cline (DeepSeek V4 Flash) | `esp32-cam/` |
| **A6 — QA và tài liệu** | FreeCoder (DeepSeek V4.1 Flash); hết quota thì dùng Cline | `docs/reports/`, test |

Công cụ chỉ là gợi ý theo quota; đổi được vì mọi Agent đều đọc chung `AGENTS.md` và `docs/context/`.

## 2. Giai đoạn 0 — Chuẩn bị (bạn tự làm, khoảng 1 buổi)

| ID | Việc | Xong khi |
|---|---|---|
| P0-1 | Tạo venv, `pip install -r requirements.txt` | `python -c "import insightface, onnxruntime, cv2"` không lỗi |
| P0-2 | Cài PostgreSQL, tạo database `access_control`, điền `backend/.env` | `psql` đăng nhập được |
| P0-3 | Tải model `buffalo_sc` (lệnh trong README). Tải `2.7_80x80_MiniFASNetV2.pth` từ repo minivision-ai/Silent-Face-Anti-Spoofing (thư mục `resources/anti_spoof_models/`) vào `backend/ai/weights/`; repo gốc chỉ có `.pth`, file `.onnx` do A1 tạo ở B4 CP-01 (hoặc bạn dùng bản `.onnx` có sẵn từ nguồn khác, khi đó vẫn kiểm tra lại cách cắt và chuẩn hóa ở B4 CP-02, CP-03) | Có file `.pth` (hoặc `.onnx`) trên đĩa |
| P0-4 | Chuẩn bị ảnh test: 3 người, mỗi người 10 ảnh; 5 ảnh chụp lại từ màn hình điện thoại; vài ảnh đeo kính, ngược sáng | Có thư mục `test_data/` (không commit) |
| P0-5 | `git init`, đẩy lên GitHub, kiểm tra `.env` không bị đưa lên | GitHub không thấy `.env` |
| P0-6 | Cắm webcam, kiểm tra Windows nhận camera (ứng dụng Camera mở được, sau đó **đóng hẳn**); kiểm tra loa laptop; kiểm tra máy có **giọng đọc tiếng Việt** (Settings → Language → Vietnamese → Text-to-speech) hoặc chuẩn bị Piper offline | Camera hiện hình; nghe được loa; biết máy đang có giọng tiếng Việt hay chưa |

## 3. Giai đoạn 1 — Web trên laptop

| ID | Việc | Agent | Phụ thuộc | Kết quả | Tiêu chí xong |
|---|---|---|---|---|---|
| B1 | Viết `models.py` thật, Alembic migration đầu tiên | A2 | P0-2 | 3 bảng | Bạn chạy `alembic upgrade head`, thấy 3 bảng trong pgAdmin |
| B2 | `detector.py`, `aligner.py`, `quality.py` | A1 | P0-3 | Phát hiện mặt, cắt 112x112, lọc khung | Ảnh cắt chỉ gồm lông mày đến cằm, không tóc và tai; khung mờ hoặc có 2 mặt bị loại |
| B3 | `embedder.py`, `matcher.py` | A1 | B2 | Embedding 512 chiều, so khớp | Cùng người: độ giống cao; khác người: thấp; có bảng số liệu trên ảnh test |
| B4 | `anti_spoof.py` (vùng cắt mở rộng riêng) | A1 | B2 | Phân biệt thật và giả | Chặn được ảnh chụp từ màn hình điện thoại trong bộ test |
| B5 | `registration_service.py` + `POST /api/residents` (backend tự quay 3 giây từ camera, không nhận `frames[]`) | A2 | B1, B2, B3, B11 | Tạo cư dân kèm embedding trong một transaction | Đủ 15 khung đạt thì lưu; thiếu thì trả 422 và không tạo user; trong lúc quay, xác thực tự động tạm dừng rồi chạy lại |
| B6 | `decision.py`, `verification_service.py` + `POST /api/verify`, ghi `access_logs` | A2 | B1, B3, B4 | Quyết định granted/denied kèm lý do | Cư dân `inactive` luôn bị từ chối; người lạ và ảnh giả bị từ chối |
| B7 | `GET/PATCH` cư dân, `GET /api/logs`, `WS /ws/dashboard` | A2 | B1 | Các route còn lại | Test được trên `/docs` |
| B11 | Camera chạy nền trong backend: `FrameSource`, `LocalCamera`, tự mở lại khi mất camera, bộ đệm khung, `GET /api/camera/status`, cấu hình `.env`, cờ `ai_control.paused`, `main.py` (lifespan nạp model và chạy camera/AI ngay khi bật backend, CORS, health) | A2 | P0-6 | Backend là chủ duy nhất của camera (trình duyệt không mở camera) | Rút cắm camera, backend không cần khởi động lại; `record(3.0)` trả 25–32 khung |
| B12 | **Tự động xác thực khi có người đứng trước camera**: vòng lặp nền 6 lần/giây, theo dõi mặt, kích hoạt khi mặt đủ lớn và ổn định, quyết định, ghi `access_logs`, chống báo lặp, phát sự kiện `access_result` và `ai_status` | A2 | B3, B4, B6, B11 | Chạy khi backend chạy, **không cần mở web, không cần bật stream** | Web đóng, stream tắt, đưa mặt vào: 1 dòng nhật ký, 1 sự kiện, loa đọc; không báo liên tục khi đứng yên |
| B13 | **Stream camera trực tiếp tùy chọn**: `GET /api/stream` (MJPEG), đếm người xem, chỉ mã hóa hình khi có người xem, vẽ khung và nhãn, snapshot | A2 | B11, B12 | Xem trực tiếp khi cần, tắt thì tiết kiệm CPU | Đóng tab stream thì `viewers` về 0, CPU giảm, AI và loa vẫn chạy |
| B14 | **Thông báo bằng loa, đọc tiếng Việt mạch lạc**: giọng tiếng Việt, số đổi sang chữ (`so_sang_chu`, `doc_gio`, `doc_can_ho`), `announcement` (`display` và `spoken`), hàng đợi một luồng, ưu tiên cảnh báo người lạ, `POST /api/speaker/test`, `mute`, `status` | A2 (+ bạn nghe thử) | B12 | Granted: "<tên> ở phòng <phòng> đã vào chung cư lúc <giờ>". Denied: "Có người lạ đang ở ngoài chung cư, nhân viên an ninh cần ra gấp" | Không mở web mà đưa mặt vào vẫn có tiếng; đọc mạch lạc, không đánh vần; không có giọng tiếng Việt thì im và báo trên web; cảnh báo đọc trước thông báo thường |
| B8 | Trang **Cư dân** (form, nút quay 3 giây gọi backend, tiến độ qua WebSocket, danh sách, bật/tắt) và **Tổng quan thời gian thực** (WebSocket tự nối lại, chip camera/AI/stream/loa, nút **Xem trực tiếp**, nút **Tắt loa**) | A3 | `API_CONTRACT.md` chốt (làm trước với dữ liệu giả) | Giống `docs/demo/smart-access-demo.html` | Thêm được cư dân thật kèm khuôn mặt; Dashboard tự cập nhật khi có người đi vào, không cần tải lại trang |
| B9 | Trang **Xác thực** (không có nút chụp: kết quả hiện theo sự kiện, kèm câu `display` và chuỗi `spoken`), **Nhật ký** (lọc), ô vùng cắt, `DoorStatus` | A3 | B6, B7, B12, B13, B14 | Giao diện nối backend | Một lượt xác thực chạy từ camera đến nhật ký, hiện sau khoảng 1 giây |
| B10 | Kiểm thử tích hợp và đo: độ chính xác, FAR, FRR, thời gian xử lý mỗi lượt, tỷ lệ chặn giả mạo, **độ trễ từ lúc mặt ổn định đến lúc loa đọc**, số cảnh báo giả và bỏ sót | A6 + bạn | B5–B14 | Bảng số liệu | Có số liệu thật cho Chương 3 |

**Thứ tự gợi ý:** P0 → (B1 ‖ B2 ‖ B11) → B3 → (B4 ‖ B5) → B6 → B12 → (B7 ‖ B13 ‖ B14) → B9 → B10. B8 chạy song song từ sau khi `API_CONTRACT.md` được chốt. B14 phần `so_sang_chu`, `doc_gio`, `doc_can_ho` và `announcement` (thuần hàm) có thể làm sớm vì không cần camera.

## 4. Giai đoạn 2 — Phần cứng (có thể làm song song với giai đoạn 1)

| ID | Việc | Agent | Tiêu chí xong |
|---|---|---|---|
| H1 | Cài Mosquitto trên laptop; `mqtt_service.py` publish `{"decision": ...}` | A2 | Dùng `mosquitto_sub` thấy được message |
| H2 | Tạo project STM32CubeIDE (F103C8T6), bật FreeRTOS, GPIO relay/LED/buzzer/reed, UART | Bạn + A4 | Project biên dịch và nạp được |
| H3 | 4 task FreeRTOS: `mqtt_task`, `door_task`, `sensor_task`, `status_task`; timer tự đóng 10 giây | A4 | granted mở 10 giây rồi đóng; denied chỉ bật LED đỏ và còi, relay không đổi |
| H4 | ESP32: WiFi + MQTT, chuyển tiếp payload qua UART xuống STM32 | A5 | Lệnh từ laptop tới STM32 thành công |
| H5 | Ráp khóa 12V, nguồn, relay, reed switch; chọn nguồn đủ dòng cho khóa | Bạn | Khóa đóng mở đúng theo lệnh |
| H6 | Fail-safe: mất MQTT hoặc UART thì giữ khóa đóng, báo lỗi, không báo thành công giả | A4 + A5 | Rút WiFi khi đang chạy, khóa vẫn đóng |
| H7 | Chạy thật từ web đến khóa: granted và denied | Tất cả | Cả hai nhánh đúng, có ghi nhật ký |

## 5. Giai đoạn 3 — ESP32-CAM làm camera cửa

| ID | Việc | Agent | Tiêu chí xong |
|---|---|---|---|
| C1 | ESP32-CAM phát stream MJPEG (`/stream`, cổng 81), chạy ổn định 30 phút | A5 | Mở được bằng trình duyệt hoặc VLC |
| C2 | `RemoteCamera` trong backend (cùng giao diện `FrameSource`), chọn nguồn bằng `CAMERA_SOURCE` trong `.env` | A2 | Đổi nguồn không sửa code; nhận diện nền, stream và loa chạy nguyên với ESP32-CAM |
| C3 | Đo lại độ chính xác với ảnh từ ESP32-CAM (chất lượng thấp hơn webcam) và chỉnh ngưỡng | A1 + A6 | Có bảng so sánh webcam và ESP32-CAM |

## 6. Tài liệu (làm xuyên suốt)

| ID | Việc | Agent | Khi nào |
|---|---|---|---|
| D1 | Sau mỗi ID xong: báo cáo tiến độ và bản tường trình vào `docs/reports/`, cập nhật `PROGRESS_LOG.md` | Agent làm việc đó | Mỗi lần |
| D2 | Bạn đọc từng bản tường trình và tự giải thích lại được | Bạn | Trước khi sang việc tiếp |
| D3 | Viết Chương 1–3 và kết luận từ các báo cáo tích lũy | A6 + bạn | Từ B10 trở đi |

## 7. Việc đầu tiên nên giao ngay

1. Bạn làm P0-1 đến P0-6.
2. Giao **B1** và **B11** cho A2, **B2** cho A1 cùng lúc (ba việc độc lập nhau). A2 làm xong B1 rồi mới sang B11 nếu muốn tuần tự.
3. Giữ B8 (A3) đến khi `API_CONTRACT.md` được bạn xác nhận.

## 8. Rủi ro cần theo dõi

| Rủi ro | Xử lý |
|---|---|
| `buffalo_sc` kém chính xác hơn `buffalo_l`, ảnh ngược sáng hoặc đeo khẩu trang | Đo ở B10; nếu thiếu, thử `buffalo_l` (đổi tên model, giữ nguyên code) |
| Cài `onnxruntime` hoặc `insightface` lỗi trên Windows | Kiểm tra bản Python 3.10 hoặc 3.11; cài Visual Studio Build Tools nếu cần biên dịch |
| Ngưỡng 0,50 không phù hợp dữ liệu thật | Chọn lại từ đường FAR/FRR của bộ ảnh test |
| Khóa 12V kéo dòng lớn làm treo vi điều khiển | Nguồn riêng cho khóa, chung đất, có diode bảo vệ relay |
| Laptop tắt thì hệ thống ngừng | Ghi vào giới hạn của báo cáo; khóa mặc định đóng |
| Trên Windows một camera chỉ một chương trình mở được | Backend giữ camera; trình duyệt không gọi `getUserMedia`, chỉ xem `/api/stream` |
| Vòng lặp AI chạy liên tục làm nóng CPU | Hạ xuống 3 lần/giây khi không có mặt; stream chỉ mã hóa khi có người xem; đo CPU ở B12 và B13 |
| Báo lặp hoặc cảnh báo giả làm phiền cư dân | Chống lặp theo cư dân 60 giây, người lạ cần 3/5 kết quả từ chối rồi nghỉ 15 giây; đo số cảnh báo giả ở B10 CP-06 |
| Máy không có giọng tiếng Việt, hoặc `pyttsx3` không thấy giọng đã cài | Cài gói tiếng Việt của Windows; nếu vẫn không thấy dùng Piper offline; edge-tts chỉ khi có Internet (B14 CP-01). Không có giọng thì im, báo trên web, không đọc bằng giọng khác |
| Giọng đọc sai thanh điệu hoặc đọc số sai | Số, giờ, phòng đã đổi sang chữ trước khi đọc; nghiệm thu bằng tai ở B14 CP-09 |
