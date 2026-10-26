# Agent 2 — Dịch vụ loa thông báo tiếng Việt mạch lạc (B14)
# docs/context/API_CONTRACT.md và docs/plan/MO_TA_CONG_VIEC.md mục B14
import asyncio
import ctypes
import hashlib
import logging
import os
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Cấu hình loa từ biến môi trường
SPEAK_ENABLED = os.getenv("SPEAK_ENABLED", "true").lower() in ("true", "1", "yes")
SPEAK_ENGINE = os.getenv("SPEAK_ENGINE", "edge").strip().lower()  # edge | sapi | piper
SPEAK_VOICE_ID = os.getenv("SPEAK_VOICE_ID", "vi-VN-NamMinhNeural").strip()
SPEAK_RATE = int(os.getenv("SPEAK_RATE", "170"))
SPEAK_VOLUME = float(os.getenv("SPEAK_VOLUME", "1.0"))
ALERT_REPEAT = int(os.getenv("ALERT_REPEAT", "2"))
DEDUP_SECONDS = float(os.getenv("DEDUP_SECONDS", "5.0"))

# Đường dẫn thư mục lưu đệm âm thanh
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_TTS_DIR = os.path.join(ROOT_DIR, "backend", "ai", "weights", "tts")
OUT_TTS_DIR = os.path.join(ROOT_DIR, "out", "tts")

os.makedirs(WEIGHTS_TTS_DIR, exist_ok=True)
os.makedirs(OUT_TTS_DIR, exist_ok=True)

# Câu cảnh báo người lạ cố định (tiền tổng hợp vào weights/tts/ để dùng ngay kể cả khi mất mạng)
STRANGER_ALERT_TEXT = "Có người lạ đang ở ngoài chung cư, bảo vệ cần ra gấp."
STRANGER_CACHE_FILE = os.path.join(WEIGHTS_TTS_DIR, "alert_stranger.mp3")

_cached_vietnamese_voice: Optional[str] = None
_voice_checked: bool = False

# Quản lý phát âm thanh MCI
_current_alias: Optional[str] = None
_mci_lock = threading.Lock()
_stop_playback_flag = False


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
        # Đóng alias cũ nếu còn
        ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)
        open_cmd = f'open "{mp3_path}" type mpegvideo alias {alias}'
        res = ctypes.windll.winmm.mciSendStringW(open_cmd, None, 0, None)
        if res != 0:
            logger.warning("Không thể mở file MP3 qua MCI: mã lỗi %s, đường dẫn %s", res, mp3_path)
            _current_alias = None
            return False

    try:
        # Bắt đầu phát không chặn
        play_cmd = f"play {alias}"
        res = ctypes.windll.winmm.mciSendStringW(play_cmd, None, 0, None)
        if res != 0:
            logger.warning("Không thể phát MP3 qua MCI: mã lỗi %s", res)
            return False

        # Vòng lặp chờ phát xong, cho phép ngắt ngay khi có yêu cầu dừng
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

    # Đảm bảo chữ tiếng Việt có dấu được truyền nguyên vẹn qua đối tượng Python
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
        if os.path.exists(STRANGER_CACHE_FILE) and os.path.getsize(STRANGER_CACHE_FILE) > 1000:
            logger.debug("Đã có cache câu cảnh báo người lạ tại %s", STRANGER_CACHE_FILE)
            return True

        logger.info("Tiền tổng hợp câu cảnh báo người lạ vào cache...")
        voice = SPEAK_VOICE_ID or "vi-VN-NamMinhNeural"
        ok = synthesize_edge_tts(STRANGER_ALERT_TEXT, STRANGER_CACHE_FILE, voice=voice, timeout_sec=8.0)
        if ok:
            logger.info("Tiền tổng hợp câu cảnh báo người lạ thành công (%s bytes)", os.path.getsize(STRANGER_CACHE_FILE))
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
    """
    if not SPEAK_ENABLED:
        logger.debug("Loa đang tắt (SPEAK_ENABLED=false)")
        return False

    if not text or not str(text).strip():
        return False

    text_clean = str(text).strip()

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
            if os.path.exists(STRANGER_CACHE_FILE) and os.path.getsize(STRANGER_CACHE_FILE) > 1000:
                audio_file = STRANGER_CACHE_FILE

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
            if _stop_playback_flag:
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
        ok = _speak_sapi5(text_clean, voice)
        if not ok:
            ok = _speak_sapi5(text_clean, voice)
        if not ok:
            success = False

    return success


# Tiền tổng hợp câu cảnh báo người lạ trong background thread khi nạp module
threading.Thread(target=preload_alert_cache, daemon=True, name="preload_alert_tts").start()
