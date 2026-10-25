# Agent 2 (Backend & DB)
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

logger = logging.getLogger(__name__)

# Trạng thái mô hình AI toàn cục
ai_running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ai_running
    # (0) Lưu main event loop cho WebSocket broadcast từ luồng nền
    try:
        import asyncio
        from api import ws
        ws.set_event_loop(asyncio.get_running_loop())
    except Exception as e:
        logger.warning("Không thể gán event loop cho WebSocket: %s", e)

    # (1) Khởi động camera và luồng nền (LocalCamera)
    camera = None
    try:
        from services.camera_service import get_camera
        camera = get_camera()
        camera.start()
        logger.info("Camera background thread đã khởi động (running=%s)", camera.status().get("running"))
    except Exception as e:
        logger.error("Lỗi khi khởi động camera trong lifespan: %s", e)

    # (2) Nạp sẵn model AI (detector, embedder, anti_spoof) nếu đã có
    ai_running = False
    try:
        from ai import detector
        if hasattr(detector, "get_app"):
            detector.get_app()
            ai_running = True
            logger.info("AI detector model đã được nạp sẵn.")
        else:
            logger.info("AI detector chưa có get_app() hoặc chưa cài đặt model, bỏ qua nạp trước.")
    except Exception as e:
        logger.warning("Không thể nạp trước model AI (hệ thống vẫn chạy không sập): %s", e)
        ai_running = False

    # (3) Nạp GalleryCache (B6) nếu có
    try:
        from services import gallery_cache
        if hasattr(gallery_cache, "init_cache"):
            gallery_cache.init_cache()
            logger.info("GalleryCache đã được khởi tạo.")
    except Exception as e:
        logger.debug("GalleryCache chưa sẵn sàng: %s", e)

    # (4) Khởi động vòng lặp tự động xác thực B12
    try:
        from services import auto_verify_service
        auto_verify_service.start()
        logger.info("Vòng lặp xác thực nền B12 (AutoVerifyService) đã khởi động thành công.")
    except Exception as e:
        logger.warning("Không thể khởi động vòng lặp xác thực nền B12: %s", e)

    yield

    # Dọn dẹp khi tắt hệ thống (shutdown)
    logger.info("Đang tắt hệ thống và giải phóng tài nguyên...")
    try:
        from services import auto_verify_service
        auto_verify_service.stop()
        logger.info("AutoVerifyService đã được dừng sạch sẽ.")
    except Exception as e:
        logger.warning("Lỗi khi dừng AutoVerifyService: %s", e)

    if camera is not None:
        try:
            camera.stop()
            logger.info("LocalCamera đã được dừng sạch sẽ và tắt đèn.")
        except Exception as e:
            logger.warning("Lỗi khi dừng camera khi shutdown: %s", e)


app = FastAPI(title="AI Security Access Control", lifespan=lifespan)

# Cấu hình CORS cho frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api import residents, verify, logs, ws, camera, stream
for r in (residents.router, residents.registration_router, verify.router, logs.router, ws.router, camera.router, stream.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    """Kiểm tra sức khỏe hệ thống: trạng thái chung, camera và AI."""
    from services.camera_service import get_camera
    from services import auto_verify_service
    cam = get_camera()
    cam_status = cam.status().get("running", False)
    ai_status = auto_verify_service.is_running() or ai_running
    return {
        "status": "ok",
        "camera": cam_status,
        "ai": ai_status,
    }

