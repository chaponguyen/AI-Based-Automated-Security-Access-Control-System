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
            # Kiểm tra client đã ngắt kết nối chưa (CP-04)
            if await request.is_disconnected():
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

            # TODO (CP-03): Vẽ khung nhận diện và nhãn khi đã có AI Engine

            # Resize giảm tải băng thông và CPU nếu khung gốc lớn hơn STREAM_WIDTH
            h, w = frame.shape[:2]
            if w > stream_width:
                new_h = int(h * stream_width / w)
                display_frame = cv2.resize(frame, (stream_width, new_h), interpolation=cv2.INTER_AREA)
            else:
                display_frame = frame

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
