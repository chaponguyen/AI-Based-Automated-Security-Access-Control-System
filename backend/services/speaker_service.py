# Agent 2 — Dịch vụ loa thông báo tiếng Việt mạch lạc (B14)
# docs/context/API_CONTRACT.md và docs/plan/MO_TA_CONG_VIEC.md mục B14
import asyncio
import ctypes
from dataclasses import dataclass, field
import hashlib
import logging
import os
import subprocess
import threading
import time
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Cấu hình loa từ biến môi trường
SPEAK_ENABLED = os.getenv("SPEAK_ENABLED", "true").lower() in ("true", "1", "yes")
SPEAK_ENGINE = os.getenv("SPEAK_ENGINE", "edge").strip().lower()  # edge | sapi | piper
SPEAK_VOICE_ID = os.getenv("SPEAK_VOICE_ID", "vi-VN-NamMinhNeural").strip()
SPEAK_RATE = int(os.getenv("SPEAK_RATE", "170"))
SPEAK_VOLUME = float(os.getenv("SPEAK_VOLUME", "1.0"))
ALERT_REPEAT = int(os.getenv("ALERT_REPEAT", "2"))
DEDUP_SECONDS = float(os.getenv("DEDUP_SECONDS", "5.0"))
MAX_QUEUE_SIZE = 5

# Đường dẫn thư mục lưu đệm âm thanh
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_TTS_DIR = os.path.join(ROOT_DIR, "backend", "ai", "weights", "tts")
OUT_TTS_DIR = os.path.join(ROOT_DIR, "out", "tts")

os.makedirs(WEIGHTS_TTS_DIR, exist_ok=True)
os.makedirs(OUT_TTS_DIR, exist_ok=True)

# Câu cảnh báo người lạ cố định (tiền tổng hợp vào weights/tts/ để dùng ngay kể cả khi mất mạng)
STRANGER_ALERT_TEXT = "Có người lạ đang ở ngoài chung cư, nhân viên an ninh cần ra gấp."


def get_alert_cache_path(text: Optional[str] = None, voice: Optional[str] = None, rate: Optional[int] = None) -> str:
    """Tạo đường dẫn file đệm âm thanh cố định trong weights/tts/ dựa trên băm của (văn bản, giọng, tốc độ)."""
    t = text if text is not None else STRANGER_ALERT_TEXT
    v = voice or SPEAK_VOICE_ID or "vi-VN-NamMinhNeural"
    r = rate if rate is not None else SPEAK_RATE
    cache_key = hashlib.md5(f"{t}_{v}_{r}".encode("utf-8")).hexdigest()
    return os.path.join(WEIGHTS_TTS_DIR, f"alert_{cache_key}.mp3")


STRANGER_CACHE_FILE = get_alert_cache_path()

_cached_vietnamese_voice: Optional[str] = None
_voice_checked: bool = False

# Quản lý phát âm thanh MCI
_current_alias: Optional[str] = None
_mci_lock = threading.Lock()
_stop_playback_flag = False
_engine_lock = threading.Lock()
_shutdown_worker = False


@dataclass
class SpeakerTask:
    priority: int                   # 0: cảnh báo người lạ (cao nhất), 1: thông báo cư dân, 2: test/khác
    timestamp: float                # thời điểm đưa vào hàng đợi
    text: str                       # nội dung cần đọc
    is_alert: bool                  # True: cảnh báo người lạ
    voice: Optional[str] = None     # Giọng ghi đè (nếu có)
    enqueued_at: float = field(default_factory=time.time)


