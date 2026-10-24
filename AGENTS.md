# AGENTS.md — đọc trước khi viết bất kỳ dòng code nào

Thứ tự đọc: `docs/context/PROJECT_BRIEF.md` → `DB_SCHEMA.md` → `API_CONTRACT.md` → `DECISIONS_LOG.md` → `PROGRESS_LOG.md` → mục việc của bạn trong `docs/plan/PHAN_CHIA_CONG_VIEC.md`.

| Agent | Thư mục được sửa | Không được sửa |
|---|---|---|
| A1 — AI Engine | `backend/ai/` | `backend/api/`, `backend/database/` |
| A2 — Backend & DB | `backend/api/`, `backend/services/` (camera nền, xác thực tự động, stream, loa), `backend/database/`, `backend/main.py`, `backend/.env.example`, `scripts/tts_probe.py` | `backend/ai/` (chỉ gọi hàm) |
| A3 — Frontend | `frontend/src/` | mọi thư mục khác |
| A4 — STM32 (GĐ2) | `embedded/` | mọi thư mục khác |
| A5 — ESP32-CAM (GĐ2–3) | `esp32-cam/` | mọi thư mục khác |
| A6 — QA & Tài liệu | `docs/reports/`, file test | không sửa code nghiệp vụ, chỉ báo lỗi |

## Quy tắc
- Giữ nguyên tên hàm và chữ ký đã có trong file khung. Muốn đổi: DỪNG, ghi đề xuất vào `DECISIONS_LOG.md` mục "Đề xuất đổi contract", chờ chủ dự án duyệt, rồi mới cập nhật `API_CONTRACT.md` hoặc `DB_SCHEMA.md` trong cùng lần commit.
- Không tự đổi công nghệ đã chốt, không huấn luyện lại model, không làm xác thực bằng giọng nói. Loa thông báo (B14) là ngoại lệ đã chốt: chỉ đọc thông báo ra, bằng giọng tiếng Việt, mạch lạc.
- Commit sau mỗi hàm hoàn chỉnh bằng `python scripts/agent_commit.py A<số> "[module] mô tả ngắn - A<số>"`. Không dùng `git add -A` (sẽ commit nhầm code dở của Agent khác).
- Phiên bị ngắt: đọc `git status` và dòng cuối `PROGRESS_LOG.md`, làm tiếp, không viết lại từ đầu.
- Xong việc: cập nhật `PROGRESS_LOG.md`, ghi quyết định mới vào `DECISIONS_LOG.md`, viết báo cáo tiến độ và bản tường trình (giải thích code, câu hỏi hội đồng có thể hỏi) vào `docs/reports/`.

## BÁO CÁO THEO CHECKPOINT (bắt buộc)
Mỗi việc (B1, B2...) có checklist trong `docs/reports/<ID>.md` và mô tả trong `docs/plan/MO_TA_CONG_VIEC.md`. Không viết báo cáo dồn về cuối.
1. Làm đúng một checkpoint (một bảng, một nhóm cột, một hàm, một route hoặc một component).
2. Tự kiểm tra tối thiểu.
3. Ghi nhật ký NGAY, trước khi commit: `python scripts/log_checkpoint.py <ID> CP-xx --file <file> --auto --did "..." --why "..." --check "..." --todo "..."` (tự ghi số dòng, tick checklist, thêm vào PROGRESS_LOG).
4. `python scripts/agent_commit.py A<số> "[<ID>] CP-xx mô tả - A<số>"`, rồi mới làm checkpoint kế.
5. Sắp hết token: `python scripts/log_checkpoint.py <ID> --handoff --note "đang dở gì, file, dòng, bước kế"`.
Prompt mẫu: `docs/prompts/<ID>.md`. Tiếp tục việc dở: `docs/prompts/00_PROMPT_CHUNG.md`.

## CHẠY SONG SONG (nhiều Agent cùng lúc)
Mỗi Agent làm trong một git worktree và nhánh riêng (`../wt-ai` = A1, `../wt-be` = A2, `../wt-fe` = A3), tạo bằng `scripts/setup_worktrees.ps1` (hoặc `.sh`). Hướng dẫn đầy đủ: `docs/plan/CHAY_SONG_SONG.md`.
- Chỉ commit bằng `scripts/agent_commit.py`; script chỉ add thư mục được phép ở bảng trên cộng `docs/reports/`, `docs/context/`.
- Cần phần của Agent khác mà chưa xong: dùng stub/mock theo `API_CONTRACT.md`, ghi TODO, không viết hộ.
- Đổi contract phải được chủ dự án duyệt (xem Quy tắc). Chủ dự án là người merge các nhánh.
