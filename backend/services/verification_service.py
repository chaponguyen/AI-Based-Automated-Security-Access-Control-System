# Agent 2 — Xác thực và quyết định cấp quyền ra vào (B6 CP-03)
import time
import base64
import logging
from typing import Optional, Dict, Any, List
import cv2
import numpy as np

from ai.config import LIVENESS_MIN
try:
    from ai.config import SIM_THRESHOLD
except ImportError:
    from ai.matcher import SIM_THRESHOLD

from ai.aligner import crop_face, tight_box
from ai.anti_spoof import check_liveness
from ai.embedder import get_embedding
from ai.matcher import best_match
from services.decision import decide
from services import gallery_cache
from database.models import AccessLog


logger = logging.getLogger(__name__)


def record_access(db, result: dict) -> Optional[AccessLog]:
    """Ghi một dòng vào bảng access_logs cho mỗi quyết định thật (granted hoặc denied).

    CP-04:
    - KHÔNG ghi log khi reason == 'no_face' (không có khuôn mặt, tránh làm rác CSDL).
    - user_id lấy từ result['user']['id'] nếu nhận diện được cư dân, ngược lại là None.
    - Dùng chung cho cả endpoint POST /api/verify và luồng tự động xác thực B12.

    Args:
        db: SQLAlchemy session
        result: dict kết quả trả về từ verify_face hoặc verify_image

    Returns:
        AccessLog đã lưu vào CSDL, hoặc None nếu là lượt không có mặt (no_face)
    """
    if not result or result.get("reason") == "no_face":
        return None

    user = result.get("user")
    user_id = None
    if user:
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)

    similarity = result.get("similarity")
    if similarity is not None:
        similarity = float(similarity)

    liveness = result.get("liveness")
    if liveness is not None:
        liveness = bool(liveness)

    decision = result.get("decision")
    reason = result.get("reason")

    log_entry = AccessLog(
        user_id=user_id,
        similarity=similarity,
        liveness=liveness,
        decision=decision,
        reason=reason,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def verify_face(db, image_bgr: np.ndarray, face: dict) -> dict:
    """Xác thực một khuôn mặt đơn lẻ từ ảnh và thông tin phát hiện.

    CP-03:
    1. check_liveness (một khung) trước: nếu giả mạo -> bỏ qua crop và embedding để tiết kiệm tài nguyên.
    2. crop_face: cắt vùng chuẩn 112x112 theo 5 landmark.
    3. get_embedding: trích xuất vector đặc trưng 512 chiều.
    4. best_match: so khớp với gallery trong bộ nhớ RAM.
    5. decide: đưa ra quyết định granted/denied.
    Đo thời gian (ms) chi tiết từng bước.
    """
    ms_details: Dict[str, float] = {}

    # Bước 1: Kiểm tra chống giả mạo (Liveness check)
    t_live = time.perf_counter()
    is_real, live_score = check_liveness(image_bgr, face.get("bbox"))
    ms_live = round((time.perf_counter() - t_live) * 1000, 2)
    ms_details["liveness"] = ms_live

    # Tính khung hiển thị tight_box từ 5 landmark
    kps = face.get("kps")
    box = tight_box(kps) if kps is not None else face.get("bbox", [0, 0, 0, 0])

    crop_b64: Optional[str] = None
    aligned: Optional[np.ndarray] = None

    if not is_real:
        # Nếu giả mạo: bỏ qua embedding và so khớp cho nhanh
        user = None
        similarity = 0.0
        decision, reason = decide(
            similarity=0.0,
            liveness=False,
            user=None,
            threshold=SIM_THRESHOLD,
        )
        ms_details["crop"] = 0.0
        ms_details["embedding"] = 0.0
        ms_details["match"] = 0.0
        ms_details["total"] = ms_live

        # Vẫn tạo crop_b64 để UI hiển thị khuôn mặt bị từ chối
        try:
            if kps is not None:
                aligned = crop_face(image_bgr, kps)
                ret, buf = cv2.imencode(".jpg", aligned, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    crop_b64 = base64.b64encode(buf).decode("utf-8")
        except Exception as e:
            logger.debug("Lỗi tạo crop_b64 cho khuôn mặt giả: %s", e)
    else:
        # Bước 2: Cắt mặt chuẩn 112x112
        t_crop = time.perf_counter()
        aligned = crop_face(image_bgr, kps)
        ms_crop = round((time.perf_counter() - t_crop) * 1000, 2)
        ms_details["crop"] = ms_crop

        # Mã hóa crop_b64 cho UI
        try:
            ret, buf = cv2.imencode(".jpg", aligned, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                crop_b64 = base64.b64encode(buf).decode("utf-8")
        except Exception as e:
            logger.debug("Lỗi tạo crop_b64: %s", e)

        # Bước 3: Trích xuất embedding 512-dim
        t_emb = time.perf_counter()
        emb = get_embedding(aligned)
        ms_emb = round((time.perf_counter() - t_emb) * 1000, 2)
        ms_details["embedding"] = ms_emb

        # Bước 4: So khớp với GalleryCache
        t_match = time.perf_counter()
        gallery = gallery_cache.get_gallery()
        matched_user_id, similarity = best_match(emb, gallery)
        ms_match = round((time.perf_counter() - t_match) * 1000, 2)
        ms_details["match"] = ms_match

        # Bước 5: Quyết định cấp quyền hay từ chối
        user = gallery_cache.get_user(matched_user_id) if matched_user_id is not None else None
        decision, reason = decide(
            similarity=similarity,
            liveness=True,
            user=user,
            threshold=SIM_THRESHOLD,
        )

        ms_total = round(ms_live + ms_crop + ms_emb + ms_match, 2)
        ms_details["total"] = ms_total

    return {
        "user": user.to_dict() if user is not None else None,
        "similarity": round(float(similarity), 4),
        "liveness": bool(is_real),
        "decision": decision,
        "reason": reason,
        "box": [int(v) for v in box],
        "crop_b64": crop_b64,
        "ms": ms_details,
    }


def verify_image(db, image_bgr: np.ndarray) -> dict:
    """Xác thực từ một ảnh BGR đầy đủ.

    - Phát hiện các khuôn mặt trong ảnh.
    - Xử lý mặt lớn nhất (primary face) bằng verify_face.
    - Trả về thêm số lượng mặt phát hiện được (`faces`).
    - Biên: Nếu không có mặt nào, trả decision="denied", reason="no_face" và KHÔNG ghi log.
    """
    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0:
        return {
            "user": None,
            "similarity": 0.0,
            "liveness": False,
            "decision": "denied",
            "reason": "no_face",
            "box": None,
            "crop_b64": None,
            "faces": 0,
            "ms": {"detect": 0.0, "total": 0.0},
        }

    t_detect = time.perf_counter()
    from ai.detector import detect_faces
    faces = detect_faces(image_bgr)
    detect_ms = round((time.perf_counter() - t_detect) * 1000, 2)

    # Không có khuôn mặt nào -> trả denied/no_face và không ghi log
    if not faces:
        return {
            "user": None,
            "similarity": 0.0,
            "liveness": False,
            "decision": "denied",
            "reason": "no_face",
            "box": None,
            "crop_b64": None,
            "faces": 0,
            "ms": {"detect": detect_ms, "total": detect_ms},
        }

    # Lấy mặt lớn nhất (detect_faces đã sắp xếp diện tích giảm dần)
    primary_face = faces[0]
    result = verify_face(db, image_bgr, primary_face)
    result["faces"] = len(faces)
    result["ms"]["detect"] = detect_ms
    result["ms"]["total"] = round(result["ms"].get("total", 0.0) + detect_ms, 2)
    return result
