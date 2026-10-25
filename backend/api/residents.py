# Agent 2 — xem docs/context/API_CONTRACT.md
from typing import List, Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
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


class StatusUpdatePayload(BaseModel):
    status: Literal["active", "inactive"]


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


@router.patch("/{id}/status", response_model=ResidentResponse)
def update_resident_status(
    id: int,
    payload: StatusUpdatePayload,
    db: Session = Depends(get_db),
):
    """Cập nhật trạng thái kích hoạt/vô hiệu hóa của cư dân (active/inactive).
    
    - Giá trị status khác 'active'|'inactive' tự động trả lỗi 422 (Pydantic Literal validation).
    - Không tìm thấy id trả 404.
    - Cập nhật database và gọi cập nhật bộ nhớ GalleryCache (nếu có).
    - Trả về thông tin cư dân đã cập nhật.
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cư dân với ID {id}",
        )

    user.status = payload.status
    db.commit()
    db.refresh(user)

    # Cập nhật cache nhận diện khuôn mặt trong bộ nhớ RAM nếu B6 đã nạp
    try:
        from services import gallery_cache
        if hasattr(gallery_cache, "update_resident_status"):
            gallery_cache.update_resident_status(user.id, user.status)
        elif hasattr(gallery_cache, "reload"):
            gallery_cache.reload(db)
    except Exception:
        # TODO(B6): GalleryCache chưa khởi tạo, sẽ cập nhật khi B6 hoàn tất
        pass

    frames_count = (
        db.query(func.count(FaceEmbedding.id))
        .filter(FaceEmbedding.user_id == user.id)
        .scalar()
        or 0
    )

    return ResidentResponse(
        id=user.id,
        user_code=user.user_code or f"USR{user.id:06d}",
        full_name=user.full_name,
        age=user.age,
        apartment_number=user.apartment_number,
        status=user.status,
        frames=frames_count,
    )


# POST ""        multipart: full_name, age, apartment_number -> backend tự quay 3 giây từ camera (B5)
