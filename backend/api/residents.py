# Agent 2 — xem docs/context/API_CONTRACT.md
from fastapi import APIRouter
router = APIRouter(prefix="/api/residents", tags=["residents"])
# POST ""        multipart: full_name, age, apartment_number -> backend tự quay 3 giây từ camera, tạo cư dân kèm khuôn mặt
# GET  ""        danh sách cư dân
# PATCH "/{id}/status"   {"status": "active"|"inactive"}
