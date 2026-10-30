# Agent 2 — đẩy sự kiện xác thực và trạng thái cửa cho Dashboard
import asyncio
import logging
import threading
from typing import Any, Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

_main_loop: asyncio.AbstractEventLoop = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Lưu event loop chính của FastAPI để hỗ trợ broadcast từ luồng nền."""
    global _main_loop
    _main_loop = loop


class ConnectionManager:
    """Quản lý danh sách kết nối WebSocket của Dashboard và phát sự kiện."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Chấp nhận kết nối và gửi ngay trạng thái camera hiện tại."""
        global _main_loop
        if _main_loop is None:
            try:
                _main_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        await websocket.accept()
        with self._lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket Dashboard đã kết nối (tổng số: %d)", len(self.active_connections))

        # Khi kết nối, gửi ngay camera_status theo quy định
        try:
            from services.camera_service import get_camera
            cam = get_camera()
            cam_status = cam.status()
        except Exception:
            cam_status = {"running": False, "fps": 0, "width": 0, "height": 0, "viewers": 0}

        try:
            await websocket.send_json({
                "event": "camera_status",
                "data": cam_status,
            })
        except Exception as e:
            logger.warning("Không thể gửi camera_status khởi tạo: %s", e)

        # Gửi ngay ai_status hiện tại để chip AI trên Dashboard sáng ngay lập tức (CP-06)
        try:
            from services.auto_verify_service import get_auto_verify_service
            ai_svc = get_auto_verify_service()
            ai_data = ai_svc.get_ai_status_payload()
            await websocket.send_json({
                "event": "ai_status",
                "data": ai_data,
            })
        except Exception as e:
            logger.debug("Không thể gửi ai_status khởi tạo: %s", e)

        # Gửi ngay door_state hiện tại cho client mới kết nối (B16 CP-05)
        try:
            from services.door_service import get_door_service
            door_svc = get_door_service()
            door_data = door_svc.get_door_state_event_payload()
            await websocket.send_json({
                "event": "door_state",
                "data": door_data,
            })
        except Exception as e:
            logger.debug("Không thể gửi door_state khởi tạo: %s", e)

    def disconnect(self, websocket: WebSocket) -> None:
        """Gỡ bỏ kết nối khi client ngắt kết nối."""
        with self._lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket Dashboard đã ngắt kết nối (còn lại: %d)", len(self.active_connections))

    async def broadcast_async(self, payload: Dict[str, Any]) -> None:
        """Gửi message tới tất cả các WebSocket đang kết nối."""
        with self._lock:
            targets = list(self.active_connections)
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.debug("Lỗi gửi WebSocket tới client, gỡ kết nối: %s", e)
                self.disconnect(ws)


manager = ConnectionManager()


def broadcast(event: str, data: Dict[str, Any]) -> None:
    """Hàm phát sự kiện WebSocket gọi được từ bất kỳ đâu, kể cả luồng nền (threading).
    
    Khớp API CONTRACT:
    {
        event: "access_result" | "door_state" | "camera_status" | "ai_status" | "record_progress",
        data: {...}
    }
    """
    payload = {"event": event, "data": data}
    loop = _main_loop

    if loop is not None and loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(manager.broadcast_async(payload), loop)
            return
        except Exception as e:
            logger.error("Lỗi khi dispatch run_coroutine_threadsafe: %s", e)

    # Nếu không có loop chính nhưng đang trong một asyncio event loop
    try:
        current_loop = asyncio.get_running_loop()
        if current_loop.is_running():
            current_loop.create_task(manager.broadcast_async(payload))
    except RuntimeError:
        logger.debug("Không tìm thấy running event loop để broadcast WebSocket event: %s", event)


async def _ping_heartbeat(websocket: WebSocket, raw_token: str):
    """Ping định kỳ mỗi 20 giây và kiểm tra hiệu lực phiên (B15 CP-04).
    
    Nếu phiên bị thu hồi hoặc tài khoản bị tắt (is_active=False) thì đóng kết nối
    với mã 1008 trong vòng ~20-30 giây.

    Dùng get_session_info() trả StaffInfo (dataclass thuần) để tránh
    DetachedInstanceError khi đọc thuộc tính ORM sau khi Session đóng.
    """
    from database.database import SessionLocal
    from services import auth_service

    try:
        while True:
            await asyncio.sleep(20)
            # Kiểm tra hiệu lực phiên trong CSDL — mở Session mới mỗi lần
            db = SessionLocal()
            info = None
            try:
                info = auth_service.get_session_info(db, raw_token)
            except Exception as e:
                logger.debug("Lỗi kiểm tra phiên định kỳ trong WS ping: %s", e)
            finally:
                db.close()

            if not info or not info.is_active:
                logger.warning("Phiên WebSocket bị thu hồi hoặc tài khoản bị tắt, đóng kết nối với code 1008.")
                await websocket.close(code=1008, reason="session_revoked")
                break

            await websocket.send_json({"event": "ping", "data": {}})
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint cho Dashboard.
    
    Bảo mật B15 CP-04:
    - Kiểm tra cookie 'session' TRƯỚC khi accept.
    - Thiếu cookie hoặc phiên không hợp lệ: đóng ngay với mã 1008 (không gửi dữ liệu).
    - Kiểm tra định kỳ mỗi 20 giây qua heartbeat: nếu phiên bị thu hồi hoặc tài khoản bị tắt thì đóng kết nối với mã 1008.
    """
    raw_token = websocket.cookies.get("session")
    if not raw_token:
        logger.warning("WebSocket bị từ chối: thiếu cookie session, đóng với code 1008.")
        await websocket.close(code=1008, reason="not_authenticated")
        return

    from database.database import SessionLocal
    from services import auth_service

    db = SessionLocal()
    info = None
    try:
        info = auth_service.get_session_info(db, raw_token)
    except Exception as e:
        logger.warning("Lỗi kiểm tra phiên khi kết nối WS: %s", e)
    finally:
        db.close()

    if not info or not info.is_active:
        logger.warning("WebSocket bị từ chối: phiên không hợp lệ hoặc tài khoản bị vô hiệu hóa, đóng với code 1008.")
        await websocket.close(code=1008, reason="not_authenticated")
        return

    # Chỉ accept và bắt đầu gửi dữ liệu sau khi xác thực hợp lệ
    await manager.connect(websocket)
    ping_task = asyncio.create_task(_ping_heartbeat(websocket, raw_token))
    try:
        while True:
            # Lắng nghe tin nhắn từ client
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket client kết thúc: %s", e)
        manager.disconnect(websocket)
    finally:
        ping_task.cancel()
