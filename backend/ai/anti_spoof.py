# Agent 1 (AI) — chống giả mạo khuôn mặt, MiniFASNetV2 (bản ONNX)
# LƯU Ý: model này cần vùng cắt MỞ RỘNG quanh mặt (cấu hình gốc dùng hệ số khoảng 2.7),
# khác với vùng cắt chặt dùng để nhận diện. Kiểm tra lại cấu hình khi tích hợp.
import logging
import os

import cv2
import numpy as np

from .config import (ANTI_SPOOF_MODEL, ANTI_SPOOF_SCALE, ANTI_SPOOF_SIZE,
                     LIVENESS_MIN, LIVENESS_SEQ_MAX_FRAMES,
                     LIVENESS_SEQ_MIN_FRAMES, LIVENESS_SEQ_MOTION_MIN)

logger = logging.getLogger(__name__)

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")
MODEL_PATH = os.path.join(WEIGHTS_DIR, ANTI_SPOOF_MODEL)

_session = None


def _get_session():
    """Nạp model ONNX một lần (CPU) và giữ lại cho các lần gọi sau."""
    global _session
    if _session is not None:
        return _session

    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(
            f"Thieu file model chong gia mao: {MODEL_PATH}. "
            "Tai 2.7_80x80_MiniFASNetV2.onnx (MiniFASNetV2, dau vao 1x3x80x80) "
            "dat vao backend/ai/weights/ roi chay lai."
        )

    import onnxruntime

    session = onnxruntime.InferenceSession(
        MODEL_PATH, providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError(
            f"Model chong gia mao phai co 1 dau vao va 1 dau ra, "
            f"nhan duoc {len(inputs)} va {len(outputs)}"
        )
    shape = inputs[0].shape
    if len(shape) != 4 or int(shape[2]) != ANTI_SPOOF_SIZE or int(shape[3]) != ANTI_SPOOF_SIZE:
        raise RuntimeError(
            f"Model chong gia mao phai nhan anh CHW {ANTI_SPOOF_SIZE}x{ANTI_SPOOF_SIZE}, "
            f"nhan duoc shape {shape}"
        )

    _session = session
    logger.info("Da nap model chong gia mao %s (input %s, output %s)",
                ANTI_SPOOF_MODEL, shape, outputs[0].shape)
    return _session


def model_info():
    """Thông tin model đã nạp: tên file, tên/shape đầu vào và đầu ra."""
    session = _get_session()
    inp = session.get_inputs()[0]
    out = session.get_outputs()[0]
    return {
        "file": MODEL_PATH,
        "input_name": inp.name,
        "input_shape": list(inp.shape),
        "output_name": out.name,
        "output_shape": list(out.shape),
    }


def crop_anti_spoof(image_bgr, bbox):
    """Cắt vùng MỞ RỘNG quanh mặt cho MiniFASNetV2, trả ảnh BGR 80x80.

    Khác vùng cắt nhận diện: lấy cả tóc, vai và nền quanh mặt (hệ số ANTI_SPOOF_SCALE
    quanh tâm bbox), rồi thu nhỏ về 80x80 đúng đầu vào model.
    """
    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.ndim != 3:
        raise ValueError("image_bgr phai la numpy array BGR HxWx3")
    if bbox is None or len(bbox) != 4:
        raise ValueError("bbox phai co 4 so [x1, y1, x2, y2]")

    src_h, src_w = image_bgr.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in bbox)
    box_w, box_h = x2 - x1, y2 - y1
    if box_w <= 1 or box_h <= 1:
        raise ValueError(f"bbox khong hop le: {list(bbox)}")
    if x2 <= 0 or y2 <= 0 or x1 >= src_w or y1 >= src_h:
        raise ValueError(f"bbox nam ngoai anh: {list(bbox)}")

    # Không phóng quá biên ảnh, nếu không vùng cắt sẽ tràn ra ngoài.
    scale = min(ANTI_SPOOF_SCALE, (src_w - 1) / box_w, (src_h - 1) / box_h)
    new_w, new_h = box_w * scale, box_h * scale
    center_x, center_y = x1 + box_w / 2.0, y1 + box_h / 2.0

    left = max(0, int(center_x - new_w / 2.0))
    top = max(0, int(center_y - new_h / 2.0))
    right = min(src_w - 1, int(center_x + new_w / 2.0))
    bottom = min(src_h - 1, int(center_y + new_h / 2.0))

    crop = image_bgr[top:bottom + 1, left:right + 1]
    if crop.size == 0:
        raise ValueError(f"bbox nam ngoai anh: {list(bbox)}")

    return cv2.resize(crop, (ANTI_SPOOF_SIZE, ANTI_SPOOF_SIZE),
                      interpolation=cv2.INTER_LINEAR)


def _preprocess(crop_bgr):
    """BGR 80x80 -> tensor 1x3x80x80 float32.

    Model gốc không chia 255 và không trừ mean: giữ nguyên giá trị 0..255 như
    lúc huấn luyện (đã đối chiếu mã tham chiếu MiniFASNetV2).
    """
    if crop_bgr.shape != (ANTI_SPOOF_SIZE, ANTI_SPOOF_SIZE, 3):
        raise ValueError(
            f"anh dau vao phai co shape ({ANTI_SPOOF_SIZE}, {ANTI_SPOOF_SIZE}, 3), "
            f"nhan duoc {crop_bgr.shape}")
    tensor = crop_bgr.astype(np.float32)
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
    return np.ascontiguousarray(tensor)


