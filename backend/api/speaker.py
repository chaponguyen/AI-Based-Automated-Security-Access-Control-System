# Agent 2 — API điều khiển và kiểm tra loa thông báo (B14 CP-08)
# docs/context/API_CONTRACT.md
from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services import speaker_service
from api.deps import require_staff

router = APIRouter(prefix="/api/speaker", tags=["speaker"], dependencies=[Depends(require_staff)])


class SpeakerTestRequest(BaseModel):
    text: str


class SpeakerMuteRequest(BaseModel):
    muted: bool


@router.post("/test")
def test_speaker(payload: SpeakerTestRequest) -> Dict[str, bool]:
    """Phát thử câu bất kỳ qua cùng đường đọc của loa (B14 CP-08).
    Dùng def thường để không chặn event loop FastAPI.
    """
    ok = speaker_service.enqueue_speak(payload.text, is_alert=False)
    return {"ok": ok}


@router.post("/mute")
def mute_speaker(payload: SpeakerMuteRequest) -> Dict[str, bool]:
    """Bật/tắt chế độ im lặng của loa (nút 'Tắt loa' trên giao diện).
    Dùng def thường để không chặn event loop FastAPI.
    """
    muted_status = speaker_service.set_muted(payload.muted)
    return {"muted": muted_status}


@router.get("/status")
def get_status() -> Dict[str, Any]:
    """Lấy trạng thái loa: enabled, muted, voice, queue.
    Dùng def thường để không chặn event loop FastAPI.
    """
    return speaker_service.get_speaker_status()
