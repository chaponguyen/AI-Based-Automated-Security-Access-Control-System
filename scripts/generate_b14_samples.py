# Script sinh 10 câu mẫu nghiệm thu âm thanh loa thông báo B14 CP-09
import os
import sys
import time
import ctypes
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from services.speaker_text import announcement
from services.speaker_service import synthesize_edge_tts, SPEAK_VOICE_ID

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT_DIR, "out")
os.makedirs(OUT_DIR, exist_ok=True)


def get_mp3_duration_ms(file_path: str) -> float:
    """Lấy thời lượng file mp3 (mili-giây) qua Windows MCI."""
    alias = f"dur_{int(time.time() * 1000)}"
    ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
    res = ctypes.windll.winmm.mciSendStringW(f'open "{file_path}" type mpegvideo alias {alias}', None, 0, None)
    if res != 0:
        return 0.0
    try:
        # Đặt định dạng thời gian là milliseconds
        ctypes.windll.winmm.mciSendStringW(f'set {alias} time format milliseconds', None, 0, None)
        buf = ctypes.create_unicode_buffer(128)
        ctypes.windll.winmm.mciSendStringW(f'status {alias} length', buf, 128, None)
        val = buf.value.strip()
        return float(val) if val.isdigit() else 0.0
    finally:
        ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)


SAMPLES = [
    # 1. Nguyễn Văn An, A-1203, 09:35
    {
        "id": 1,
        "result": {"user": {"full_name": "Nguyễn Văn An", "apartment_number": "A-1203"}, "decision": "granted", "reason": "ok"},
        "dt": datetime(2026, 10, 26, 9, 35),
        "desc": "Cư dân chuẩn: tên 3 từ, căn hộ tầng 12, giờ 09:35",
    },
    # 2. Trần Thị Bình, B-0807, 09:05
    {
        "id": 2,
        "result": {"user": {"full_name": "Trần Thị Bình", "apartment_number": "B-0807"}, "decision": "granted", "reason": "ok"},
        "dt": datetime(2026, 10, 26, 9, 5),
        "desc": "Cư dân căn hộ B-0807, phút linh (09:05)",
    },
    # 3. Lê Minh Châu, C-502, 12:30
    {
        "id": 3,
        "result": {"user": {"full_name": "Lê Minh Châu", "apartment_number": "C-502"}, "decision": "granted", "reason": "ok"},
        "dt": datetime(2026, 10, 26, 12, 30),
        "desc": "Căn hộ 3 chữ số C-502 (tầng 5 phòng 02), giờ trưa 12:30",
    },
    # 4. Phạm Gia Huy, A-1203, 00:00
    {
        "id": 4,
        "result": {"user": {"full_name": "Phạm Gia Huy", "apartment_number": "A-1203"}, "decision": "granted", "reason": "ok"},
        "dt": datetime(2026, 10, 26, 0, 0),
        "desc": "Giờ nửa đêm (00:00 đọc 'không giờ đúng')",
    },
    # 5. Đặng Thị Hồng Nhung, B-0807, 23:59
    {
        "id": 5,
        "result": {"user": {"full_name": "Đặng Thị Hồng Nhung", "apartment_number": "B-0807"}, "decision": "granted", "reason": "ok"},
        "dt": datetime(2026, 10, 26, 23, 59),
        "desc": "Tên 4 từ dài, giờ khuya 23:59 (năm mươi chín phút)",
    },
    # 6. Nguyễn Văn An (không có phòng), 12:30
    {
        "id": 6,
        "result": {"user": {"full_name": "Nguyễn Văn An", "apartment_number": None}, "decision": "granted", "reason": "ok"},
        "dt": datetime(2026, 10, 26, 12, 30),
        "desc": "Biên: Cư dân chưa cập nhật căn hộ (bỏ cụm 'ở phòng')",
    },
    # 7. Trần Thị Bình, B-0807, inactive_user
    {
        "id": 7,
        "result": {"user": {"full_name": "Trần Thị Bình", "apartment_number": "B-0807"}, "decision": "denied", "reason": "inactive_user"},
        "dt": datetime(2026, 10, 26, 14, 15),
        "desc": "Cư dân bị tạm khóa thẻ/quyền ra vào có số phòng",
    },
    # 8. Lê Minh Châu, inactive_user (không phòng)
    {
        "id": 8,
        "result": {"user": {"full_name": "Lê Minh Châu", "apartment_number": ""}, "decision": "denied", "reason": "inactive_user"},
        "dt": datetime(2026, 10, 26, 14, 20),
        "desc": "Cư dân bị tạm khóa thẻ/quyền ra vào không số phòng",
    },
    # 9. Người lạ (not_matched)
    {
        "id": 9,
        "result": {"user": None, "decision": "denied", "reason": "not_matched"},
        "dt": datetime(2026, 10, 26, 15, 0),
        "desc": "Cảnh báo khẩn cấp người lạ ngoài chung cư",
    },
    # 10. Giả mạo (spoof_detected)
    {
        "id": 10,
        "result": {"user": None, "decision": "denied", "reason": "spoof_detected"},
        "dt": datetime(2026, 10, 26, 15, 5),
        "desc": "Cảnh báo khẩn cấp phát hiện khuôn mặt giả mạo",
    },
]


def main():
    print("=== B14 CP-09: TỔNG HỢP VÀ ĐO ĐẠC 10 CÂU MẪU NGHIỆM THU LOA ===")
    print(f"Giọng đọc sử dụng: {SPEAK_VOICE_ID}\n")

    results = []
    max_duration = 0.0
    longest_sample = None

    for s in SAMPLES:
        sid = s["id"]
        ann = announcement(s["result"], when=s["dt"])
        display_text = ann["display"]
        spoken_text = ann["spoken"]
        kind = ann["kind"]

        filename = f"b14_sample_{sid:02d}.mp3"
        filepath = os.path.join(OUT_DIR, filename)

        # Tổng hợp qua edge-tts
        ok = synthesize_edge_tts(spoken_text, filepath, voice=SPEAK_VOICE_ID, timeout_sec=8.0)
        dur_ms = get_mp3_duration_ms(filepath) if ok else 0.0
        dur_sec = dur_ms / 1000.0

        if dur_sec > max_duration:
            max_duration = dur_sec
            longest_sample = (sid, spoken_text, dur_sec)

        results.append({
            "id": sid,
            "desc": s["desc"],
            "display": display_text,
            "spoken": spoken_text,
            "file": filename,
            "duration": dur_sec,
            "ok": ok,
        })

        print(f"[{sid:02d}] {s['desc']}")
        print(f"     Display : \"{display_text}\"")
        print(f"     Spoken  : \"{spoken_text}\"")
        print(f"     File    : out/{filename} ({dur_sec:.2f}s)")
        print()

    print("=" * 70)
    print(f"TỔNG KẾT ĐO ĐẠC:")
    print(f"- Số câu đã tổng hợp: {len(results)}/10")
    if longest_sample:
        print(f"- Câu có thời gian đọc dài nhất: Mẫu [{longest_sample[0]:02d}] ({longest_sample[2]:.2f} giây)")
        print(f"  Nội dung: \"{longest_sample[1]}\"")
    print("=" * 70)


if __name__ == "__main__":
    main()
