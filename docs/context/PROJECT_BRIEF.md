# PROJECT BRIEF (chỉ chủ dự án được sửa)

**Đề tài:** AI-Based Automated Security Access Control System — quản lý ra vào chung cư thông minh.

## Phạm vi
- Xác thực bằng **khuôn mặt** (không dùng giọng nói). Chống giả mạo khuôn mặt.
- Web quản lý: Tổng quan, Cư dân, Xác thực, Nhật ký.
- Giai đoạn 1: chạy trên laptop. Giai đoạn 2: MQTT + STM32 + khóa 12V. Giai đoạn 3: ESP32-CAM.

## Quy tắc nghiệp vụ đã chốt
1. Thêm cư dân luôn kèm đăng ký khuôn mặt, làm cùng một bước. Không có cư dân nào thiếu khuôn mặt.
2. Đăng ký bằng cách **quay 3 giây** lấy nhiều khung hình (không chụp 5 tư thế). Lọc chất lượng, giữ tối đa 20 khung tốt nhất, cần ít nhất 15 khung đạt, nếu không thì từ chối và không lưu gì.
3. Khi nhận diện chỉ đưa **vùng mặt đã căn chỉnh theo 5 landmark (112x112)**, không có tóc và tai.
4. Cư dân có trạng thái `active` / `inactive`. `inactive` thì luôn bị từ chối dù khuôn mặt khớp.
5. Cho phép (`granted`) khi: có người khớp, `active`, chống giả mạo đạt, độ giống >= ngưỡng.
6. Giai đoạn 2: mọi quyết định (granted và denied) đều gửi MQTT `{"decision": ...}` xuống STM32. Mất kết nối thì khóa giữ trạng thái đóng.
7. Backend là chủ duy nhất của camera. Xác thực chạy nền tự động khi backend chạy, không cần mở web và không cần bật stream.
8. Stream camera (MJPEG) là tùy chọn, chỉ mã hóa hình khi có người xem. Bật hoặc tắt stream không ảnh hưởng AI và loa.
9. Loa: granted đọc "<tên> ở phòng <căn hộ> đã vào chung cư lúc <giờ> phút"; denied (người lạ hoặc giả mạo) đọc "Có người lạ đang ở ngoài chung cư, nhân viên an ninh cần ra gấp". Loa đọc tiếng Việt mạch lạc bằng giọng tiếng Việt thật (không đánh vần); không có giọng tiếng Việt thì không đọc.

## Công nghệ
React + Vite · FastAPI · PostgreSQL + SQLAlchemy + Alembic · InsightFace `buffalo_sc` (SCRFD + nhận diện, ONNX Runtime) · MiniFASNetV2 · OpenCV · WebSocket · (GĐ2) MQTT, STM32F103C8T6 + FreeRTOS, relay, khóa 12V, reed switch · (GĐ3) ESP32-CAM.

## Không làm
Xác thực giọng nói · tự huấn luyện model · YOLO · chống deepfake dạng injection.

## Giới hạn đã biết (ghi vào báo cáo)
Song sinh cùng trứng; chống giả mạo không tuyệt đối; laptop là điểm lỗi duy nhất ở giai đoạn 1.