def _softmax(logits):
    """Softmax ổn định số học cho vector logits 3 lớp."""
    values = np.asarray(logits, dtype=np.float64).reshape(-1)
    shifted = values - np.max(values)
    exp = np.exp(shifted)
    return exp / np.sum(exp)


def liveness_score(image_bgr, bbox):
    """Xác suất lớp "thật" (0..1) của khuôn mặt trong bbox."""
    crop = crop_anti_spoof(image_bgr, bbox)
    session = _get_session()
    inp = session.get_inputs()[0]
    out = session.get_outputs()[0]
    logits = session.run([out.name], {inp.name: _preprocess(crop)})[0]
    probs = _softmax(np.asarray(logits).reshape(-1))
    if probs.size < 3:
        raise RuntimeError(f"model chong gia mao phai tra 3 lop, nhan duoc {probs.size}")
    # Theo repo goc: lop 0 = fake, lop 1 = real, lop 2 = fake.
    return float(probs[1])


def check_liveness(image_bgr, bbox):
    """Trả về (is_real: bool, score: float).

    Ảnh nhiều mặt thì A2 gọi hàm này riêng cho từng bbox. Bbox không hợp lệ
    trả (False, 0.0) và ghi cảnh báo, không làm sập request.
    """
    try:
        score = liveness_score(image_bgr, bbox)
    except (TypeError, ValueError) as exc:
        logger.warning("Bbox khong hop le cho kiem tra song: %r (%s)", bbox, exc)
        return False, 0.0
    return bool(score >= LIVENESS_MIN), float(score)


def _gray_crop(image_bgr, bbox):
    """Vùng cắt chống giả mạo -> ảnh xám 80x80 float32 đã làm mượt nhẹ."""
    crop = crop_anti_spoof(image_bgr, bbox)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)


def check_liveness_sequence(frames, boxes):
    """Kiểm tra sống theo thời gian trên 6–15 khung của CÙNG một khuôn mặt.

    `frames` là danh sách ảnh BGR đầy đủ, `boxes` là bbox tương ứng từng khung
    (A2 đã theo dõi mặt bằng IoU). Trả về (is_real, score, detail):
    - score: trung vị xác suất lớp "thật" qua các khung.
    - detail: số khung dùng được, điểm từng khung, trung vị/min/độ lệch, năng lượng
      chuyển động, ngưỡng đã dùng và chế độ chạy.

    Điều kiện đạt: trung vị >= LIVENESS_MIN VÀ năng lượng chuyển động
    >= LIVENESS_SEQ_MOTION_MIN. Ảnh tĩnh chụp lại (hoặc replay đứng yên) giữ nguyên
    từng pixel nên chuyển động gần 0 dù điểm model rất cao.

    Chuỗi ngắn hơn LIVENESS_SEQ_MIN_FRAMES thì quay về kiểm tra một khung cuối,
    để A2 không phải xử lý riêng trường hợp mới thấy mặt.
    """
    detail = {"mode": "sequence", "frames": 0, "scores": [], "median": 0.0,
              "minimum": 0.0, "std": 0.0, "motion": 0.0,
              "liveness_min": float(LIVENESS_MIN),
              "motion_min": float(LIVENESS_SEQ_MOTION_MIN)}

    if frames is None or boxes is None:
        detail["mode"] = "invalid"
        detail["reason"] = "thieu frames hoac boxes"
        return False, 0.0, detail
    frames = list(frames)
    boxes = list(boxes)
    if len(frames) != len(boxes):
        detail["mode"] = "invalid"
        detail["reason"] = f"so khung {len(frames)} khac so bbox {len(boxes)}"
        logger.warning("check_liveness_sequence: %s", detail["reason"])
        return False, 0.0, detail
    if not frames:
        detail["mode"] = "invalid"
        detail["reason"] = "chuoi rong"
        return False, 0.0, detail

    # Chỉ giữ các khung mới nhất nếu A2 giữ lịch sử dài.
    frames = frames[-LIVENESS_SEQ_MAX_FRAMES:]
    boxes = boxes[-LIVENESS_SEQ_MAX_FRAMES:]

    scores, grays = [], []
    for frame, box in zip(frames, boxes):
        try:
            scores.append(liveness_score(frame, box))
            grays.append(_gray_crop(frame, box))
        except (TypeError, ValueError) as exc:
            logger.warning("Bo qua khung loi trong chuoi kiem tra song: %r (%s)", box, exc)

    if not scores:
        detail["mode"] = "invalid"
        detail["reason"] = "khong co khung hop le"
        return False, 0.0, detail

    if len(scores) < LIVENESS_SEQ_MIN_FRAMES:
        is_real, score = check_liveness(frames[-1], boxes[-1])
        detail.update({"mode": "single_frame", "frames": len(scores),
                       "scores": [round(s, 6) for s in scores]})
        return is_real, score, detail

    diffs = [float(np.mean(np.abs(grays[i] - grays[i - 1])))
             for i in range(1, len(grays))]
    motion = float(np.mean(diffs))
    median = float(np.median(scores))
    detail.update({
        "frames": len(scores),
        "scores": [round(s, 6) for s in scores],
        "median": median,
        "minimum": float(np.min(scores)),
        "std": float(np.std(scores)),
        "motion": motion,
    })

    is_real = bool(median >= LIVENESS_MIN and motion >= LIVENESS_SEQ_MOTION_MIN)
    return is_real, median, detail
