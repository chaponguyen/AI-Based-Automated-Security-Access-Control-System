# API CONTRACT. Chủ sở hữu: Agent 2. Agent 3 và các Agent khác đọc theo.

| Method | Đường dẫn | Vào | Ra |
|---|---|---|---|
| POST | `/api/auth/login` | `{username, password}` | 200 `{id, username, full_name, role}` kèm cookie `session` (HttpOnly, SameSite=Lax); 401 `{"reason": "invalid_credentials"}`; 423 `{"reason": "locked", "retry_after_s": n}` |
| POST | `/api/auth/logout` | — | 200 `{"ok": true}` (thu hồi phiên, xóa cookie) |
| GET | `/api/auth/me` | — | 200 `{id, username, full_name, role}` hoặc 401 `{"reason": "not_authenticated"}` |
| POST | `/api/residents` | multipart: `full_name`, `age`, `apartment_number` (yêu cầu role `manager`) | 201 `{id, user_code, frames_kept}`; 422 `{reason: "not_enough_quality_frames", good: n, required: 15}`; 409 `{reason: "registration_in_progress"}` hoặc 409 `{reason: "already_registered", user: {...}, similarity: x}`; 403 `{"reason": "forbidden"}` nếu role `security` |
| GET | `/api/registration/precheck` | — (khung camera hiện tại) | `{"state": "no_face"|"multiple_faces"|"low_quality"|"new"|"exists", "exists": bool, "user": {...}|null, "similarity": float|null, "box": [x1,y1,x2,y2]|null}` |
| GET | `/api/residents` | — | `[{id, user_code, full_name, age, apartment_number, status, frames}]` |
| PATCH | `/api/residents/{id}/status` | `{status: "active"|"inactive"}` (yêu cầu role `manager`) | cư dân đã cập nhật; 403 `{"reason": "forbidden"}` nếu role `security` |
| POST | `/api/verify` | multipart: `image` | `{user, similarity, liveness, decision, reason, box, crop_b64}` |
| GET | `/api/logs` | `?decision=&q=&from=&to=` | `[{id, timestamp, name, similarity, liveness, decision, reason}]` (mỗi dòng có thêm trường `id`) |
| POST | `/api/logs/delete` | `{ids?: [số], from?: ISO, to?: ISO}` (yêu cầu role `manager`) | 200 `{"deleted": n}`; 422 nếu thiếu cả hai |
| GET | `/api/staff` | — (yêu cầu role `manager`) | `[{id, username, full_name, role, is_active, last_login_at, created_at}]` |
| POST | `/api/staff` | `{username, full_name, password, role}` (yêu cầu role `manager`) | 201 `{id, username, full_name, role, is_active, last_login_at, created_at}`; 409 `{"reason": "username_taken"}`; 422 |
| PATCH | `/api/staff/{id}` | `{full_name?, role?, is_active?, password?}` (yêu cầu role `manager`) | 200 bản ghi mới; 409 `{"reason": "last_manager"\|"self_protected"}`; 404 |
| DELETE | `/api/staff/{id}` | — (yêu cầu role `manager`) | 200 `{"ok": true}`; 409 `{"reason": "last_manager"\|"self_protected"}`; 404 |
| DELETE | `/api/residents/{id}` | — (yêu cầu role `manager`) | 200 `{"ok": true, "deleted": {id, user_code, full_name}}`; 404 |
| GET | `/api/audit` | `?limit=&action=&q=&from=&to=` (yêu cầu role `manager`) | `[{id, timestamp, staff_username, action, target_type, target_id, detail}]` (mới nhất trước, limit mặc định 200, tối đa 1000; `from`/`to` lọc theo khoảng thời gian) |
| POST | `/api/door/open` | `{reason?: string}` (mọi staff) | 200 `{"state": "open", "open_seconds": 10, "until": ISO8601+tz, "remaining_seconds": float, "already_open": bool}` |
| GET | `/api/door/status` | — (mọi staff) | `{"state": "closed"\|"open", "until": ISO8601+tz\|null, "remaining_seconds": float, "by": str\|null}` |
| GET | `/api/health` | — (công khai) | `{status: "ok"}` |
| GET | `/api/camera/status` | — | `{running, fps, width, height, viewers}` |
| GET | `/api/stream` | — | MJPEG `multipart/x-mixed-replace; boundary=frame` (chỉ mã hóa khi có người xem) |
| GET | `/api/stream/snapshot` | — | 1 ảnh JPEG của khung mới nhất |
| POST | `/api/speaker/test` | `{text}` | `{ok: bool}` |
| POST | `/api/speaker/mute` | `{muted: bool}` | `{muted: bool}` |
| GET | `/api/speaker/status` | — | `{enabled, muted, voice, queue}` |
| WS | `/ws/dashboard` | — (kiểm tra cookie session trước khi accept, sai đóng với mã 1008) | `{event: "access_result"|"door_state"|"camera_status"|"ai_status"|"record_progress", data: {...}}` |

