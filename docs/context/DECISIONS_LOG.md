# NHẬT KÝ QUYẾT ĐỊNH (thêm dòng mới ở cuối, không sửa dòng cũ)

| Quyết định | Lý do |
|---|---|
| Bỏ xác thực giọng nói | Giữ phạm vi vừa sức và tập trung vào khuôn mặt, nhúng, web |
| Thêm cư dân bắt buộc kèm khuôn mặt, lưu trong một transaction | Cư dân thiếu khuôn mặt không xác thực được nên không được tồn tại |
| Đăng ký bằng đoạn quay 3 giây thay vì 5 tư thế | Nhiều khung hình hơn, đủ biến thiên góc và ánh sáng, thao tác đơn giản hơn |
| Giữ tối đa 20 khung tốt nhất, tối thiểu 15 khung đạt | Tránh kho embedding quá lớn mà vẫn đủ ổn định; tránh đăng ký bằng dữ liệu kém |
| Nhận diện bằng vùng căn chỉnh 112x112 theo 5 landmark | Loại tóc và tai, đúng đầu vào chuẩn của model |
| Chống giả mạo dùng vùng cắt riêng (mở rộng quanh mặt) | MiniFASNet cần ngữ cảnh quanh mặt, khác vùng cắt nhận diện |
| `status` active/inactive trên cư dân | Tạm dừng quyền ra vào mà không xóa dữ liệu |
| Dùng `buffalo_sc` | Nhẹ, chạy tốt trên CPU laptop; chỉ có 5 landmark; độ chính xác thấp hơn `buffalo_l` nên phải đo bằng thực nghiệm |
| Ngưỡng độ giống ban đầu 0,50, chỉnh theo FAR/FRR thực đo | Không có ngưỡng đúng sẵn cho mọi dữ liệu |
| Web trước, phần cứng sau | Tách rủi ro; STM32 và MQTT có thể làm song song vì payload đã cố định |
| STM32F103 không có WiFi nên ESP32 làm cầu nối UART | Tận dụng ESP32-CAM đã mua |
| Camera do backend giữ, trình duyệt không mở camera | Windows chỉ cho một chương trình dùng camera; AI phải chạy cả khi không có web |
| Xác thực tự động nền, kích hoạt khi mặt đủ lớn, đủ chất lượng, ổn định 3 khung | Không cần nút chụp; tránh kích khi đi ngang |
| Stream MJPEG tùy chọn, chỉ mã hóa khi có người xem | Tiết kiệm CPU; AI độc lập với stream |
| Loa đọc tiếng Việt mạch lạc, chỉ dùng giọng tiếng Việt; số, giờ, phòng đổi sang chữ trước khi đọc | Quyết định chủ dự án; giọng khác đọc tiếng Việt sẽ đánh vần hoặc sai |
| Dùng full_name làm "username" khi đọc loa | CSDL không có trường username riêng |
| Chống lặp: cư dân 60 giây; người lạ cần 3/5 kết quả từ chối rồi nghỉ 15 giây | Tránh loa đọc liên tục khi người đứng yên trước camera |
| Chạy song song bằng git worktree, mỗi Agent một nhánh; commit qua `scripts/agent_commit.py` | `git add -A` trong cùng một thư mục làm Agent này commit nhầm code dở của Agent kia |
| Đổi contract (hàm, route, schema) phải được chủ dự án duyệt trước | Ba Agent song song dựa vào contract; một Agent tự đổi sẽ làm hai Agent kia hỏng |
| B4 chưa đạt tiêu chí chống giả mạo: 8/8 ảnh chụp lại màn hình lọt ở mọi ngưỡng 0,40–0,80; giữ `LIVENESS_MIN=0,60` | MiniFASNetV2 bỏ sót replay phủ kín khung (mất viền màn hình trong vùng cắt 2,7). Chưa có ngưỡng nào tách được ảnh thật/giả trên bộ hiện tại; cần thêm liveness theo thời gian hoặc model khác rồi đo lại, không tăng ngưỡng >0,99 dựa trên 8 ảnh |
| Hạ `SIM_THRESHOLD` từ 0,50 xuống **0,40**; hằng chuyển vào `backend/ai/config.py`, `matcher.py` import lại (giữ tên `ai.matcher.SIM_THRESHOLD`) | Đo 231 cặp thật (10 selfie + 8 webcam của chủ dự án, 4 người lạ): `best_match` cùng người 0,5447–0,8444, người lạ −0,1154–0,1125. Ngưỡng 0,40 cách người lạ cao nhất 0,2875 và cách cùng người thấp nhất 0,1447; 0,50 chỉ còn 0,0447 dưới cùng người thấp nhất, trong khi A2 đo trực tiếp được 0,5552. Dữ liệu nhỏ nên ngưỡng là tạm thời; chống đăng ký trùng khuôn mặt khuyến nghị 0,60 (chưa làm backend) |

