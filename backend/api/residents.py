# Agent 2 — xem docs/context/API_CONTRACT.md
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.database import get_db
from database.models import User, FaceEmbedding

router = APIRouter(prefix="/api/residents", tags=["residents"])


class ResidentResponse(BaseModel):
    id: int
    user_code: str
    full_name: str
    age: int
    apartment_number: str
    status: str
    frames: int

    class Config:
        from_attributes = True


@router.get("", response_model=List[ResidentResponse])
def get_residents(db: Session = Depends(get_db)):
    """Lấy danh sách cư dân kèm số lượng khung hình khuôn mặt (frames).
    
    Khớp API CONTRACT: [{id, user_code, full_name, age, apartment_number, status, frames}].
    Sử dụng outerjoin và group_by để gom số lượng frames trong một truy vấn duy nhất (không N+1).
    """
    results = (
        db.query(User, func.count(FaceEmbedding.id).label("frames"))
        .outerjoin(FaceEmbedding, User.id == FaceEmbedding.user_id)
        .group_by(User.id)
        .order_by(User.id.asc())
        .all()
    )

    residents_list = []
    for user, frames_count in results:
        residents_list.append(
            ResidentResponse(
                id=user.id,
                user_code=user.user_code or f"USR{user.id:06d}",
                full_name=user.full_name,
                age=user.age,
                apartment_number=user.apartment_number,
                status=user.status,
                frames=frames_count,
            )
        )
    return residents_list


# POST ""        multipart: full_name, age, apartment_number -> backend tự quay 3 giây từ camera (B5)
# PATCH "/{id}/status"   {"status": "active"|"inactive"} (CP-02)