class SpeakerQueue:
    """Hàng đợi một luồng có độ ưu tiên, giới hạn tối đa 5 mục (CP-07)."""

    def __init__(self, maxsize: int = MAX_QUEUE_SIZE):
        self.maxsize = maxsize
        self._items: List[SpeakerTask] = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._muted = False
        self._last_spoken_text: str = ""
        self._last_spoken_time: float = 0.0

    def put(self, task: SpeakerTask) -> bool:
        """Thêm task vào hàng đợi. Không chặn caller. Trả về True nếu được nhận, False nếu bị bỏ."""
        with self._condition:
            if self._muted or not SPEAK_ENABLED:
                logger.debug("Bỏ qua task vì loa đang tắt hoặc mute: '%s'", task.text)
                return False

            # Chống lặp DEDUP: Câu giống hệt vừa đọc trong DEDUP_SECONDS thì bỏ
            now = time.time()
            if task.text == self._last_spoken_text and (now - self._last_spoken_time) < DEDUP_SECONDS:
                logger.debug("DEDUP: Bỏ qua câu giống hệt vừa đọc trong %.1fs: '%s'", DEDUP_SECONDS, task.text)
                return False

            # Chống lặp câu đang nằm trong hàng đợi chờ đọc
            for it in self._items:
                if it.text == task.text:
                    logger.debug("DEDUP: Câu '%s' đã có trong hàng đợi, bỏ qua.", task.text)
                    return False

            # Hàng đợi tối đa 5 mục: nếu đầy thì bỏ mục ưu tiên thấp nhất cũ nhất
            if len(self._items) >= self.maxsize:
                worst_idx = -1
                worst_prio = -1
                worst_time = float("inf")
                for i, it in enumerate(self._items):
                    # priority lớn hơn nghĩa là ưu tiên kém hơn
                    if it.priority > worst_prio or (it.priority == worst_prio and it.timestamp < worst_time):
                        worst_prio = it.priority
                        worst_time = it.timestamp
                        worst_idx = i

                # Nếu task mới có ưu tiên còn thấp hơn mục kém nhất hiện tại
                if task.priority > worst_prio:
                    logger.warning("Hàng đợi loa đầy (5 mục) và task mới có ưu tiên thấp hơn, bỏ qua: '%s'", task.text)
                    return False

                dropped = self._items.pop(worst_idx)
                logger.warning(
                    "Hàng đợi loa đầy (5 mục), loại bỏ mục ưu tiên thấp nhất cũ nhất: '%s' (prio=%d)",
                    dropped.text, dropped.priority
                )

            self._items.append(task)
            self._condition.notify()
            return True

    def get(self, timeout: float = 1.0) -> Optional[SpeakerTask]:
        """Lấy task có độ ưu tiên cao nhất (priority nhỏ nhất, FIFO khi cùng priority)."""
        with self._condition:
            while len(self._items) == 0:
                if _shutdown_worker:
                    return None
                self._condition.wait(timeout=timeout)
                if _shutdown_worker:
                    return None

            if self._muted:
                self._items.clear()
                return None

            # Tìm mục có priority nhỏ nhất, nếu bằng nhau thì timestamp nhỏ nhất
            best_idx = 0
            best_task = self._items[0]
            for i in range(1, len(self._items)):
                it = self._items[i]
                if (it.priority, it.timestamp) < (best_task.priority, best_task.timestamp):
                    best_task = it
                    best_idx = i

            return self._items.pop(best_idx)

    def clear(self):
        """Xóa toàn bộ hàng đợi."""
        with self._condition:
            self._items.clear()
            self._condition.notify_all()

    def set_muted(self, muted: bool):
        """Cập nhật cờ mute. Nếu muted=True thì xóa sạch hàng đợi."""
        with self._condition:
            self._muted = bool(muted)
            if self._muted:
                self._items.clear()
            self._condition.notify_all()

    def is_muted(self) -> bool:
        with self._lock:
            return self._muted

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def record_spoken(self, text: str):
        """Ghi nhận câu đã đọc thành công để phục vụ dedup."""
        with self._lock:
            self._last_spoken_text = text
            self._last_spoken_time = time.time()


_speaker_queue = SpeakerQueue(maxsize=MAX_QUEUE_SIZE)


