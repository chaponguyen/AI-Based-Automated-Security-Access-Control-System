"""Dịch vụ stream video MJPEG cho trình duyệt web.

Chỉ mã hóa JPEG khi có người xem kết nối (tiết kiệm CPU, không ảnh hưởng vòng lặp AI).
"""
import os
import asyncio
import logging
from typing import AsyncGenerator
import cv2
import numpy as np
from fastapi import Request
from services.camera_service import get_camera

logger = logging.getLogger(__name__)


import time
import unicodedata
from typing import AsyncGenerator, List, Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

# Khởi tạo font chữ tiếng Việt có dấu (Arial/Segoe UI trên Windows, DejaVu trên Linux)
_font_cache: Optional[ImageFont.FreeTypeFont] = None


def _get_vietnamese_font(size: int = 15) -> Optional[ImageFont.FreeTypeFont]:
    """Tải font hỗ trợ tiếng Việt có dấu từ hệ điều hành."""
    global _font_cache
    if _font_cache is not None:
        return _font_cache

    font_candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                _font_cache = ImageFont.truetype(path, size)
                return _font_cache
            except Exception:
                continue
    return None


def _strip_vietnamese_accents(text: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu thành không dấu phục vụ fallback cv2.putText."""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _draw_label_banner(
    img: np.ndarray,
    text: str,
    x1: int,
    y1: int,
    color_bgr: Tuple[int, int, int],
) -> None:
    """Vẽ nhãn banner tiếng Việt có dấu chuẩn đẹp lên ảnh BGR, không chuyển đổi cả khung hình."""
    font = _get_vietnamese_font(size=15)
    if font is not None:
        try:
            # Đo kích thước chữ
            dummy = Image.new("RGB", (1, 1))
            d_dummy = ImageDraw.Draw(dummy)
            bbox = d_dummy.textbbox((0, 0), text, font=font)
            tw = (bbox[2] - bbox[0]) + 14
            th = (bbox[3] - bbox[1]) + 8

            by1 = max(0, y1 - th)
            by2 = y1
            bx1 = max(0, x1)
            bx2 = min(img.shape[1], x1 + tw)

            actual_w = bx2 - bx1
            actual_h = by2 - by1
            if actual_w > 0 and actual_h > 0:
                # PIL dùng RGB, OpenCV dùng BGR
                rgb_bg = (color_bgr[2], color_bgr[1], color_bgr[0])
                patch = Image.new("RGB", (actual_w, actual_h), color=rgb_bg)
                d = ImageDraw.Draw(patch)
                d.text((6, (actual_h - (bbox[3] - bbox[1])) // 2 - 1), text, font=font, fill=(255, 255, 255))
                patch_bgr = np.array(patch)[:, :, ::-1]
                img[by1:by2, bx1:bx2] = patch_bgr
                return
        except Exception as err:
            logger.debug("Lỗi vẽ nhãn tiếng Việt bằng PIL: %s, fallback sang cv2.putText", err)

    # Fallback nếu không có font hoặc lỗi: dùng cv2.putText không dấu
    clean_text = _strip_vietnamese_accents(text)
    cv2.rectangle(img, (x1, max(0, y1 - 22)), (x1 + len(clean_text) * 11, y1), color_bgr, -1)
    cv2.putText(
        img,
        clean_text,
        (x1 + 4, max(12, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


# Snapshot an toàn luồng cho overlay (ghi bằng phép gán nguyên tử tuple trong Python)
_overlay_snapshot: Tuple[float, List[Dict[str, Any]]] = (0.0, [])


def set_latest_overlay(items: List[Dict[str, Any]]) -> None:
    """Cập nhật dữ liệu khung/nhãn mới nhất từ luồng nhận diện AI (B12).

    Phép gán tuple _overlay_snapshot = (time.time(), items) là thao tác nguyên tử,
    không cần khóa lâu, đảm bảo an toàn luồng tuyệt đối và không bao giờ làm nghẽn AI hay Stream.
    """
    global _overlay_snapshot
    _overlay_snapshot = (time.time(), items)


def get_latest_overlay(max_age_sec: float = 1.5) -> List[Dict[str, Any]]:
    """Lấy danh sách overlay mới nhất.

    Nếu kết quả cũ quá max_age_sec (1.5 giây), ngừng hiển thị nhãn/khung để tránh thông tin sai lệch.
    """
    ts, items = _overlay_snapshot
    if (time.time() - ts) > max_age_sec:
        return []
    return items


# Snapshot an toàn luồng cho precheck đăng ký (B5 CP-07)
_precheck_snapshot: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)


def set_latest_precheck(data: Optional[Dict[str, Any]]) -> None:
    """Lưu kết quả precheck đăng ký mới nhất (an toàn luồng, không lock lâu)."""
    global _precheck_snapshot
    _precheck_snapshot = (time.time(), data)


def get_latest_precheck(max_age_sec: float = 2.0) -> Optional[Dict[str, Any]]:
    """Lấy dữ liệu precheck còn mới (trong vòng max_age_sec, mặc định 2.0 giây)."""
    ts, data = _precheck_snapshot
    if (time.time() - ts) <= max_age_sec and data is not None:
        return data
    return None


def draw_overlay(frame: np.ndarray) -> np.ndarray:
    """Vẽ khung và nhãn lên bản sao của khung hình stream (CP-03, B5 CP-07).

    - Ưu tiên 1: Kết quả precheck đăng ký B5 CP-07 (còn mới dưới 2.0s):
      + exists: khung ĐỎ (0, 0, 220), nhãn "ĐÃ TỒN TẠI: <tên>".
      + new: khung XANH DƯƠNG (255, 140, 0), nhãn "Người mới".
    - Ưu tiên 2: Kết quả nhận diện B12 qua get_latest_overlay() (dưới 1.5s):
      + granted: khung XANH LÁ (0, 200, 0), nhãn full_name, 5 landmarks.
      + denied: khung ĐỎ (0, 0, 220), nhãn "Không xác định".
      + tracking: khung VÀNG CAM (0, 215, 255), nhãn "Đang nhận diện...".
    - Quá thời gian quy định thì ngừng vẽ nhãn.
    - Vẽ trên bản sao frame.copy() để tuyệt đối không ảnh hưởng khung hình gốc của AI.
    """
    # 1. Kiểm tra precheck đăng ký trước (B5 CP-07)
    precheck = get_latest_precheck(max_age_sec=2.0)
    if precheck is not None:
        box = precheck.get("box")
        if box and len(box) >= 4:
            display_frame = frame.copy()
            x1, y1, x2, y2 = [int(v) for v in box]
            exists = bool(precheck.get("exists", False))
            name = precheck.get("name", "")

            if exists:
                color = (0, 0, 220)       # Đỏ
                label = f"ĐÃ TỒN TẠI: {name}" if name else "ĐÃ TỒN TẠI"
            else:
                color = (255, 140, 0)     # Xanh dương (BGR)
                label = "Người mới"

            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            landmarks = precheck.get("landmarks")
            if landmarks:
                for pt in landmarks:
                    if len(pt) >= 2:
                        lx, ly = int(pt[0]), int(pt[1])
                        cv2.circle(display_frame, (lx, ly), radius=3, color=(0, 255, 255), thickness=-1)
            _draw_label_banner(display_frame, label, x1, y1, color)
            return display_frame

    # 2. Overlay tự động xác thực B12
    overlay_items = get_latest_overlay(max_age_sec=1.5)
    if not overlay_items:
        return frame

    # BẮT BUỘC sao chép để không làm biến đổi khung gốc trong CameraService
    display_frame = frame.copy()

    for item in overlay_items:
        box = item.get("box")
        if not box or len(box) < 4:
            continue

        x1, y1, x2, y2 = [int(v) for v in box]
        landmarks = item.get("landmarks")
        name = item.get("name") or "Không xác định"
        decision = item.get("decision", "tracking")

        # Xác định màu sắc theo quyết định
        if decision == "granted":
            color = (0, 200, 0)      # Xanh lá
            label = name
        elif decision == "denied":
            color = (0, 0, 220)      # Đỏ
            label = name if name != "Đang nhận diện..." else "Không xác định"
        else:
            color = (0, 215, 255)    # Vàng cam (đang theo dõi / phân tích)
            label = name

        # 1. Vẽ hình chữ nhật tight_box quanh khuôn mặt
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)

        # 2. Vẽ 5 điểm landmark mắt, mũi, khóe miệng
        if landmarks:
            for pt in landmarks:
                if len(pt) >= 2:
                    lx, ly = int(pt[0]), int(pt[1])
                    cv2.circle(display_frame, (lx, ly), radius=3, color=(0, 255, 255), thickness=-1)

        # 3. Vẽ nhãn banner hiển thị tên hoặc trạng thái (hỗ trợ tiếng Việt có dấu)
        _draw_label_banner(display_frame, label, x1, y1, color)

    return display_frame


async def generate_mjpeg_stream(request: Request) -> AsyncGenerator[bytes, None]:
    """Tạo luồng stream MJPEG multipart/x-mixed-replace cho trình duyệt.
    
    Tần suất tối đa STREAM_MAX_FPS (mặc định 12 fps).
    Resize chiều rộng theo STREAM_WIDTH (mặc định 960).
    Chất lượng nén JPEG theo STREAM_JPEG_QUALITY (mặc định 70).
    """
    camera = get_camera()

    stream_fps = float(os.getenv("STREAM_MAX_FPS", "12"))
    stream_width = int(os.getenv("STREAM_WIDTH", "960"))
    stream_quality = int(os.getenv("STREAM_JPEG_QUALITY", "70"))
    frame_interval = 1.0 / stream_fps if stream_fps > 0 else 0.083

    # CP-02: Tăng số lượng người xem khi client kết nối
    camera.change_viewers(+1)
    logger.info(
        "Client kết nối stream MJPEG (viewers=%d, fps=%.1f, width=%d, quality=%d)",
        camera.status().get("viewers", 1),
        stream_fps,
        stream_width,
        stream_quality,
    )

    last_frame_ts = None

    try:
        while True:
            # CP-04: Đóng kết nối thì dừng stream ngay lập tức
            if await request.is_disconnected():
                logger.info("Phát hiện client đã ngắt kết nối qua request.is_disconnected(), dừng stream.")
                break

            now_ts, frame = camera.latest()

            if frame is None:
                # Camera chưa sẵn sàng hoặc mất kết nối, chờ một chút
                await asyncio.sleep(0.1)
                continue

            # Bỏ qua nếu khung hình chưa đổi để tránh mã hóa lặp lại khung cũ
            if now_ts is not None and now_ts == last_frame_ts:
                await asyncio.sleep(0.02)
                continue

            last_frame_ts = now_ts

            # CP-03 (STUB): Vẽ khung nhận diện và nhãn (chờ tích hợp AI từ B12)
            display_frame = draw_overlay(frame)

            # Resize giảm tải băng thông và CPU nếu khung gốc lớn hơn STREAM_WIDTH
            h, w = display_frame.shape[:2]
            if w > stream_width:
                new_h = int(h * stream_width / w)
                display_frame = cv2.resize(display_frame, (stream_width, new_h), interpolation=cv2.INTER_AREA)


            # Mã hóa JPEG
            ret, jpeg_buffer = cv2.imencode(
                ".jpg",
                display_frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), stream_quality],
            )
            if not ret:
                await asyncio.sleep(0.02)
                continue

            jpeg_bytes = jpeg_buffer.tobytes()
            content_length = len(jpeg_bytes)

            chunk = (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(content_length).encode("ascii") + b"\r\n\r\n" +
                jpeg_bytes +
                b"\r\n"
            )

            yield chunk
            await asyncio.sleep(frame_interval)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning("Ngoại lệ trong vòng lặp stream MJPEG: %s", e)
    finally:
        # CP-02: Giảm số lượng người xem khi client ngắt kết nối
        camera.change_viewers(-1)
        logger.info("Client ngắt kết nối stream MJPEG (viewers=%d).", camera.status().get("viewers", 0))
