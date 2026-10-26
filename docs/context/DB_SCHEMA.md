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

