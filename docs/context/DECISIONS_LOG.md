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
| Mỗi viewer mã hóa JPEG riêng nên CPU tăng gần tuyến tính theo số viewers (13% / 20,8% / 55% với 0 / 1 / 3 viewers) | Hiện tại hệ thống phục vụ nội bộ ít người xem; phương án nếu cần cho nhiều client: mã hóa một lần chia sẻ buffer cho nhiều client |

## Đề xuất đổi contract
(Agent ghi đề xuất ở đây: ID việc, thay đổi muốn làm, lý do, Agent nào bị ảnh hưởng. Chủ dự án duyệt hoặc từ chối rồi ghi kết quả bên cạnh.)

| ID việc | Đề xuất | Lý do | Ảnh hưởng | Kết quả duyệt |
|---|---|---|---|---|
