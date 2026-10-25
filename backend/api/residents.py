import re
from typing import List, Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.database import get_db
from database.models import User, FaceEmbedding
from services.registration_service import registration_lock

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


class ResidentCreateResponse(BaseModel):
    id: int
    user_code: str
    frames_kept: int


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ResidentCreateResponse,
    responses={
        201: {"description": "Đăng ký cư dân thành công kèm khuôn mặt"},
        409: {
            "description": "Đang có phiên đăng ký khác đang diễn ra",
            "content": {"application/json": {"example": {"reason": "registration_in_progress"}}},
        },
        422: {
            "description": "Dữ liệu nhập không hợp lệ hoặc không đủ khung hình đạt chất lượng",
        },
    },
)
def create_resident(
    full_name: str = Form(..., description="Họ và tên cư dân (2 đến 150 ký tự sau khi bỏ khoảng trắng thừa)"),
    age: int = Form(..., description="Tuổi cư dân (1 đến 120)"),
    apartment_number: str = Form(..., description="Mã căn hộ (1 đến 20 ký tự, chữ, số, - / .)"),
    db: Session = Depends(get_db),
):
    """Đăng ký cư dân kèm khuôn mặt qua đoạn quay 3 giây từ camera backend.
    
    CP-01: Nhập liệu và khóa đồng thời
    - full_name: 2 đến 150 ký tự sau khi bỏ khoảng trắng thừa.
    - age: 1 đến 120.
    - apartment_number: 1 đến 20 ký tự (chữ, số, -, /, .).
    - Sai nhập liệu tự động trả 422 mặc định của FastAPI.
    - Nếu hai yêu cầu cùng lúc: yêu cầu sau nhận 409 {"reason":"registration_in_progress"} bằng threading.Lock, nhả trong finally.
    """
    if not registration_lock.acquire(blocking=False):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"reason": "registration_in_progress"},
        )
    try:
        # Validate full_name
        name_clean = full_name.strip()
        if len(name_clean) < 2 or len(name_clean) > 150:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="full_name phải từ 2 đến 150 ký tự sau khi bỏ khoảng trắng thừa",
            )

        # Validate age
        if age < 1 or age > 120:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="age phải trong khoảng từ 1 đến 120",
            )

        # Validate apartment_number
        apt_clean = apartment_number.strip()
        if not (1 <= len(apt_clean) <= 20) or not re.match(r"^[A-Za-z0-9\-/\.]+$", apt_clean):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="apartment_number phải từ 1 đến 20 ký tự và chỉ chứa chữ cái, chữ số, hoặc -, /, .",
            )

        # CP-01: Khung route và kiểm tra dữ liệu thành công
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"id": 0, "user_code": "USR000000", "frames_kept": 0},
        )
    finally:
        registration_lock.release()