def find_vietnamese_voice() -> Optional[str]:
    """Tìm giọng tiếng Việt trên hệ thống Windows SAPI5 / OneCore."""
    global _cached_vietnamese_voice, _voice_checked
    if _voice_checked:
        return _cached_vietnamese_voice

    _voice_checked = True

    # Nếu đang dùng edge-tts thì ưu tiên giọng đã cấu hình
    if SPEAK_ENGINE == "edge":
        _cached_vietnamese_voice = SPEAK_VOICE_ID or "vi-VN-NamMinhNeural"
        return _cached_vietnamese_voice

    # Nếu đã cấu hình sẵn trong .env
    if SPEAK_VOICE_ID:
        _cached_vietnamese_voice = SPEAK_VOICE_ID
        return _cached_vietnamese_voice

    # Dò qua PowerShell System.Speech
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.GetInstalledVoices() | ForEach-Object { "
        "$v = $_.VoiceInfo; "
        "if ($v.Culture.Name -like '*vi*' -or $v.Name -like '*vietnam*' -or $v.Name -like '*An*' -or $v.Name -like '*HoaiMy*' -or $v.Name -like '*NamMinh*') { "
        "$v.Name "
        "} }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            first_voice = r.stdout.strip().splitlines()[0].strip()
            if first_voice:
                _cached_vietnamese_voice = first_voice
                return _cached_vietnamese_voice
    except Exception as e:
        logger.debug("Lỗi khi dò giọng tiếng Việt: %s", e)

    _cached_vietnamese_voice = None
    return None


def play_beep(freq: int = 1000, duration_ms: int = 150, count: int = 1):
    """Phát tiếng bíp bằng winsound trên Windows."""
    try:
        import winsound
        for _ in range(count):
            winsound.Beep(freq, duration_ms)
            if count > 1:
                time.sleep(0.05)
    except Exception:
        pass


def stop_playback():
    """Dừng phát âm thanh ngay lập tức (nút Tắt loa hoặc chuyển sự kiện)."""
    global _stop_playback_flag, _current_alias
    _stop_playback_flag = True
    with _mci_lock:
        if _current_alias:
            try:
                ctypes.windll.winmm.mciSendStringW(f"stop {_current_alias}", None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f"close {_current_alias}", None, 0, None)
            except Exception:
                pass
            _current_alias = None


def _play_mp3_mci(mp3_path: str, timeout_sec: float = 15.0) -> bool:
    """Phát file MP3 qua Windows Multimedia API (MCI) không cần thêm thư viện ngoài."""
    global _current_alias, _stop_playback_flag
    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < 100:
        return False

    alias = f"tts_{int(time.time() * 1000)}_{threading.get_ident()}"
    with _mci_lock:
        _stop_playback_flag = False
        _current_alias = alias
        ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)
        open_cmd = f'open "{mp3_path}" type mpegvideo alias {alias}'
        res = ctypes.windll.winmm.mciSendStringW(open_cmd, None, 0, None)
        if res != 0:
            logger.warning("Không thể mở file MP3 qua MCI: mã lỗi %s, đường dẫn %s", res, mp3_path)
            _current_alias = None
            return False

    try:
        play_cmd = f"play {alias}"
        res = ctypes.windll.winmm.mciSendStringW(play_cmd, None, 0, None)
        if res != 0:
            logger.warning("Không thể phát MP3 qua MCI: mã lỗi %s", res)
            return False

        start_t = time.time()
        buf = ctypes.create_unicode_buffer(128)
        while not _stop_playback_flag:
            if time.time() - start_t > timeout_sec:
                break
            ctypes.windll.winmm.mciSendStringW(f"status {alias} mode", buf, 128, None)
            if buf.value != "playing":
                break
            time.sleep(0.04)

        return not _stop_playback_flag
    finally:
        with _mci_lock:
            try:
                ctypes.windll.winmm.mciSendStringW(f"stop {alias}", None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)
            except Exception:
                pass
            if _current_alias == alias:
                _current_alias = None


