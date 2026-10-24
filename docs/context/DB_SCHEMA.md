# DB SCHEMA (PostgreSQL). Chủ sở hữu: Agent 2

| Bảng | Cột |
|---|---|
| `users` | `id` PK · `full_name` · `age` · `apartment_number` · `status` ('active'/'inactive') · `created_at` |
| `face_embeddings` | `id` PK · `user_id` FK (xóa user thì xóa theo) · `embedding` FLOAT[512] chuẩn hóa L2 · `quality` · `model_version` · `created_at` |
| `access_logs` | `id` PK · `user_id` FK (NULL nếu không xác định, ON DELETE SET NULL) · `similarity` · `liveness` · `decision` ('granted'/'denied') · `reason` · `timestamp` |

- `user_code` dạng `USR000001` được tính từ `id` khi hiển thị, không lưu cột riêng.
- Một người có 15 đến 20 dòng `face_embeddings` (từ đoạn quay 3 giây).
- Một căn hộ có thể có nhiều người nên `apartment_number` không phải khóa.
- Chỉ lưu embedding, không lưu ảnh gốc.
