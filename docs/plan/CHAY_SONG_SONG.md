# Chạy song song AI, Backend, Frontend

## 1. Chuẩn bị (làm một lần)
1. Làm xong P0 trong `PHAN_CHIA_CONG_VIEC.md` (venv, PostgreSQL, model, ảnh test).
2. Đọc và xác nhận `docs/context/API_CONTRACT.md`. Đây là hợp đồng giữa 3 Agent, B8 (Frontend) dựa vào nó để làm trước với dữ liệu giả.
3. Tạo repo: `git init`, `git add -A`, `git commit -m "init"`. Kiểm tra `backend/.env` không bị commit.
4. Tạo worktree: `powershell -File scripts\setup_worktrees.ps1` (Windows) hoặc `bash scripts/setup_worktrees.sh`.
   Script tạo `../wt-ai` (nhánh `agent/a1-ai`), `../wt-be` (`agent/a2-be`), `../wt-fe` (`agent/a3-fe`) và copy `.env`, `weights/`, `test_data/` (các thư mục này bị gitignore).
5. `cd ../wt-fe/frontend` rồi `npm install`. Venv Python dùng chung: kích hoạt `venv` ở thư mục gốc.

## 2. Đợt 1: chạy cùng lúc

| Công cụ | Mở ở thư mục | Dán prompt | Ghi chú |
|---|---|---|---|
| A1 AI Engine | `../wt-ai` | `docs/prompts/B2.md` | cần `weights/` và `test_data/` |
| A2 Backend | `../wt-be` | `docs/prompts/B1.md`, xong thì `B11.md` | cần `backend/.env` |
| A3 Frontend | `../wt-fe` | `docs/prompts/B8.md` | dùng mock, chưa cần backend thật |

Mỗi lần chỉ giao một ID cho mỗi Agent. Phiên bị ngắt: dùng prompt "Tiếp tục việc dở" trong `docs/prompts/00_PROMPT_CHUNG.md`.

## 3. Sau mỗi đợt (bạn làm)
1. Đọc báo cáo trong `docs/reports/<ID>.md`, tự giải thích lại được (việc D2).
2. Merge từng nhánh vào nhánh chính, ở thư mục gốc:
   ```
   git merge agent/a1-ai
   git merge agent/a2-be
   git merge agent/a3-fe
   ```
   Thư mục tách biệt nên hiếm khi conflict. Nếu `PROGRESS_LOG.md` hoặc `DECISIONS_LOG.md` conflict thì giữ cả hai bên.
3. Chạy các lệnh Agent không được tự chạy (ví dụ `alembic upgrade head` sau B1) và kiểm tra tay.
4. Cho các nhánh lấy bản mới: trong mỗi worktree chạy `git merge main` (hoặc tên nhánh chính của bạn).
5. Giao A6 kiểm tra chéo bằng prompt trong `00_PROMPT_CHUNG.md`, rồi sang đợt kế.

## 4. Thứ tự các đợt
- Đợt 1: B1, B2, B8 (mock); A2 tiếp B11.
- Đợt 2: B3, rồi B4 song song với B5.
- Đợt 3: B6, rồi B12.
- Đợt 4: B7, B13, B14 song song (A2 làm nhiều việc thì giao tuần tự; B14 phần hàm thuần có thể làm sớm).
- Đợt 5: B9 (A3), rồi B10 (A6 và bạn).
Phần cứng H1–H6 (A4, A5) có thể chạy song song với giai đoạn 1, cũng ở worktree riêng.

## 5. Quy tắc khi chạy song song
- Commit qua `python scripts/agent_commit.py A<số> "<message>"`. Script chỉ add thư mục Agent được phép (xem `AGENTS.md`) cộng `docs/reports/`, `docs/context/`.
- Phần của Agent khác chưa có thì dùng stub hoặc mock theo `API_CONTRACT.md`, ghi TODO.
- Đổi hàm, route, schema: Agent dừng lại và ghi vào mục "Đề xuất đổi contract" trong `DECISIONS_LOG.md`; bạn duyệt rồi mới đổi.
- Trước khi giao B5 hoặc B6, mở các file khung trong `backend/ai/` kiểm tra chữ ký hàm đã đủ để A2 gọi.