async def _async_edge_communicate(text: str, output_path: str, voice: str, rate_val: int) -> bool:
    """Gọi edge_tts.Communicate trong Python để giữ nguyên tiếng Việt có dấu."""
    import edge_tts

    rate_str = "+0%"
    if rate_val != 170:
        pct = int((rate_val - 170) / 170 * 100)
        rate_str = f"{pct:+d}%"

    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_path)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 100


def synthesize_edge_tts(text: str, output_path: str, voice: Optional[str] = None, timeout_sec: float = 8.0) -> bool:
    """Tổng hợp giọng đọc tiếng Việt qua edge-tts với timeout cứng 8 giây để không treo luồng."""
    if not voice:
        voice = SPEAK_VOICE_ID or "vi-VN-NamMinhNeural"

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        logger.warning("Thư viện edge-tts chưa được cài đặt trong môi trường Python.")
        return False

    try:
        return asyncio.run(
            asyncio.wait_for(
                _async_edge_communicate(text, output_path, voice, SPEAK_RATE),
                timeout=timeout_sec,
            )
        )
    except asyncio.TimeoutError:
        logger.warning("edge-tts tổng hợp giọng đọc bị quá thời gian (timeout %ss): '%s'", timeout_sec, text)
        return False
    except Exception as e:
        logger.warning("edge-tts gặp lỗi khi tổng hợp âm thanh: %s", e)
        return False


def preload_alert_cache() -> bool:
    """Tiền tổng hợp câu cảnh báo người lạ cố định vào weights/tts/ để phát ngay cả khi mạng chập chờn."""
    try:
        cache_file = get_alert_cache_path()
        if os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
            logger.debug("Đã có cache câu cảnh báo người lạ tại %s", cache_file)
            return True

        logger.info("Tiền tổng hợp câu cảnh báo người lạ vào cache...")
        voice = SPEAK_VOICE_ID or "vi-VN-NamMinhNeural"
        ok = synthesize_edge_tts(STRANGER_ALERT_TEXT, cache_file, voice=voice, timeout_sec=8.0)
        if ok:
            logger.info("Tiền tổng hợp câu cảnh báo người lạ thành công (%s bytes)", os.path.getsize(cache_file))
            return True
        logger.warning("Không thể tiền tổng hợp câu cảnh báo người lạ lúc khởi động (mạng chưa sẵn sàng).")
        return False
    except Exception as e:
        logger.warning("Lỗi khi tiền tổng hợp alert cache: %s", e)
        return False


def _speak_sapi5(text: str, voice_name: str) -> bool:
    """Đọc văn bản qua SAPI5 bằng PowerShell (chỉ khi có giọng tiếng Việt SAPI5)."""
    escaped_text = text.replace("'", "''")
    escaped_voice = voice_name.replace("'", "''")
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SelectVoice('{escaped_voice}'); "
        f"$s.Speak('{escaped_text}');"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return r.returncode == 0
    except Exception as e:
        logger.warning("Lỗi phát âm SAPI5: %s", e)
        return False


