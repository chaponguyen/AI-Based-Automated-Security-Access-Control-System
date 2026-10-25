# Agent 2 — Vòng lặp tự động xác thực khuôn mặt chạy nền (B12 CP-01, CP-02, CP-03, CP-04)
import os
import time
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Callable
import numpy as np
from dotenv import load_dotenv

# Tải cấu hình từ backend/.env
load_dotenv()

from database.database import SessionLocal
from services.camera_service import get_camera
from services import ai_control
from services.verification_service import verify_face, record_access
from services.speaker_text import announcement
from api.ws import broadcast
from ai.detector import detect_faces
from ai.quality import frame_quality

logger = logging.getLogger(__name__)


def _parse_float_env(key: str, default: float) -> float:
    """Đọc biến môi trường kiểu số thực, dùng mặc định nếu thiếu hoặc sai định dạng."""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        logger.warning("Cấu hình '%s=%s' không hợp lệ: phải là số thực/nguyên. Dùng mặc định %s", key, raw, default)
        return default


# ==================== CẤU HÌNH THAM SỐ VÒNG LẶP ====================
AI_FPS_ACTIVE = 6.0         # Tốc độ tối đa khi có mặt hoặc vừa thấy mặt (khung/giây)
AI_FPS_IDLE = 3.0           # Tốc độ khi không có mặt trong 5 giây (khung/giây)
IDLE_TIMEOUT_SEC = 5.0      # Thời gian không thấy mặt để chuyển sang chế độ tiết kiệm CPU

# Cấu hình điều kiện kích hoạt xác thực (CP-02)
MIN_FACE_PX_VERIFY = 110    # Cạnh ngắn tối thiểu của bbox để kích hoạt xác thực (110 px)
STABLE_FRAMES_REQUIRED = 3  # Số khung hình liên tiếp ổn định (~0.5 giây ở 6 fps)
IOU_THRESHOLD = 0.5         # Ngưỡng IoU để liên kết theo dõi cùng một khuôn mặt

# Cấu hình chống báo lặp (CP-04)
# GRANTED_COOLDOWN_S: Cư dân granted không báo lại trong 60 giây (khóa theo user_id)
# STRANGER_REST_S: Người lạ cảnh báo khi có ít nhất 3/5 kết quả denied, sau đó nghỉ 15 giây
GRANTED_COOLDOWN_S = _parse_float_env("GRANTED_COOLDOWN_S", 60.0)
STRANGER_REST_S = _parse_float_env("STRANGER_REST_S", 15.0)
STRANGER_MIN_DENIED = 3       # Số lần denied trong 5 kết quả gần nhất để cảnh báo người lạ

# Tương thích ngược tên biến cũ
RESIDENT_COOLDOWN_SEC = GRANTED_COOLDOWN_S
STRANGER_COOLDOWN_SEC = STRANGER_REST_S


def compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """Tính Intersection over Union (IoU) giữa hai hộp giới hạn [x1, y1, x2, y2]."""
    x_a = max(box_a[0], box_b[0])
    y_a = max(box_a[1], box_b[1])
    x_b = min(box_a[2], box_b[2])
    y_b = min(box_a[3], box_b[3])

    inter_w = max(0.0, x_b - x_a)
    inter_h = max(0.0, y_b - y_a)
    inter_area = inter_w * inter_h
    if inter_area == 0.0:
        return 0.0

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union_area = area_a + area_b - inter_area
    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


