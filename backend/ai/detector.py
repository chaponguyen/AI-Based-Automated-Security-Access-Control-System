# Agent 1 (AI) — phát hiện mặt bằng SCRFD trong InsightFace buffalo_sc
import threading

import numpy as np

from .config import DET_SCORE_MIN, DET_SIZE

_app = None
_lock = threading.Lock()


def get_app():
    """Nạp FaceAnalysis một lần cho cả tiến trình, các lần sau dùng lại."""
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                from insightface.app import FaceAnalysis

                app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
                app.prepare(ctx_id=-1, det_size=DET_SIZE)
                _app = app
    return _app


def detect_faces(image_bgr):
    """Trả về list[dict(bbox, kps, score)]; kps là 5 landmark (mắt, mũi, 2 khóe miệng).

    bbox = [x1, y1, x2, y2] theo pixel; kps = 5 cặp [x, y]; score là độ tin cậy.
    Danh sách sắp theo diện tích bbox giảm dần. Ảnh không hợp lệ trả [].
    """
    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        return []
    if image_bgr.size == 0 or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return []

    bboxes, kpss = get_app().det_model.detect(image_bgr, max_num=0, metric="default")
    if bboxes is None or len(bboxes) == 0 or kpss is None:
        return []

    faces = []
    for bbox, kps in zip(bboxes, kpss):
        score = float(bbox[4])
        if score < DET_SCORE_MIN:
            continue
        x1, y1, x2, y2 = (float(v) for v in bbox[:4])
        faces.append({
            "bbox": [x1, y1, x2, y2],
            "kps": [[float(x), float(y)] for x, y in np.asarray(kps).reshape(5, 2)],
            "score": score,
        })
    faces.sort(key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]),
               reverse=True)
    return faces