def speak(text: str, is_alert: bool = False, voice_override: Optional[str] = None) -> bool:
    """Phát âm văn bản qua loa, CHỈ sử dụng giọng tiếng Việt thật (CP-06).

    Quy tắc:
    - Nếu là cảnh báo (is_alert=True): phát 3 tiếng bíp ngắn trước, rồi đọc ALERT_REPEAT lần.
    - Không có giọng tiếng Việt hoặc mất mạng/lỗi: KHÔNG đọc bằng giọng khác để tránh đánh vần;
      ghi log speaker_unavailable, phát tiếng bíp cảnh báo, trả False và thử lại ở câu sau.
    - Giữ timeout cứng 8 giây cho tổng hợp để không treo luồng.
    - Câu cảnh báo người lạ cố định ưu tiên lấy từ cache offline weights/tts/.
    - An toàn luồng: _engine_lock bảo đảm không bao giờ đọc chồng.
    """
    if not SPEAK_ENABLED or _speaker_queue.is_muted():
        logger.debug("Loa đang tắt hoặc mute")
        return False

    if not text or not str(text).strip():
        return False

    text_clean = str(text).strip()

    with _engine_lock:
        if _stop_playback_flag or _speaker_queue.is_muted():
            return False

        # Nếu là cảnh báo người lạ: phát 3 tiếng bíp ngắn trước
        if is_alert:
            play_beep(freq=1200, duration_ms=120, count=3)

        repeats = ALERT_REPEAT if is_alert else 1
        voice = voice_override or find_vietnamese_voice()

        # ==================== ENGINE EDGE-TTS ====================
        if SPEAK_ENGINE == "edge":
            if not voice:
                voice = "vi-VN-NamMinhNeural"

            # 1. Trường hợp câu cảnh báo người lạ: ưu tiên file cache tiền tổng hợp
            audio_file = None
            if text_clean == STRANGER_ALERT_TEXT or is_alert:
                alert_cache = get_alert_cache_path(text_clean, voice, SPEAK_RATE)
                if os.path.exists(alert_cache) and os.path.getsize(alert_cache) > 1000:
                    audio_file = alert_cache

            # 2. Nếu chưa có file cache, tạo file mp3 theo hash md5 nội dung
            if not audio_file:
                text_hash = hashlib.md5(f"{voice}_{SPEAK_RATE}_{text_clean}".encode("utf-8")).hexdigest()
                temp_path = os.path.join(OUT_TTS_DIR, f"{text_hash}.mp3")

                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
                    audio_file = temp_path
                else:
                    ok = synthesize_edge_tts(text_clean, temp_path, voice=voice, timeout_sec=8.0)
                    if ok:
                        audio_file = temp_path

            # 3. Nếu tổng hợp thất bại (mất mạng, lỗi engine): ghi log, phát bíp, trả False
            if not audio_file or not os.path.exists(audio_file):
                logger.warning(
                    "speaker_unavailable: Không thể phát âm thanh tiếng Việt bằng edge-tts (lỗi kết nối hoặc timeout), thử lại ở câu sau."
                )
                play_beep(freq=800, duration_ms=250, count=1)
                return False

            # 4. Phát file MP3 qua MCI
            success = True
            for _ in range(repeats):
                if _stop_playback_flag or _speaker_queue.is_muted():
                    break
                ok = _play_mp3_mci(audio_file)
                if not ok:
                    success = False

            return success

        # ==================== ENGINE SAPI5 ====================
        if not voice:
            logger.warning("speaker_unavailable: Máy chưa cài đặt giọng tiếng Việt, bỏ qua đọc để không đọc sai/đánh vần.")
            play_beep(freq=800, duration_ms=250, count=1)
            return False

        success = True
        for _ in range(repeats):
            if _stop_playback_flag or _speaker_queue.is_muted():
                break
            ok = _speak_sapi5(text_clean, voice)
            if not ok:
                ok = _speak_sapi5(text_clean, voice)
            if not ok:
                success = False

        return success


def _speaker_worker_loop():
    """Luồng đọc riêng biệt của loa (CP-07). Lấy task từ hàng đợi và gọi engine."""
    logger.info("Luồng xử lý loa thông báo một luồng đã khởi chạy.")
    while not _shutdown_worker:
        try:
            task = _speaker_queue.get(timeout=1.0)
            if task is None:
                continue

            if _speaker_queue.is_muted() or not SPEAK_ENABLED:
                continue

            # Đo thời gian từ lúc đưa vào hàng đợi đến lúc bắt đầu phát
            queue_latency_ms = (time.time() - task.enqueued_at) * 1000
            logger.info(
                "Loa bắt đầu phát (độ trễ hàng đợi: %.1f ms, alert=%s, prio=%d): '%s'",
                queue_latency_ms, task.is_alert, task.priority, task.text
            )

            # Chỉ luồng loa được gọi engine
            ok = speak(task.text, is_alert=task.is_alert, voice_override=task.voice)
            if ok:
                _speaker_queue.record_spoken(task.text)
        except Exception as e:
            logger.error("Lỗi trong luồng loa: %s", e, exc_info=True)
            time.sleep(0.1)


