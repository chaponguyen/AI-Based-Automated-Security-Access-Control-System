import logging
import threading

from typing import List, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)

# Agent 2 — thêm cư dân PHẢI kèm khuôn mặt, lưu trong một transaction
# Hằng số cấu hình riêng theo quy định, không viết cứng trong mã xử lý
MIN_GOOD_FRAMES = 15   # ít hơn thì từ chối, không tạo cư dân
MAX_KEEP = 20          # giữ tối đa 20 khung tốt nhất
MODEL_VERSION = "buffalo_sc"

# Khóa luồng đảm bảo chỉ có tối đa một phiên đăng ký cư dân diễn ra tại một thời điểm
registration_lock = threading.Lock()


class NotEnoughQualityFramesError(Exception):
    """Ném ra khi số khung hình đạt chuẩn nhỏ hơn ngưỡng tối thiểu MIN_GOOD_FRAMES."""

    def __init__(self, good: int, required: int = MIN_GOOD_FRAMES):
        self.good = good
        self.required = required
        super().__init__(f"Chỉ thu được {good}/{required} khung hình đạt chất lượng.")


def reload_gallery_cache(db=None):
    """Nạp lại bộ nhớ cache gallery sau khi có cư dân mới.

    TODO(B6): GalleryCache do Agent A2 phụ trách triển khai ở B6.
    Hiện tại B6 chưa hoàn tất nên kiểm tra và bỏ qua an toàn, ghi nhận log TODO.
    """
    try:
        from services import gallery_cache
        if hasattr(gallery_cache, "reload"):
            gallery_cache.reload(db)
        elif hasattr(gallery_cache, "init_cache"):
            gallery_cache.init_cache(db)
    except Exception as err:
        logger.debug("GalleryCache chưa sẵn sàng (B6), bỏ qua nạp cache: %s", err)



def record_registration_frames(camera: Optional[Any] = None) -> List[np.ndarray]:
    """Quay 3 giây từ camera backend, tạm dừng AI và phát tiến độ qua WebSocket.

    CP-02:
    - Bật cờ ai_control.pause_ai().
    - Gọi camera.record(3.0, on_tick).
    - Mỗi tick tính nhanh detect_faces + frame_quality cho khung đó và phát record_progress {t_ms, got, kept} qua WebSocket broadcast.
    - Luôn tắt cờ ai_control.resume_ai() trong finally kể cả khi lỗi.
    """
    if camera is None:
        from services.camera_service import get_camera
        camera = get_camera()

    from services.ai_control import pause_ai, resume_ai
    from api.ws import broadcast
    from ai.detector import detect_faces
    from ai.quality import frame_quality

    pause_ai()
    kept_count = 0
    try:
        def on_tick(t_ms: int, got: int, frame: Optional[np.ndarray] = None):
            nonlocal kept_count
            if frame is not None:
                try:
                    faces = detect_faces(frame)
                    q = frame_quality(frame, faces, allow_multiple=False)
                    if q.get("ok"):
                        kept_count += 1
                except Exception as err:
                    logger.debug("Lỗi tính nhanh chất lượng khung tại tick %d ms: %s", t_ms, err)

            broadcast("record_progress", {
                "t_ms": t_ms,
                "got": got,
                "kept": kept_count,
            })

        frames = camera.record(3.0, on_tick=on_tick)
        return frames
    finally:
        resume_ai()


def filter_and_select_frames(
    frames: List[np.ndarray],
    min_good: int = MIN_GOOD_FRAMES,
    max_keep: int = MAX_KEEP,
) -> List[dict]:
    """Lọc các khung hình đạt chuẩn và chọn tối đa max_keep khung có chất lượng tốt nhất.

    CP-03:
    - Mỗi khung phải có đúng 1 mặt từ detect_faces(f) và frame_quality.ok is True.
    - Cần tối thiểu min_good (15) khung đạt; ít hơn ném NotEnoughQualityFramesError(good, min_good).
    - Giữ tối đa max_keep (20) khung có điểm score cao nhất (sắp xếp giảm dần).
    - Trả về danh sách các dict: {"frame": ndarray, "face": dict, "score": float}.
    """
    from ai.detector import detect_faces
    from ai.quality import frame_quality

    good_items = []
    for f in frames:
        if f is None or not isinstance(f, np.ndarray) or f.size == 0:
            continue
        try:
            faces = detect_faces(f)
            q = frame_quality(f, faces, allow_multiple=False)
            if q.get("ok"):
                good_items.append({
                    "frame": f,
                    "face": faces[0],
                    "score": float(q.get("score", 0.0)),
                })
        except Exception as e:
            logger.debug("Lỗi khi đánh giá chất lượng khung: %s", e)

    good_count = len(good_items)
    if good_count < min_good:
        raise NotEnoughQualityFramesError(good=good_count, required=min_good)

    # Sắp xếp các khung đạt chuẩn theo điểm chất lượng giảm dần
    good_items.sort(key=lambda item: item["score"], reverse=True)
    return good_items[:max_keep]


