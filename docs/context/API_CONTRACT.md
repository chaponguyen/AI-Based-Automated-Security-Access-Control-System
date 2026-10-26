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
| GET | `/api/logs` | `?decision=&q=&from=&to=` | `[{timestamp, name, similarity, liveness, decision, reason}]` |
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
`record_progress.data` = `{t_ms, got, kept}`. `ai_status.data` = `{running, fps, tracking, last_event_at}`.

## Bảo mật và Phân quyền (B15)
- **Công khai:** chỉ `POST /api/auth/login` và `GET /api/health`.
- **Yêu cầu đăng nhập (`require_staff`):** Mọi route còn lại (kể cả stream MJPEG, camera status, speaker, logs, verify) và WebSocket dashboard. Thiếu hoặc phiên hết hạn trả 401 `{"reason": "not_authenticated"}`.
- **Phân quyền vai trò:**
  - `manager`: Đầy đủ quyền, bao gồm thêm cư dân (`POST /api/residents`) và đổi trạng thái (`PATCH /api/residents/{id}/status`).
  - `security`: Xem camera stream, xem danh sách cư dân, xem nhật ký, thao tác loa. Khi gọi POST residents hoặc PATCH status trả 403 `{"reason": "forbidden"}`.

## MQTT (giai đoạn 2)
| Topic | Bên gửi | Payload |
|---|---|---|
| `door/access/decision` | Backend | `{"decision": "granted"}` hoặc `{"decision": "denied"}` |
| `door/status` | STM32 qua ESP32 | `{"lock": "locked"\|"unlocked", "door": "closed"\|"open"}` |
