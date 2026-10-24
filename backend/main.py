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
    logger.info("Bắt đầu khởi động hệ thống AI Security Access Control...")

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

    # (4) Khởi động vòng lặp tự động xác thực B12 nếu có
    try:
        from services import verification_service
        if hasattr(verification_service, "start_background_loop"):
            verification_service.start_background_loop()
            logger.info("Vòng lặp xác thực nền B12 đã khởi động.")
    except Exception as e:
        logger.debug("Verification background loop chưa sẵn sàng: %s", e)

    yield

    # Dọn dẹp khi tắt hệ thống (shutdown)
    logger.info("Đang tắt hệ thống và giải phóng tài nguyên...")
    try:
        from services import verification_service
        if hasattr(verification_service, "stop_background_loop"):
            verification_service.stop_background_loop()
    except Exception:
        pass

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

from api import residents, verify, logs, ws, camera
for r in (residents.router, verify.router, logs.router, ws.router, camera.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    """Kiểm tra sức khỏe hệ thống: trạng thái chung, camera và AI."""
    from services.camera_service import get_camera
    cam = get_camera()
    cam_status = cam.status().get("running", False)
    return {
        "status": "ok",
        "camera": cam_status,
        "ai": ai_running,
    }