def register_resident(db, info, frames, _fail_at_embedding: Optional[int] = None):
    """info: full_name, age, apartment_number. frames: ảnh quay trong 3 giây.

    CP-03, CP-04:
    - Lọc chất lượng -> chọn tối đa MAX_KEEP=20 khung tốt nhất (tối thiểu MIN_GOOD_FRAMES=15).
    - Tạo embedding (ArcFace 512-dim đã chuẩn hóa L2) cho từng khung đã chọn.
    - Lưu trong MỘT transaction duy nhất: thêm User, flush() lấy id, thêm các FaceEmbedding (kèm quality, model_version), commit().
    - Nếu gặp lỗi: rollback toàn bộ transaction để không tạo User mồ côi.
    - Sau khi lưu thành công: nạp lại bộ nhớ gallery (reload_gallery_cache).
    - Trả về dict: {"id": user.id, "user_code": user.user_code, "frames_kept": len(embeddings), "user": user}.
    """
    from ai.aligner import crop_face
    from ai.embedder import get_embedding
    from database.models import User, FaceEmbedding

    # 1. Lọc và chọn khung hình đạt chuẩn
    selected_frames = filter_and_select_frames(frames, min_good=MIN_GOOD_FRAMES, max_keep=MAX_KEEP)

    # 2. Trích xuất thông tin cư dân
    if isinstance(info, dict):
        full_name = str(info.get("full_name", "")).strip()
        age = int(info.get("age", 0))
        apartment_number = str(info.get("apartment_number", "")).strip()
    else:
        full_name = str(getattr(info, "full_name", "")).strip()
        age = int(getattr(info, "age", 0))
        apartment_number = str(getattr(info, "apartment_number", "")).strip()

    # 3. Tạo embeddings cho các khung hình được chọn
    embedding_records = []
    for item in selected_frames:
        aligned = crop_face(item["frame"], item["face"]["kps"])
        emb = get_embedding(aligned)
        if emb is not None:
            embedding_records.append((emb.tolist(), item["score"]))

    if len(embedding_records) < MIN_GOOD_FRAMES:
        raise NotEnoughQualityFramesError(good=len(embedding_records), required=MIN_GOOD_FRAMES)

    # Nếu không có db (chạy test thuần không CSDL), trả về thông tin tính toán
    if db is None:
        return {
            "id": 0,
            "user_code": "USR000000",
            "frames_kept": len(embedding_records),
            "user": None,
        }

    # 4. Lưu trong MỘT Transaction duy nhất
    try:
        user = User(
            full_name=full_name,
            age=age,
            apartment_number=apartment_number,
            status="active",
        )
        db.add(user)
        db.flush()  # Sinh user.id tự tăng để liên kết foreign key

        for idx, (emb_vec, quality) in enumerate(embedding_records):
            if _fail_at_embedding is not None and (idx + 1) == _fail_at_embedding:
                raise RuntimeError(f"Giả lập lỗi tại embedding thứ {_fail_at_embedding} để kiểm thử rollback")

            face_emb = FaceEmbedding(
                user_id=user.id,
                embedding=emb_vec,
                quality=quality,
                model_version=MODEL_VERSION,
            )
            db.add(face_emb)

        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("Lỗi khi lưu cư dân và embedding vào CSDL, đã rollback: %s", e)
        raise e

    # 5. Sau khi lưu thành công: gọi hàm đệm nạp lại gallery cache (TODO B6)
    reload_gallery_cache(db)

    return {
        "id": user.id,
        "user_code": user.user_code,
        "frames_kept": len(embedding_records),
        "user": user,
    }



