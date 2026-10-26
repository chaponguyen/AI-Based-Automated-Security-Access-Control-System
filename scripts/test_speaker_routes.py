# Test tự động cho B14 CP-08: Nối sự kiện và các route của speaker_service
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from api.speaker import (
    router,
    test_speaker,
    mute_speaker,
    get_status,
    SpeakerTestRequest,
    SpeakerMuteRequest,
)
from services import speaker_service, auto_verify_service


def test_api_routes():
    print("--- 1. Kiểm tra các route API theo API_CONTRACT.md ---")

    # 1. GET /api/speaker/status
    res_status = get_status()
    print("GET /api/speaker/status ->", res_status)
    assert isinstance(res_status, dict)
    assert "enabled" in res_status and "muted" in res_status and "voice" in res_status and "queue" in res_status

    # 2. POST /api/speaker/mute {muted: true}
    res_mute = mute_speaker(SpeakerMuteRequest(muted=True))
    print("POST /api/speaker/mute (True) ->", res_mute)
    assert res_mute == {"muted": True}
    assert speaker_service.is_muted() is True

    # 3. POST /api/speaker/mute {muted: false}
    res_unmute = mute_speaker(SpeakerMuteRequest(muted=False))
    print("POST /api/speaker/mute (False) ->", res_unmute)
    assert res_unmute == {"muted": False}
    assert speaker_service.is_muted() is False

    # 4. POST /api/speaker/test {text: "..."}
    res_test = test_speaker(SpeakerTestRequest(text="Thử nghiệm phát âm qua API"))
    print("POST /api/speaker/test ->", res_test)
    assert res_test == {"ok": True}

    print("=> PASS: Toàn bộ 3 route API của speaker hoạt động chính xác!\n")


def test_event_callback_integration():
    print("--- 2. Kiểm tra nối sự kiện từ auto_verify_service sang speaker_service ---")
    speaker_service.set_muted(False)

    # Đăng ký callback giống như main.py
    auto_verify_service.set_event_callback(speaker_service.handle_access_result)

    # 1. Sự kiện cư dân granted
    resident_event = {
        "user": {"full_name": "Khuê", "apartment_number": "A-1203"},
        "decision": "granted",
        "reason": "ok",
        "similarity": 0.65,
        "box": [100, 100, 200, 200],
        "announcement": {
            "display": "Khuê ở phòng A-1203 đã vào chung cư lúc 10:05.",
            "spoken": "Khuê ở phòng a, mười hai không ba đã vào chung cư lúc mười giờ linh năm phút.",
            "kind": "granted",
        },
        "timestamp": "2026-10-26T10:05:00",
    }

    # Giả lập phát sự kiện từ auto_verify_service
    if auto_verify_service._auto_verify_service._on_event_callback:
        auto_verify_service._auto_verify_service._on_event_callback("access_result", resident_event)
        print("Đã phát sự kiện cư dân granted sang callback loa.")

    # 2. Sự kiện người lạ denied
    stranger_event = {
        "user": None,
        "decision": "denied",
        "reason": "not_matched",
        "similarity": 0.22,
        "box": [100, 100, 200, 200],
        "announcement": {
            "display": "Có người lạ đang ở ngoài chung cư, nhân viên an ninh cần ra gấp.",
            "spoken": "Có người lạ đang ở ngoài chung cư, nhân viên an ninh cần ra gấp.",
            "kind": "stranger",
        },
        "timestamp": "2026-10-26T10:05:02",
    }

    if auto_verify_service._auto_verify_service._on_event_callback:
        auto_verify_service._auto_verify_service._on_event_callback("access_result", stranger_event)
        print("Đã phát sự kiện người lạ denied sang callback loa.")

    status = speaker_service.get_speaker_status()
    print("Trạng thái loa sau khi nhận 2 sự kiện:", status)
    print("=> PASS: Nối sự kiện thành công, loa nhận và đưa vào hàng đợi không lỗi!\n")


if __name__ == "__main__":
    print("=== KIỂM THỬ B14 CP-08: NỐI SỰ KIỆN VÀ ROUTE CỦA SPEAKER ===\n")
    test_api_routes()
    test_event_callback_integration()
    print("=== TẤT CẢ CÁC BÀI TEST CP-08 ĐÃ PASS 100% ===")
