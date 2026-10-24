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


def draw_overlay(frame: np.ndarray) -> np.ndarray:
    """Vẽ khung và nhãn lên khung hình stream (CP-03 STUB).

    TODO (CP-03): Tích hợp với B12 (AI Engine) khi có:
    - Nhận diện cư dân: vẽ tight_box màu xanh lá (0, 255, 0), nhãn full_name, 5 landmarks
    - Người lạ / từ chối: vẽ tight_box màu đỏ (0, 0, 255), nhãn "Không xác định"
    Hiện tại trả về khung hình gốc để không ảnh hưởng stream và AI.
    """
    return frame


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
