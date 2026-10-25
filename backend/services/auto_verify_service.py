# Agent 2 — Vòng lặp tự động xác thực khuôn mặt chạy nền (B12 CP-01, CP-02)
import time
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple
import numpy as np

from database.database import SessionLocal
from services.camera_service import get_camera
from services import ai_control
from ai.detector import detect_faces
from ai.quality import frame_quality

logger = logging.getLogger(__name__)

# ==================== CẤU HÌNH THAM SỐ VÒNG LẶP ====================
AI_FPS_ACTIVE = 6.0         # Tốc độ tối đa khi có mặt hoặc vừa thấy mặt (khung/giây)
AI_FPS_IDLE = 3.0           # Tốc độ khi không có mặt trong 5 giây (khung/giây)
IDLE_TIMEOUT_SEC = 5.0      # Thời gian không thấy mặt để chuyển sang chế độ tiết kiệm CPU

# Cấu hình điều kiện kích hoạt xác thực (CP-02)
MIN_FACE_PX_VERIFY = 110    # Cạnh ngắn tối thiểu của bbox để kích hoạt xác thực (110 px)
STABLE_FRAMES_REQUIRED = 3  # Số khung hình liên tiếp ổn định (~0.5 giây ở 6 fps)
IOU_THRESHOLD = 0.5         # Ngưỡng IoU để liên kết theo dõi cùng một khuôn mặt

# Cấu hình chống báo lặp (CP-04)
RESIDENT_COOLDOWN_SEC = 60.0  # Chống báo lặp cho cư dân granted (giây)
STRANGER_COOLDOWN_SEC = 15.0  # Thời gian nghỉ sau khi cảnh báo người lạ (giây)
STRANGER_MIN_DENIED = 3       # Số lần denied trong 5 kết quả gần nhất để cảnh báo người lạ


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

        # Số khung hình liên tiếp đạt chất lượng và kích thước
        self.stable_count: int = 1 if is_qualified else 0
        self.is_qualified: bool = is_qualified
        self.ready_to_verify: bool = (self.stable_count >= STABLE_FRAMES_REQUIRED)

        # Trạng thái và lịch sử (chuẩn bị cho CP-03..CP-05)
        self.verify_history: List[dict] = []
        self.triggered: bool = False
        self.last_triggered_at: Optional[float] = None

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
    - Điều kiện kích hoạt:
      + Cạnh ngắn bbox >= MIN_FACE_PX_VERIFY (110 px).
      + frame_quality đạt (không mờ, không nghiêng quá mức, không quá sáng/tối).
      + Xuất hiện ổn định liên tiếp STABLE_FRAMES_REQUIRED = 3 khung (~0.5s).
    - Người đi ngang nhanh hoặc đứng xa sẽ không kích hoạt xác thực.
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

    def _worker(self) -> None:
        """Vòng lặp thực thi của luồng nền."""
        logger.info("Bắt đầu vòng lặp worker AutoVerifyService.")
        camera = get_camera()

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

                        if ready_tracks:
                            for track in ready_tracks:
                                logger.debug(
                                    "Track %d sẵn sàng xác thực (stable=%d, edge=%.1f)",
                                    track.track_id,
                                    track.stable_count,
                                    track.short_edge(),
                                )
                    else:
                        # Khi không có khuôn mặt trong khung: xóa trạng thái theo dõi
                        with self._lock:
                            if self._tracked_faces:
                                self._tracked_faces.clear()

                    # (Các bước CP-03..CP-05 sẽ tiếp tục phát triển ở đây)
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
