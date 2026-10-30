# DB SCHEMA (PostgreSQL). Chủ sở hữu: Agent 2

| Bảng | Cột |
|---|---|
| `users` | `id` PK · `full_name` · `age` · `apartment_number` · `status` ('active'/'inactive') · `created_at` |
| `face_embeddings` | `id` PK · `user_id` FK (xóa user thì xóa theo) · `embedding` FLOAT[512] chuẩn hóa L2 · `quality` · `model_version` · `created_at` |
| `access_logs` | `id` PK · `user_id` FK (NULL nếu không xác định, ON DELETE SET NULL) · `similarity` · `liveness` · `decision` ('granted'/'denied') · `reason` · `timestamp` |
| `staff_accounts` | `id` PK · `username` String(50) duy nhất (chữ thường) · `full_name` String(150) · `password_hash` String(255) · `role` ('security'/'manager') · `is_active` Boolean (mặc định true) · `failed_attempts` Integer (mặc định 0) · `locked_until` DateTime (null) · `created_at` · `last_login_at` DateTime (null) |
| `staff_sessions` | `id` PK · `token_hash` String(64) duy nhất (sha256 của token) · `staff_id` FK (`staff_accounts.id` ON DELETE CASCADE) · `created_at` · `expires_at` · `last_seen_at` |
| `audit_logs` | `id` PK · `staff_id` FK (`staff_accounts.id` ON DELETE SET NULL) · `staff_username` String(50) (chép lại) · `action` String(50) · `target_type` String(30) (null) · `target_id` String(50) (null) · `detail` Text (null) · `timestamp` (index) |

- `user_code` dạng `USR000001` được tính từ `id` khi hiển thị, không lưu cột riêng.
- Một người có 15 đến 20 dòng `face_embeddings` (từ đoạn quay 3 giây).
- Một căn hộ có thể có nhiều người nên `apartment_number` không phải khóa.
- Chỉ lưu embedding, không lưu ảnh gốc.
- `staff_accounts.role` chỉ nhận giá trị `'security'` hoặc `'manager'` (CheckConstraint `ck_staff_accounts_role`).
- `staff_sessions` chỉ lưu `token_hash` (sha256), KHÔNG bao giờ lưu token gốc.
- `audit_logs` ghi nhận vết thao tác quản trị bảo mật (B16 sẽ ghi dữ liệu vào bảng này).

## Quy ước thời gian từng cột (B16 sửa múi giờ, đo thực tế 2026-10-30)

Mọi cột `DateTime` trong CSDL đều là **naive** (không có `tzinfo`). Có HAI quy ước ghi khác nhau, phải biết cột nào thuộc quy ước nào khi đọc/ghi:

| Quy ước | Cột | Ai ghi |
|---|---|---|
| **DB_LOCAL** (giờ máy của PostgreSQL, hiện là UTC+7) | `users.created_at`, `face_embeddings.created_at`, `access_logs.timestamp`, `staff_accounts.created_at` | `server_default=func.now()` của PostgreSQL |
| **UTC** | `audit_logs.timestamp`, `staff_sessions.created_at`, `staff_sessions.expires_at`, `staff_sessions.last_seen_at`, `staff_accounts.last_login_at` | Python `datetime.utcnow()` |

- Offset của PostgreSQL được đọc MỘT LẦN lúc backend khởi động bằng `SELECT extract(timezone from now())` (`backend/services/time_service.py: init_db_offset`), KHÔNG viết cứng `+7`.
- Mọi giá trị thời gian trả ra API phải đi qua `to_api_iso(dt, convention)` để thành ISO 8601 CÓ offset (`+07:00` hoặc `+00:00`).
- Bộ lọc `from`/`to` phải đi qua `parse_filter_dt(s, convention_cua_cot)`: chuỗi có offset thì tôn trọng offset, chuỗi không có offset được coi là giờ Việt Nam (UTC+7).
- **KHÔNG đổi múi giờ của PostgreSQL**: dữ liệu cũ đã lưu theo giờ máy sẽ bị lẫn nghĩa. Nếu buộc phải chuyển DB sang máy khác múi giờ, phải chuyển đổi dữ liệu cột DB_LOCAL trước (xem `DECISIONS_LOG.md`).
- Bảng tra cứu lập trình: `COLUMN_CONVENTION` trong `backend/services/time_service.py`.

