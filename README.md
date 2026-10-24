# AI Security Access Control — Quản lý ra vào chung cư thông minh

Nhận diện khuôn mặt (InsightFace) + chống giả mạo, quản lý cư dân và nhật ký ra vào trên Web.
Giai đoạn 1: chạy trên laptop (camera laptop). Giai đoạn 2: MQTT + STM32 + khóa điện. Giai đoạn 3: ESP32-CAM.

## Chạy nhanh (Windows PowerShell)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cd backend ; copy .env.example .env      # điền DATABASE_URL
alembic upgrade head
uvicorn main:app                          # http://localhost:8000/docs (không dùng --reload: camera và AI chạy ngay khi bật backend)
```
```
cd frontend ; npm install ; npm run dev   # http://localhost:5173
```
Tải model một lần: `python -c "from insightface.app import FaceAnalysis as F; F(name='buffalo_sc').prepare(ctx_id=-1)"`

## Đọc trước khi làm việc
`AGENTS.md` → `docs/context/` → `docs/plan/PHAN_CHIA_CONG_VIEC.md`.
Tính năng thời gian thực: backend giữ camera, tự xác thực khi có người đứng trước camera (không cần mở web), stream xem trực tiếp tùy chọn, loa đọc tiếng Việt thông báo cư dân vào hoặc cảnh báo người lạ (xem B11–B14 trong `docs/plan/MO_TA_CONG_VIEC.md`).
Bản demo giao diện (dữ liệu mô phỏng): `docs/demo/smart-access-demo.html`.

Chạy nhiều Agent song song (AI, Backend, Frontend): xem `docs/plan/CHAY_SONG_SONG.md`.
