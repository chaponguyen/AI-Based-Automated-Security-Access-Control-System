# API CONTRACT. Chủ sở hữu: Agent 2. Agent 3 và các Agent khác đọc theo.

| Method | Đường dẫn | Vào | Ra |
|---|---|---|---|
| POST | `/api/residents` | multipart: `full_name`, `age`, `apartment_number` (backend tự quay 3 giây từ camera, không nhận khung hình) | 201 `{id, user_code, frames_kept}`; 422 `{reason: "not_enough_quality_frames", good: n, required: 15}`; 409 `{reason: "registration_in_progress"}` hoặc 409 `{reason: "already_registered", user: {...}, similarity: x}` |
| GET | `/api/registration/precheck` | — (khung camera hiện tại) | `{"state": "no_face"\|"multiple_faces"\|"low_quality"\|"new"\|"exists", "exists": bool, "user": {...}\|null, "similarity": float\|null, "box": [x1,y1,x2,y2]\|null}` |
| GET | `/api/residents` | — | `[{id, user_code, full_name, age, apartment_number, status, frames}]` |
| PATCH | `/api/residents/{id}/status` | `{status: "active"\|"inactive"}` | cư dân đã cập nhật |
| POST | `/api/verify` | multipart: `image` | `{user, similarity, liveness, decision, reason, box, crop_b64}` |
| GET | `/api/logs` | `?decision=&q=&from=&to=` | `[{timestamp, name, similarity, liveness, decision, reason}]` |
| GET | `/api/health` | — | `{status: "ok"}` |
| GET | `/api/camera/status` | — | `{running, fps, width, height, viewers}` |
| GET | `/api/stream` | — | MJPEG `multipart/x-mixed-replace; boundary=frame` (chỉ mã hóa khi có người xem) |
| GET | `/api/stream/snapshot` | — | 1 ảnh JPEG của khung mới nhất |
| POST | `/api/speaker/test` | `{text}` | `{ok: bool}` |
| POST | `/api/speaker/mute` | `{muted: bool}` | `{muted: bool}` |
| GET | `/api/speaker/status` | — | `{enabled, muted, voice, queue}` |
| WS | `/ws/dashboard` | — | `{event: "access_result"\|"door_state"\|"camera_status"\|"ai_status"\|"record_progress", data: {...}}` |

`reason` dùng mã cố định: `ok`, `not_matched`, `spoof_detected`, `inactive_user`, `no_face`, `multiple_faces`, `low_quality`.

`access_result.data` = `{user, decision, reason, similarity, box, timestamp, announcement: {display, spoken, kind}}` (`kind`: `granted` | `stranger` | `inactive`).
`record_progress.data` = `{t_ms, got, kept}`. `ai_status.data` = `{running, fps, tracking, last_event_at}`.

## MQTT (giai đoạn 2)
| Topic | Bên gửi | Payload |
|---|---|---|
| `door/access/decision` | Backend | `{"decision": "granted"}` hoặc `{"decision": "denied"}` |
| `door/status` | STM32 qua ESP32 | `{"lock": "locked"\|"unlocked", "door": "closed"\|"open"}` |
