# Prompt dùng chung

## Tiếp tục việc dở (sau khi hết token, đổi công cụ, hoặc phiên mới)
```
Đọc AGENTS.md và docs/context/. Tiếp tục việc <ID> theo thứ tự:
1. Mở docs/reports/<ID>.md: xem checklist (checkpoint [x] cuối cùng) và mục "Bàn giao khi bị ngắt".
2. Chạy git status và git diff để thấy phần code chưa commit.
3. Nếu code dở chưa có nhật ký: ghi nhật ký cho phần đó trước (scripts/log_checkpoint.py ... --auto), rồi commit.
4. Làm tiếp từ checkpoint chưa tick. KHÔNG viết lại phần đã có.
Giữ đúng quy tắc báo cáo theo checkpoint trong AGENTS.md.
```

## Kiểm tra chéo (giao cho A6 sau mỗi việc xong)
```
Đọc AGENTS.md. Đọc docs/reports/<ID>.md và code tương ứng. Với mỗi checkpoint trong nhật ký, kiểm tra: (a) file và dòng ghi có đúng với code không, (b) code có làm đúng như mô tả không, (c) có khớp DB_SCHEMA.md / API_CONTRACT.md không. Ghi kết quả vào mục "Tổng kết cuối" của báo cáo đó. Chỉ báo lỗi, không sửa code nghiệp vụ.
```

## Viết bản tường trình cho người đọc (bạn dùng để học và trả lời hội đồng)
```
Đọc docs/reports/<ID>.md và code tương ứng. Viết thêm vào mục "Tổng kết cuối": giải thích bằng ngôn ngữ đơn giản từng hàm hoặc từng bảng đã làm, vì sao chọn cách đó, giới hạn, và 3 câu hỏi hội đồng có thể hỏi kèm gợi ý trả lời.
```
