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

    print("\n" + "="*50)
    total_vi = len(vi_sapi) + len(vi_onecore) + len(piper_models)
    if total_vi > 0:
        print(f"KẾT QUẢ: Tìm thấy {total_vi} nguồn giọng tiếng Việt khả dụng.")
    else:
        print("KẾT QUẢ: HIỆN CHƯA CÓ GIỌNG TIẾNG VIỆT NÀO TRÊN MÁY TÍNH.")
        print("\nCác phương án theo tài liệu docs/plan/MO_TA_CONG_VIEC.md mục B14:")
        print("  Phương án 1 (Khuyến nghị): Cài gói tiếng Việt cho Windows:")
        print("     Settings -> Time & language -> Language & region -> Add Vietnamese -> Text-to-speech.")
        print("  Phương án 2: Sử dụng Piper TTS offline:")
        print("     Tải mô hình tiếng Việt (vi_VN-vivos-x_low hoặc vi_VN-25hours-single) vào backend/ai/weights/tts/.")
        print("  Phương án 3: Sử dụng edge-tts (cần kết nối Internet, dự phòng).")
    print("="*50)


if __name__ == "__main__":
    main()