# ==================== CÁC HÀM CÔNG KHAI (CP-07) ====================

def enqueue_speak(
    text: str,
    is_alert: bool = False,
    priority: Optional[int] = None,
    voice_override: Optional[str] = None
) -> bool:
    """Đưa câu thông báo vào hàng đợi một luồng cho loa (CP-07). Không chặn vòng lặp AI.

    Quy tắc:
    - Cảnh báo người lạ: priority = 0 (ưu tiên cao nhất).
    - Cư dân / thông báo thường: priority = 1.
    - Không chặn luồng gọi (trả về bool ngay).
    - Câu giống hệt vừa đọc trong DEDUP_SECONDS thì bỏ.
    - Hàng đợi tối đa 5 mục, đầy thì bỏ mục ưu tiên thấp nhất cũ nhất.
    """
    if not text or not str(text).strip():
        return False

    if priority is None:
        priority = 0 if is_alert else 1

    task = SpeakerTask(
        priority=priority,
        timestamp=time.time(),
        text=str(text).strip(),
        is_alert=is_alert,
        voice=voice_override,
        enqueued_at=time.time(),
    )
    return _speaker_queue.put(task)


def set_muted(muted: bool) -> bool:
    """Bật/tắt chế độ im lặng của loa (CP-07).
    Khi muted=True: dừng đọc ngay lập tức và xóa sạch hàng đợi.
    """
    _speaker_queue.set_muted(muted)
    if muted:
        stop_playback()
    logger.info("Chế độ loa: %s", "TẮT TIẾNG (muted=True)" if muted else "BẬT TIẾNG (muted=False)")
    return _speaker_queue.is_muted()


def is_muted() -> bool:
    """Kiểm tra trạng thái loa có đang bị mute hay không."""
    return _speaker_queue.is_muted()


def get_speaker_status() -> Dict[str, Any]:
    """Trả về trạng thái loa theo API_CONTRACT: {enabled, muted, voice, queue}."""
    return {
        "enabled": SPEAK_ENABLED,
        "muted": _speaker_queue.is_muted(),
        "voice": SPEAK_VOICE_ID or find_vietnamese_voice() or "",
        "queue": _speaker_queue.size(),
    }


def handle_access_result(event_name: str, event_data: dict) -> None:
    """Callback nhận sự kiện từ AutoVerifyService (B12) để phát âm qua loa (CP-08).

    Quy tắc:
    - Chỉ xử lý event 'access_result'.
    - Loa chỉ đọc announcement.spoken (giao diện dùng announcement.display).
    - Cảnh báo người lạ: kind == 'stranger' hoặc (denied và reason != 'inactive_user') -> is_alert=True (prio 0).
    - Cư dân granted hoặc inactive: is_alert=False (prio 1).
    - Đưa vào hàng đợi qua enqueue_speak, không chặn vòng lặp AI.
    """
    if event_name != "access_result" or not isinstance(event_data, dict):
        return

    ann = event_data.get("announcement")
    if not isinstance(ann, dict):
        return

    spoken_text = ann.get("spoken")
    if not spoken_text or not str(spoken_text).strip():
        return

    kind = ann.get("kind", "")
    decision = event_data.get("decision", "")
    reason = event_data.get("reason", "")

    is_alert = (kind == "stranger") or (decision == "denied" and reason != "inactive_user")
    priority = 0 if is_alert else 1

    enqueue_speak(str(spoken_text).strip(), is_alert=is_alert, priority=priority)


# Khởi chạy luồng loa nền và tiền tổng hợp cache
threading.Thread(target=preload_alert_cache, daemon=True, name="preload_alert_tts").start()
_speaker_worker_thread = threading.Thread(target=_speaker_worker_loop, daemon=True, name="speaker_worker")
_speaker_worker_thread.start()
