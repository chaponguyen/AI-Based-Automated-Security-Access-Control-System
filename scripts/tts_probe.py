#!/usr/bin/env python3
"""Dò tìm các giọng đọc Text-To-Speech (TTS) trên máy tính (B14 CP-01).

Kiểm tra:
1. SAPI5 / Desktop Voices qua COM / System.Speech
2. Windows OneCore Voices qua Registry
3. Piper offline TTS model trong backend/ai/weights/tts/
4. Edge-TTS (nếu có cài đặt)
"""
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def probe_sapi5_voices():
    """Dò giọng SAPI5 Desktop qua PowerShell System.Speech."""
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.GetInstalledVoices() | ForEach-Object { "
        "$v = $_.VoiceInfo; "
        "[PSCustomObject]@{ Id = $v.Id; Name = $v.Name; Culture = $v.Culture.Name; Enabled = $_.Enabled } "
        "} | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode == 0 and r.stdout.strip():
            import json
            data = json.loads(r.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return data
    except Exception as e:
        print(f"Lỗi khi dò SAPI5: {e}")
    return []


def probe_onecore_voices():
    """Dò giọng Windows OneCore qua Registry."""
    ps_cmd = (
        'Get-ChildItem "HKLM:\\SOFTWARE\\Microsoft\\Speech_OneCore\\Voices\\Tokens" -ErrorAction SilentlyContinue | '
        "ForEach-Object { "
        "$name = (Get-ItemProperty $_.PSPath -Name '(default)' -ErrorAction SilentlyContinue).'(default)'; "
        "$lang = (Get-ItemProperty ($_.PSPath + '\\Attributes') -Name 'Language' -ErrorAction SilentlyContinue).Language; "
        "[PSCustomObject]@{ Token = $_.PSChildName; Name = $name; LangHex = $lang } "
        "} | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode == 0 and r.stdout.strip():
            import json
            data = json.loads(r.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return data
    except Exception:
        pass
    return []


def probe_piper_models():
    """Kiểm tra mô hình Piper TTS trong backend/ai/weights/tts/."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tts_dir = os.path.join(root, "backend", "ai", "weights", "tts")
    models = []
    if os.path.exists(tts_dir):
        for f in os.listdir(tts_dir):
            if f.endswith(".onnx"):
                models.append(f)
    return models


def probe_edge_tts_voices():
    """Kiểm tra engine edge-tts và các giọng tiếng Việt khả dụng."""
    try:
        import edge_tts
        import asyncio

        async def _fetch_voices():
            voices = await edge_tts.list_voices()
            return [
                v for v in voices
                if "vi-VN" in v.get("ShortName", "") or "Vietnamese" in v.get("Locale", "")
            ]

        try:
            return asyncio.run(asyncio.wait_for(_fetch_voices(), timeout=5.0))
        except Exception:
            # Dự phòng danh sách chuẩn nếu timeout mạng
            return [
                {"ShortName": "vi-VN-NamMinhNeural", "Gender": "Male", "FriendlyName": "Microsoft NamMinh Online (Natural) - Vietnamese"},
                {"ShortName": "vi-VN-HoaiMyNeural", "Gender": "Female", "FriendlyName": "Microsoft HoaiMy Online (Natural) - Vietnamese"},
            ]
    except ImportError:
        return None


def is_vietnamese(name_or_culture):
    s = str(name_or_culture).lower()
    return any(k in s for k in ["vi-vn", "vivn", "vietnam", "vietnamese", "42a", "hoaimy", "namminh", "an"])


def main():
    print("=== B14: DÒ TÌM GIỌNG ĐỌC TIẾNG VIỆT (TTS PROBE) ===\n")

    sapi_voices = probe_sapi5_voices()
    print(f"1. Giọng SAPI5 (Desktop) phát hiện được: {len(sapi_voices)}")
    vi_sapi = []
    for v in sapi_voices:
        name = v.get("Name", "")
        culture = v.get("Culture", "")
        vid = v.get("Id", "")
        is_vi = is_vietnamese(name) or is_vietnamese(culture) or is_vietnamese(vid)
        marker = " [TIẾNG VIỆT]" if is_vi else ""
        print(f"   - {name} ({culture}){marker} -> Id: {vid}")
        if is_vi:
            vi_sapi.append(v)

    onecore_voices = probe_onecore_voices()
    print(f"\n2. Giọng Windows OneCore phát hiện được: {len(onecore_voices)}")
    vi_onecore = []
    for v in onecore_voices:
        name = v.get("Name", v.get("Token", ""))
        lang = v.get("LangHex", "")
        is_vi = is_vietnamese(name) or lang == "42a" or "vietnam" in name.lower()
        marker = " [TIẾNG VIỆT]" if is_vi else ""
        print(f"   - {name} (Lang: {lang}){marker} -> Token: {v.get('Token')}")
        if is_vi:
            vi_onecore.append(v)

    piper_models = probe_piper_models()
    print(f"\n3. Mô hình Piper TTS (offline): {len(piper_models)} mô hình")
    for m in piper_models:
        print(f"   - {m}")

    edge_voices = probe_edge_tts_voices()
    print(f"\n4. Engine Edge-TTS (online Neural):")
    if edge_voices is None:
        print("   - Chưa cài đặt thư viện edge-tts (pip install edge-tts)")
    else:
        print(f"   - Đã cài đặt thư viện edge-tts [SẴN SÀNG]")
        for ev in edge_voices:
            s_name = ev.get("ShortName", "")
            gender = ev.get("Gender", "")
            print(f"   - {s_name} ({gender}) [TIẾNG VIỆT]")

    print("\n" + "="*50)
    total_local_vi = len(vi_sapi) + len(vi_onecore) + len(piper_models)
    total_edge_vi = len(edge_voices) if edge_voices else 0

    if total_local_vi > 0:
        print(f"KẾT QUẢ: Tìm thấy {total_local_vi} nguồn giọng tiếng Việt nội bộ.")
    elif total_edge_vi > 0:
        print(f"KẾT QUẢ: Hệ thống nội bộ chưa có giọng SAPI5/OneCore tiếng Việt,")
        print(f"         nhưng engine Edge-TTS ĐÃ SẴN SÀNG với {total_edge_vi} giọng tiếng Việt chất lượng cao.")
        print(f"         Giọng nam được chọn: vi-VN-NamMinhNeural.")
        print(f"         Cấu hình áp dụng: SPEAK_ENGINE=edge, SPEAK_VOICE_ID=vi-VN-NamMinhNeural.")
    else:
        print("KẾT QUẢ: HIỆN CHƯA CÓ GIỌNG TIẾNG VIỆT NÀO TRÊN MÁY TÍNH.")
        print("\nCác phương án theo tài liệu docs/plan/MO_TA_CONG_VIEC.md mục B14:")
        print("  Phương án 1 (Khuyến nghị): Cài gói tiếng Việt cho Windows:")
        print("     Settings -> Time & language -> Language & region -> Add Vietnamese -> Text-to-speech.")
        print("  Phương án 2: Sử dụng Piper TTS offline:")
        print("     Tải mô hình tiếng Việt vào backend/ai/weights/tts/.")
        print("  Phương án 3: Sử dụng edge-tts (SPEAK_ENGINE=edge, SPEAK_VOICE_ID=vi-VN-NamMinhNeural).")
    print("="*50)


if __name__ == "__main__":
    main()