`reason` dùng mã cố định: `ok`, `not_matched`, `spoof_detected`, `inactive_user`, `no_face`, `multiple_faces`, `low_quality`.

`access_result.data` = `{user, decision, reason, similarity, box, timestamp, announcement: {display, spoken, kind}}` (`kind`: `granted` | `stranger` | `inactive`).
`door_state.data` = `{"state": "open"|"closed", "until": ISO8601+tz|null, "open_seconds": int, "remaining_seconds": float, "by": str|null, "reason": str|null}` (gửi trạng thái hiện tại ngay khi WS kết nối; `until` luôn có múi giờ dạng `+00:00`; `remaining_seconds` = 0 khi cửa đóng).
`record_progress.data` = `{t_ms, got, kept}`. `ai_status.data` = `{running, fps, tracking, last_event_at}`.

## Quy ước thời gian (B16 sửa múi giờ, 2026-10-30)

- **Mọi giá trị thời gian trả ra API là chuỗi ISO 8601 CÓ offset** (`+07:00` hoặc `+00:00`), không bao giờ là datetime naive. Áp dụng cho: `GET /api/logs` (`timestamp`), `GET /api/audit` (`timestamp`), `GET /api/staff` và `POST/PATCH /api/staff` (`created_at`, `last_login_at`), `GET /api/door/status` + `POST /api/door/open` (`until`), WS `access_result.data.timestamp`, WS `ai_status.data.last_event_at`, WS `door_state.data.until`.
- `last_login_at`, `audit_logs.timestamp`, `staff_sessions.*` mang offset `+00:00` (lưu UTC). `access_logs.timestamp`, `staff_accounts.created_at` mang offset thực tế của PostgreSQL (`+07:00` trên máy hiện tại). Chi tiết từng cột: `DB_SCHEMA.md`.
- `ai_status.data.last_event_at` là epoch giây đổi sang ISO 8601 UTC (`+00:00`), `null` nếu chưa có sự kiện.
- **Bộ lọc `from`/`to`** (có ở `GET /api/logs`, `POST /api/logs/delete`, `GET /api/audit`):
  - Chuỗi có offset (`2026-10-30T00:00:00+07:00`, `...Z`): tôn trọng đúng offset đó.
  - Chuỗi KHÔNG có offset (`2026-10-30T00:00:00`): được hiểu là **giờ Việt Nam (UTC+7)**.
  - Backend tự đổi sang quy ước lưu của chính bảng đang lọc trước khi so sánh (access_logs: DB_LOCAL; audit_logs: UTC), nên lọc "ngày hôm nay giờ Việt Nam" cho kết quả đúng trên cả hai bảng.
  - `from` > `to` trả **422** `{"detail": "Tham số 'from' phải nhỏ hơn hoặc bằng 'to'."}`; chuỗi sai định dạng trả **400**.


## Bảo mật và Phân quyền (B15 - B16)
- **Công khai:** chỉ `POST /api/auth/login` và `GET /api/health`.
- **Yêu cầu đăng nhập (`require_staff`):** Mọi route còn lại (kể cả stream MJPEG, camera status, speaker, logs, verify, door) và WebSocket dashboard. Thiếu hoặc phiên hết hạn trả 401 `{"reason": "not_authenticated"}`.
- **Phân quyền vai trò:**
  - `manager`: Đầy đủ quyền quản trị: thêm/xóa cư dân (`POST /api/residents`, `DELETE /api/residents/{id}`), đổi trạng thái cư dân (`PATCH /api/residents/{id}/status`), quản lý nhân viên (`/api/staff`), xóa nhật ký (`POST /api/logs/delete`), xem nhật ký kiểm toán (`GET /api/audit`), điều khiển cửa.
  - `security`: Xem camera stream, xem danh sách cư dân, xem nhật ký ra vào, thao tác loa, điều khiển mở cửa (`POST /api/door/open`, `GET /api/door/status`). Khi gọi các route chỉ dành cho manager bị chặn với 403 `{"reason": "forbidden"}`.

## MQTT (giai đoạn 2)
| Topic | Bên gửi | Payload |
|---|---|---|
| `door/access/decision` | Backend | `{"decision": "granted"}` hoặc `{"decision": "denied"}` |
| `door/status` | STM32 qua ESP32 | `{"lock": "locked"\|"unlocked", "door": "closed"\|"open"}` |
