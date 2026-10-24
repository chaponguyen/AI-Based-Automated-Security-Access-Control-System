# Agent 1 (AI) — chống giả mạo khuôn mặt, MiniFASNetV2 (bản ONNX)
# LƯU Ý: model này cần vùng cắt MỞ RỘNG quanh mặt (cấu hình gốc dùng hệ số khoảng 2.7),
# khác với vùng cắt chặt dùng để nhận diện. Kiểm tra lại cấu hình khi tích hợp.
import logging
import os

from .config import ANTI_SPOOF_MODEL, ANTI_SPOOF_SIZE

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


def check_liveness(image_bgr, bbox):
    """Trả về (is_real: bool, score: float)."""
    raise NotImplementedError
