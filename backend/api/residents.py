import re
from typing import List, Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.database import get_db
from database.models import User, FaceEmbedding
from services.registration_service import (
    registration_lock,
    record_registration_frames,
    register_resident,
    NotEnoughQualityFramesError,
    AlreadyRegisteredError,
    find_existing_resident,
)

router = APIRouter(prefix="/api/residents", tags=["residents"])
registration_router = APIRouter(prefix="/api/registration", tags=["registration"])


@registration_router.get("/precheck")
def precheck_registration():
    """Kiểm tra khuôn mặt hiện tại trước camera trước khi đăng ký (B5 CP-07).

    - Lấy camera.latest()
    - detect_faces, chọn mặt lớn nhất nếu có nhiều mặt
    - Trả về state: 'no_face' | 'multiple_faces' | 'low_quality' | 'new' | 'exists'
    - exists: bool
    - user: {id, user_code, full_name, apartment_number, status} | null
    - similarity: float | null
    - box: [x1, y1, x2, y2] | null
    - Cập nhật màu khung trên stream: ĐỎ nhãn 'ĐÃ TỒN TẠI: <tên>' nếu trùng, XANH DƯƠNG 'Người mới' nếu chưa có.
    - Dùng def thường. Không ghi access_logs, không phát access_result.
    """
    from services.camera_service import get_camera
    from services import gallery_cache
    from services.stream_service import set_latest_precheck
    from ai.detector import detect_faces
    from ai.quality import frame_quality
    from ai.aligner import crop_face
    from ai.embedder import get_embedding

    camera = get_camera()
    now_t, frame = camera.latest()
    if frame is None:
        set_latest_precheck(None)
        return {
            "state": "no_face",
            "exists": False,
            "user": None,
            "similarity": None,
            "box": None,
        }

    faces = detect_faces(frame)
    if not faces:
        set_latest_precheck(None)
        return {
            "state": "no_face",
            "exists": False,
            "user": None,
            "similarity": None,
            "box": None,
        }

    if len(faces) > 1:
        # Có nhiều hơn 1 mặt: chọn mặt lớn nhất để trả box
        def face_area(fc):
            b = fc.get("bbox", [0, 0, 0, 0])
            return max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        largest = max(faces, key=face_area)
        box = [int(v) for v in largest.get("bbox", [0, 0, 0, 0])]
        set_latest_precheck(None)
        return {
            "state": "multiple_faces",
            "exists": False,
            "user": None,
            "similarity": None,
            "box": box,
        }

    # Đúng 1 mặt trong khung hình
    face = faces[0]
    box = [int(v) for v in face.get("bbox", [0, 0, 0, 0])]
    q = frame_quality(frame, faces, allow_multiple=False)
    if not q.get("ok"):
        set_latest_precheck(None)
        return {
            "state": "low_quality",
            "exists": False,
            "user": None,
            "similarity": None,
            "box": box,
        }

    # Đạt chất lượng: trích xuất embedding và so khớp với GalleryCache
    aligned = crop_face(frame, face["kps"])
    emb = get_embedding(aligned)
    gallery = gallery_cache.get_gallery()
    matched_id, similarity = find_existing_resident(emb, gallery)

    if matched_id is not None:
        matched_user = gallery_cache.get_user(matched_id) or {}
        user_dict = {
            "id": matched_user.get("id", matched_id),
            "user_code": matched_user.get("user_code"),
            "full_name": matched_user.get("full_name"),
            "apartment_number": matched_user.get("apartment_number"),
            "status": matched_user.get("status"),
        }
        # Lưu kết quả precheck vào stream overlay (màu ĐỎ nhãn "ĐÃ TỒN TẠI: <tên>")
        set_latest_precheck({
            "box": box,
            "landmarks": face.get("kps"),
            "exists": True,
            "name": user_dict.get("full_name", ""),
        })
        return {
            "state": "exists",
            "exists": True,
            "user": user_dict,
            "similarity": round(float(similarity), 4),
            "box": box,
        }
    else:
        # Người mới chưa có trong hệ thống
        set_latest_precheck({
            "box": box,
            "landmarks": face.get("kps"),
            "exists": False,
            "name": "Người mới",
        })
        return {
            "state": "new",
            "exists": False,
            "user": None,
            "similarity": round(float(similarity), 4) if similarity > 0 else None,
            "box": box,
        }


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

        # B5 CP-07: (a) TRƯỚC khi quay: kiểm tra trên khung camera hiện tại
        from services.camera_service import get_camera
        from services import gallery_cache
        from services.stream_service import set_latest_precheck
        from ai.detector import detect_faces
        from ai.quality import frame_quality
        from ai.aligner import crop_face
        from ai.embedder import get_embedding

        camera = get_camera()
        now_t, current_frame = camera.latest()
        if current_frame is not None:
            faces = detect_faces(current_frame)
            if len(faces) == 1:
                face = faces[0]
                q = frame_quality(current_frame, faces, allow_multiple=False)
                if q.get("ok"):
                    aligned = crop_face(current_frame, face["kps"])
                    emb = get_embedding(aligned)
                    matched_id, sim = find_existing_resident(emb, gallery_cache.get_gallery())
                    if matched_id is not None:
                        matched_user = gallery_cache.get_user(matched_id) or {}
                        user_payload = {
                            "id": matched_user.get("id", matched_id),
                            "user_code": matched_user.get("user_code"),
                            "full_name": matched_user.get("full_name"),
                            "apartment_number": matched_user.get("apartment_number"),
                            "status": matched_user.get("status"),
                        }
                        # Đổi màu khung trên stream sang đỏ ngay lập tức
                        set_latest_precheck({
                            "box": [int(v) for v in face.get("bbox", [0, 0, 0, 0])],
                            "landmarks": face.get("kps"),
                            "exists": True,
                            "name": user_payload.get("full_name", ""),
                        })
                        return JSONResponse(
                            status_code=status.HTTP_409_CONFLICT,
                            content={
                                "reason": "already_registered",
                                "user": user_payload,
                                "similarity": round(float(sim), 4),
                            },
                        )

        # CP-02: Quay 3 giây từ camera backend, tạm dừng AI và phát tiến độ qua WebSocket
        frames = record_registration_frames()

        # CP-03: Lọc và chọn khung đạt chuẩn (register_resident)
        try:
            selected_frames = register_resident(
                db,
                {"full_name": name_clean, "age": age, "apartment_number": apt_clean},
                frames,
            )
        except AlreadyRegisteredError as e:
            # B5 CP-07: (b) SAU khi quay và lọc khung: trùng thì trả 409 already_registered
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "reason": "already_registered",
                    "user": e.user,
                    "similarity": round(float(e.similarity), 4),
                },
            )
        except NotEnoughQualityFramesError as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "reason": "not_enough_quality_frames",
                    "good": e.good,
                    "required": e.required,
                },
            )

        # CP-04: Lưu thành công trong một transaction, trả về id, user_code, frames_kept
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "id": selected_frames["id"],
                "user_code": selected_frames["user_code"],
                "frames_kept": selected_frames["frames_kept"],
            },
        )



    finally:
        registration_lock.release()