## Đề xuất đổi contract
(Agent ghi đề xuất ở đây: ID việc, thay đổi muốn làm, lý do, Agent nào bị ảnh hưởng. Chủ dự án duyệt hoặc từ chối rồi ghi kết quả bên cạnh.)

| ID việc | Đề xuất | Lý do | Ảnh hưởng | Kết quả duyệt |
|---|---|---|---|---|
| B4 CP-06 (bổ sung, chờ duyệt) | Thêm hàm MỚI trong `backend/ai/anti_spoof.py`: `check_liveness_sequence(frames, boxes)` → `(is_real: bool, score: float, detail: dict)`. `frames`/`boxes` là 6–15 khung gần nhất của CÙNG một mặt (A2 đã theo dõi bằng IoU), mỗi phần tử là ảnh BGR đầy đủ + bbox tương ứng. Hàm giữ nguyên `check_liveness(image, bbox)` làm cổng đầu; chỉ thêm cổng thời gian. Không đổi route, không đổi schema, không đổi tên hàm cũ. | B4 chưa đạt: MiniFASNetV2 chấp nhận 8/8 ảnh replay (có viền lẫn full-frame) ở mọi ngưỡng 0,40–0,80; điểm giả/thật chồng lấn nên không thể cứu bằng ngưỡng. Cần tín hiệu theo thời gian (ổn định điểm, biến thiên khung, chuyển động khớp của landmark) để tách ảnh tĩnh/replay khỏi người thật. | A2 (B12) phải giữ 6–15 khung gần nhất kèm bbox của mỗi mặt đang theo dõi và gọi hàm mới sau khi `check_liveness` đạt; A1 viết hàm + script đo. Không ảnh hưởng A3/A4/A5. Dữ liệu đo cần video ngắn (xem yêu cầu bên dưới). | Đã duyệt (chủ dự án, 2026-10-24) |
| B4 CP-06 (chốt luật quyết định) | `check_liveness_sequence` bỏ tín hiệu chuyển động, chỉ dùng: cửa sổ 15 khung, tỷ lệ khung có điểm ≥ `LIVENESS_MIN` (0,60) đạt ≥ 0,87, độ lệch chuẩn điểm ≤ 0,11. Mỗi tham số là một hằng riêng trong `config.py`: `LIVENESS_SEQ_FRAMES`, `LIVENESS_SEQ_FRAC_MIN`, `LIVENESS_SEQ_STD_MAX`; xoá `LIVENESS_SEQ_MOTION_MIN`. `detail` trả thêm `frac`, `std`, `frames`, `median`, `minimum` để A2 ghi `access_logs`. Trạng thái B4: "đạt cho demo, chưa kiểm định rộng". | Trên 2 clip hiệu chỉnh, chuyển động người thật và replay video chồng lấn (trung vị 7,37 so với 6,99) nên không tách được; độ lệch chuẩn điểm và tỷ lệ khung đạt tách hoàn toàn. Kiểm định trên 3 clip thật + 3 clip giả mới: 0/146 cửa sổ giả lọt, 211/226 cửa sổ thật qua (biên hẹp 0,0083). "Chuyển động 0,000" chỉ đo trên clip tổng hợp, không dùng làm bằng chứng cho ảnh tĩnh cầm tay. | A2 (B12) gọi hàm sau `check_liveness`, ghi `frac`/`std`/`frames` vào `access_logs`; A1 khuyến nghị đòi 2 cửa sổ liên tiếp cùng đạt (~3,0 giây ở 10 khung/giây) nhưng không tự làm. Không ảnh hưởng A3/A4/A5. | Đã duyệt (chủ dự án, 2026-10-25) |