class TrackedFace:
    """Đối tượng theo dõi một khuôn mặt liên tục qua các khung hình."""

    def __init__(self, track_id: int, face: dict, now: float, is_qualified: bool = False) -> None:
        self.track_id: int = track_id
        self.bbox: List[float] = [float(v) for v in face.get("bbox", [0, 0, 0, 0])]
        self.kps: Any = face.get("kps")
        self.score: float = float(face.get("score", 0.0))
        self.created_at: float = now
        self.last_seen_at: float = now

        # Số khung hình liên tiếp đạt chất lượng và kích thước (CP-02)
        self.stable_count: int = 1 if is_qualified else 0
        self.is_qualified: bool = is_qualified
        self.ready_to_verify: bool = (self.stable_count >= STABLE_FRAMES_REQUIRED)

        # Lịch sử kết quả xác thực (giữ 5 kết quả gần nhất - CP-03)
        self.verify_history: List[dict] = []
        self.triggered: bool = False
        self.last_triggered_at: Optional[float] = None
        self.last_decision: Optional[str] = None
        self.user_id: Optional[int] = None

    def update(self, face: dict, is_qualified: bool, now: float) -> None:
        """Cập nhật vị trí và trạng thái ổn định khi được khớp trong khung mới."""
        self.bbox = [float(v) for v in face.get("bbox", [0, 0, 0, 0])]
        self.kps = face.get("kps")
        self.score = float(face.get("score", 0.0))
        self.last_seen_at = now
        self.is_qualified = is_qualified

        if is_qualified:
            self.stable_count += 1
        else:
            self.stable_count = 0

        self.ready_to_verify = (self.stable_count >= STABLE_FRAMES_REQUIRED)

    def short_edge(self) -> float:
        """Cạnh ngắn của bbox tính bằng pixel."""
        w = max(0.0, self.bbox[2] - self.bbox[0])
        h = max(0.0, self.bbox[3] - self.bbox[1])
        return min(w, h)

    def to_face_dict(self) -> dict:
        """Xuất thông tin mặt theo cấu trúc phù hợp cho verify_face."""
        return {
            "bbox": [float(v) for v in self.bbox],
            "kps": self.kps,
            "score": self.score,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Xuất thông tin trạng thái theo dõi phục vụ debug và báo cáo."""
        return {
            "track_id": self.track_id,
            "bbox": [int(v) for v in self.bbox],
            "short_edge": round(self.short_edge(), 1),
            "stable_count": self.stable_count,
            "is_qualified": self.is_qualified,
            "ready_to_verify": self.ready_to_verify,
            "triggered": self.triggered,
            "history_len": len(self.verify_history),
        }


class AutoVerifyService:
    """Quản lý luồng nền tự động xác thực khuôn mặt khi có người trước camera.

    CP-01:
    - Khởi động trong lifespan của FastAPI, dừng sạch sẽ khi tắt hệ thống.
    - Đọc camera.latest(), bỏ qua các khung đã xử lý.
    - Giới hạn tốc độ: tối đa 6 fps khi có mặt; tự hạ xuống 3 fps khi không có mặt sau 5s.
    - Mỗi chu kỳ tạo SessionLocal() riêng và giải phóng trong finally.
    - Bắt mọi ngoại lệ trong vòng lặp, ghi log cảnh báo và tiếp tục chạy.

    CP-02:
    - Theo dõi khuôn mặt giữa các khung bằng IoU > 0.5.
    - Điều kiện kích hoạt: bbox >= 110 px, frame_quality đạt, ổn định liên tiếp 3 khung (~0.5s).

    CP-03:
    - Gọi verify_face cho mỗi mặt đủ điều kiện, lưu 5 kết quả gần nhất.
    - Granted khi 2 kết quả liên tiếp cùng một cư dân đều đạt.
    - Cư dân inactive ổn định thì phát sự kiện inactive_user.
    - Ghi đúng 1 dòng access_logs bằng record_access.
    - Dựng announcement (display, spoken, kind) cùng thời điểm log.
    - Phát access_result qua WebSocket broadcast và callback on_event.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False

        # Quản lý thời gian và tần số
        self._last_processed_time: float = 0.0
        self._last_face_seen_time: float = 0.0
        self._actual_fps: float = 0.0
        self._fps_count: int = 0
        self._fps_start_time: float = time.time()
        self._is_idle: bool = True

        # Trạng thái theo dõi khuôn mặt (CP-02..CP-05)
        self._tracked_faces: Dict[int, TrackedFace] = {}
        self._next_track_id: int = 1
        self._last_event_at: Optional[float] = None
        self._on_event_callback: Optional[Callable[[str, dict], None]] = None

        # Cơ chế chống báo lặp (CP-04)
        self._resident_cooldown: Dict[int, float] = {}  # {user_id: last_granted_timestamp}
        self._last_stranger_alert_at: float = 0.0       # timestamp lần cuối cảnh báo người lạ

    def set_event_callback(self, callback: Optional[Callable[[str, dict], None]]) -> None:
        """Đăng ký hàm callback nhận sự kiện (phục vụ cắm loa hoặc MQTT sau này)."""
        self._on_event_callback = callback

    def start(self) -> None:
        """Khởi động luồng nền nếu chưa chạy."""
        with self._lock:
            if self._running and self._thread is not None and self._thread.is_alive():
                logger.info("AutoVerifyService đã đang chạy.")
                return

            self._stop_event.clear()
            self._running = True
            self._last_processed_time = 0.0
            self._last_face_seen_time = 0.0
            self._is_idle = True
            self._fps_count = 0
            self._fps_start_time = time.time()
            self._tracked_faces.clear()
            self._next_track_id = 1

            self._thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="AutoVerifyWorker",
            )
            self._thread.start()
            logger.info("AutoVerifyService luồng nền đã khởi động thành công.")

    def stop(self, timeout: float = 3.0) -> None:
        """Dừng luồng nền sạch sẽ."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            logger.info("AutoVerifyService luồng nền đã dừng sạch sẽ.")
        self._thread = None

    def is_running(self) -> bool:
        """Kiểm tra luồng nền có đang chạy hay không."""
        with self._lock:
            return self._running and self._thread is not None and self._thread.is_alive()

    def status(self) -> Dict[str, Any]:
        """Trả về thông tin trạng thái hoạt động của dịch vụ."""
        with self._lock:
            tracks_info = [t.to_dict() for t in self._tracked_faces.values()]
            return {
                "running": self._running,
                "fps": round(self._actual_fps, 2),
                "is_idle": self._is_idle,
                "tracking": len(self._tracked_faces),
                "tracks": tracks_info,
                "is_paused": ai_control.is_ai_paused(),
                "last_event_at": self._last_event_at,
            }

    def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """Phát sự kiện độc lập tới WebSocket và callback ngoài."""
        # 1. Phát qua WebSocket Dashboard
        try:
            broadcast(event, data)
        except Exception as ws_err:
            logger.warning("Lỗi phát WebSocket broadcast: %s", ws_err)

        # 2. Gọi callback ngoài (loa hoặc MQTT) độc lập
        if self._on_event_callback is not None:
            try:
                self._on_event_callback(event, data)
            except Exception as cb_err:
                logger.warning("Lỗi thực thi on_event_callback: %s", cb_err)

    def _update_tracker(self, frame: np.ndarray, faces: List[dict], now: float) -> List[TrackedFace]:
        """Cập nhật các luồng theo dõi khuôn mặt bằng IoU > 0.5 và kiểm tra chất lượng.

        Trả về danh sách các TrackedFace đã đạt đủ điều kiện sẵn sàng xác thực (CP-02).
        """
        if not faces:
            self._tracked_faces.clear()
            return []

        matched_track_ids = set()
        ready_tracks: List[TrackedFace] = []

        for face in faces:
            bbox = face.get("bbox", [0, 0, 0, 0])
            w = max(0.0, bbox[2] - bbox[0])
            h = max(0.0, bbox[3] - bbox[1])
            short_edge = min(w, h)

            # Điều kiện 1: Cạnh ngắn bbox >= MIN_FACE_PX_VERIFY (110 px)
            is_size_ok = (short_edge >= MIN_FACE_PX_VERIFY)

            # Điều kiện 2: frame_quality đạt (không mờ, không nghiêng lệch, sáng hợp lệ)
            is_quality_ok = False
            if is_size_ok:
                try:
                    q_res = frame_quality(frame, [face], allow_multiple=True)
                    is_quality_ok = bool(q_res.get("ok", False))
                except Exception as q_err:
                    logger.debug("Lỗi tính frame_quality: %s", q_err)
                    is_quality_ok = False

            is_qualified = (is_size_ok and is_quality_ok)

            # Tìm track hiện có có IoU cao nhất >= IOU_THRESHOLD (0.5)
            best_track: Optional[TrackedFace] = None
            best_iou = 0.0

            for track in self._tracked_faces.values():
                if track.track_id in matched_track_ids:
                    continue
                iou = compute_iou(bbox, track.bbox)
                if iou >= IOU_THRESHOLD and iou > best_iou:
                    best_iou = iou
                    best_track = track

            if best_track is not None:
                # Đã khớp track cũ: cập nhật vị trí và tăng stable_count nếu đạt
                best_track.update(face, is_qualified, now)
                matched_track_ids.add(best_track.track_id)
                if best_track.ready_to_verify:
                    ready_tracks.append(best_track)
            else:
                # Khuôn mặt mới xuất hiện: tạo TrackedFace mới
                track_id = self._next_track_id
                self._next_track_id += 1
                new_track = TrackedFace(track_id=track_id, face=face, now=now, is_qualified=is_qualified)
                self._tracked_faces[track_id] = new_track
                matched_track_ids.add(track_id)
                if new_track.ready_to_verify:
                    ready_tracks.append(new_track)

        # Xóa các track cũ không xuất hiện trong khung hình này
        unmatched_ids = [tid for tid in self._tracked_faces if tid not in matched_track_ids]
        for tid in unmatched_ids:
            del self._tracked_faces[tid]

        return ready_tracks

    def _process_verification(self, db, frame: np.ndarray, ready_tracks: List[TrackedFace], now: float) -> None:
        """Thực hiện xác thực khuôn mặt và phát sự kiện ra quyết định kèm chống báo lặp (CP-03, CP-04, CP-05).

        CP-05:
        - Xử lý độc lập từng khuôn mặt được theo dõi trong khung hình.
        - Khi có nhiều sự kiện cùng lúc trong khung hình: ưu tiên cảnh báo người lạ phát trước
          dù có cư dân đi cùng (chống tailgating, DECISIONS_LOG).
        """
        pending_actions = []

        for track in ready_tracks:
            # 1. Kiểm tra trạng thái cooldown của track nếu đã kích hoạt trước đó (hỗ trợ đứng yên lâu - CP-04)
            if track.triggered:
                # Xác định thời gian cooldown tương ứng theo quyết định trước đó
                if track.last_decision in ("granted", "inactive_user") and track.user_id is not None:
                    # Cư dân: khóa theo GRANTED_COOLDOWN_S (60s) theo user_id
                    cooldown_sec = GRANTED_COOLDOWN_S
                    last_time = max(track.last_triggered_at or 0.0, self._resident_cooldown.get(track.user_id, 0.0))
                else:
                    # Người lạ / Spoof: nghỉ STRANGER_REST_S (15s)
                    cooldown_sec = STRANGER_REST_S
                    last_time = max(track.last_triggered_at or 0.0, self._last_stranger_alert_at)

                if (now - last_time) < cooldown_sec:
                    # Vẫn đang trong thời gian cooldown/nghỉ: bỏ qua, không gọi verify_face để tiết kiệm CPU
                    continue
                else:
                    # Đã hết thời gian cooldown: nhả cờ triggered để đánh giá lại
                    logger.debug(
                        "Track %d đã hết thời gian cooldown (%.1fs >= %.1fs), reset để xác thực lại",
                        track.track_id,
                        now - last_time,
                        cooldown_sec,
                    )
                    track.triggered = False
                    track.verify_history.clear()

            # 2. Gọi verify_face (B6) cho khuôn mặt đủ điều kiện (xử lý độc lập cho từng khuôn mặt)
            face_dict = track.to_face_dict()
            v_res = verify_face(db, frame, face_dict)

            # Giữ 5 kết quả gần nhất của mỗi mặt đang theo dõi
            track.verify_history.append(v_res)
            if len(track.verify_history) > 5:
                track.verify_history.pop(0)

            # 3. Đánh giá điều kiện ra quyết định chính thức:
            is_granted = False
            is_inactive = False
            is_stranger = False
            final_res = None
            target_user_id = None

            # a) Kiểm tra Granted: Có 2 kết quả liên tiếp cùng một cư dân đều đạt
            for i in range(len(track.verify_history) - 1):
                r_a = track.verify_history[i]
                r_b = track.verify_history[i + 1]
                u_a = r_a.get("user")
                u_b = r_b.get("user")
                u_a_id = u_a.get("id") if isinstance(u_a, dict) else getattr(u_a, "id", None)
                u_b_id = u_b.get("id") if isinstance(u_b, dict) else getattr(u_b, "id", None)

                if (
                    r_a.get("decision") == "granted"
                    and r_b.get("decision") == "granted"
                    and u_b_id is not None
                    and u_a_id == u_b_id
                ):
                    is_granted = True
                    final_res = r_b
                    target_user_id = u_b_id
                    break

                # b) Kiểm tra Inactive: 2 kết quả liên tiếp báo inactive_user cùng một người
                elif (
                    r_a.get("reason") == "inactive_user"
                    and r_b.get("reason") == "inactive_user"
                    and u_b_id is not None
                    and u_a_id == u_b_id
                ):
                    is_inactive = True
                    final_res = r_b
                    target_user_id = u_b_id
                    break

            # c) Kiểm tra Người lạ (Stranger/Spoof): khi không phải cư dân và có ít nhất 3/5 kết quả denied
            if not is_granted and not is_inactive:
                denied_results = [r for r in track.verify_history if r.get("decision") == "denied"]
                if len(track.verify_history) >= 3 and len(denied_results) >= STRANGER_MIN_DENIED:
                    is_stranger = True
                    final_res = track.verify_history[-1]

            # 4. Kiểm tra cooldown trước khi đưa vào hàng chờ phát sự kiện
            if final_res is not None and (is_granted or is_inactive or is_stranger):
                # - Cư dân (granted/inactive): khóa GRANTED_COOLDOWN_S theo user_id
                if is_granted or is_inactive:
                    if target_user_id is not None:
                        last_resident_event = self._resident_cooldown.get(target_user_id, 0.0)
                        if (now - last_resident_event) < GRANTED_COOLDOWN_S:
                            logger.debug(
                                "Cư dân %d đang trong thời gian cooldown %ds (còn %.1fs), bỏ qua báo lặp",
                                target_user_id,
                                int(GRANTED_COOLDOWN_S),
                                GRANTED_COOLDOWN_S - (now - last_resident_event),
                            )
                            track.triggered = True
                            track.last_triggered_at = now
                            track.user_id = target_user_id
                            track.last_decision = "granted" if is_granted else "inactive_user"
                            continue

                # - Người lạ (stranger/spoof): nghỉ STRANGER_REST_S sau mỗi lần cảnh báo
                elif is_stranger:
                    if (now - self._last_stranger_alert_at) < STRANGER_REST_S:
                        logger.debug(
                            "Cảnh báo người lạ đang trong thời gian nghỉ %ds (còn %.1fs), bỏ qua báo lặp",
                            int(STRANGER_REST_S),
                            STRANGER_REST_S - (now - self._last_stranger_alert_at),
                        )
                        track.triggered = True
                        track.last_triggered_at = now
                        track.last_decision = "stranger"
                        continue

                # CP-05: Đưa vào danh sách chờ xử lý kèm mức ưu tiên:
                # Người lạ ưu tiên cao nhất (priority 0), inactive (priority 1), granted (priority 2)
                decision_type = "stranger" if is_stranger else ("inactive" if is_inactive else "granted")
                priority = 0 if is_stranger else (1 if is_inactive else 2)
                pending_actions.append((priority, track, final_res, decision_type, target_user_id))

        if not pending_actions:
            return

        # CP-05: Sắp xếp các sự kiện theo thứ tự ưu tiên: Cảnh báo người lạ luôn được phát trước!
        pending_actions.sort(key=lambda item: item[0])

        for priority, track, final_res, decision_type, target_user_id in pending_actions:
            # 5. QUAN TRỌNG: Chỉ ghi ĐÚNG 1 dòng access_logs khi thực sự phát sự kiện
            log_entry = record_access(db, final_res)
            log_time = log_entry.timestamp if (log_entry and log_entry.timestamp) else datetime.now()

            # Dựng thông báo announcement (display và spoken) cùng thời điểm với log
            ann = announcement(final_res, when=log_time)

            # Dựng payload access_result đúng hợp đồng API_CONTRACT
            access_result_data = {
                "user": final_res.get("user"),
                "decision": final_res.get("decision"),
                "reason": final_res.get("reason"),
                "similarity": final_res.get("similarity"),
                "box": [int(v) for v in track.bbox],
                "timestamp": log_time.isoformat() if hasattr(log_time, "isoformat") else str(log_time),
                "announcement": ann,
            }

            # Phát sự kiện qua WebSocket và callback
            self._emit_event("access_result", access_result_data)
            self._last_event_at = now

            # Cập nhật thời điểm cooldown (CP-04, CP-05)
            if decision_type in ("granted", "inactive"):
                if target_user_id is not None:
                    self._resident_cooldown[target_user_id] = now
                    track.user_id = target_user_id
                    track.last_decision = decision_type
            elif decision_type == "stranger":
                self._last_stranger_alert_at = now
                track.last_decision = "stranger"

            # Đánh dấu đã kích hoạt cho track này
            track.triggered = True
            track.last_triggered_at = now

            logger.info(
                "Đã kích hoạt sự kiện access_result (ưu tiên=%s, p=%d): decision=%s, reason=%s, user=%s (Track %d)",
                decision_type,
                priority,
                final_res.get("decision"),
                final_res.get("reason"),
                final_res.get("user", {}).get("full_name") if final_res.get("user") else "None",
                track.track_id,
            )

    def _worker(self) -> None:
        """Vòng lặp thực thi của luồng nền."""
        logger.info("Bắt đầu vòng lặp worker AutoVerifyService.")
        camera = get_camera()

        # Đảm bảo GalleryCache đã được nạp nếu service chạy độc lập
        try:
            from services.gallery_cache import get_gallery_cache
            cache = get_gallery_cache()
            if cache.stats().get("total_users", 0) == 0:
                cache.reload()
                logger.info("AutoVerifyService đã tự động nạp GalleryCache: %s", cache.stats())
        except Exception as cache_err:
            logger.debug("Tự động nạp GalleryCache trong worker: %s", cache_err)

        while not self._stop_event.is_set():
            loop_start = time.perf_counter()

            try:
                # 1. Kiểm tra cờ tạm dừng AI (khi B5 đang quay video đăng ký)
                if ai_control.is_ai_paused():
                    self._stop_event.wait(timeout=0.2)
                    continue

                # 2. Xác định tần số mục tiêu (Idle 3 fps hoặc Active 6 fps)
                now = time.time()
                time_since_face = now - self._last_face_seen_time
                if self._last_face_seen_time > 0 and time_since_face <= IDLE_TIMEOUT_SEC:
                    target_fps = AI_FPS_ACTIVE
                    self._is_idle = False
                else:
                    target_fps = AI_FPS_IDLE
                    self._is_idle = True

                target_interval = 1.0 / target_fps

                # 3. Lấy khung hình mới nhất từ camera
                t_frame, frame = camera.latest()

                # Bỏ qua nếu camera chưa có khung hoặc khung này đã được xử lý rồi
                if frame is None or t_frame is None or t_frame <= self._last_processed_time:
                    self._stop_event.wait(timeout=min(0.05, target_interval))
                    continue

                self._last_processed_time = t_frame

                # 4. Tạo Session DB riêng cho mỗi lượt và giải phóng an toàn trong finally
                db = SessionLocal()
                try:
                    # Phát hiện các khuôn mặt trong khung hình
                    faces = detect_faces(frame)

                    if faces:
                        self._last_face_seen_time = time.time()
                        self._is_idle = False

                        # CP-02: Cập nhật tracker và kiểm tra điều kiện kích hoạt
                        with self._lock:
                            ready_tracks = self._update_tracker(frame, faces, now)

                        # CP-03: Thực hiện xác thực cho các track đã sẵn sàng
                        if ready_tracks:
                            with self._lock:
                                self._process_verification(db, frame, ready_tracks, now)
                    else:
                        # Khi không có khuôn mặt trong khung: xóa trạng thái theo dõi
                        with self._lock:
                            if self._tracked_faces:
                                self._tracked_faces.clear()

                finally:
                    db.close()

                # 5. Cập nhật thống kê FPS thực tế
                self._fps_count += 1
                fps_elapsed = now - self._fps_start_time
                if fps_elapsed >= 1.0:
                    with self._lock:
                        self._actual_fps = self._fps_count / fps_elapsed
                    self._fps_count = 0
                    self._fps_start_time = now

            except Exception as e:
                # Đảm bảo vòng lặp không bao giờ chết âm thầm vì ngoại lệ
                logger.error("Lỗi trong vòng lặp auto_verify: %s", e, exc_info=True)

            # 6. Điều tiết thời gian ngủ để duy trì đúng tần số target_fps
            loop_duration = time.perf_counter() - loop_start
            sleep_needed = target_interval - loop_duration
            if sleep_needed > 0.001:
                self._stop_event.wait(timeout=sleep_needed)

        logger.info("Vòng lặp worker AutoVerifyService đã kết thúc.")


# Singleton toàn cục
_auto_verify_service = AutoVerifyService()


def get_auto_verify_service() -> AutoVerifyService:
    return _auto_verify_service


def start() -> None:
    _auto_verify_service.start()


def stop() -> None:
    _auto_verify_service.stop()


def status() -> Dict[str, Any]:
    return _auto_verify_service.status()


def is_running() -> bool:
    return _auto_verify_service.is_running()


def set_event_callback(callback: Optional[Callable[[str, dict], None]]) -> None:
    _auto_verify_service.set_event_callback(callback)
