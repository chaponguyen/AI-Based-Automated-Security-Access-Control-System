# Agent 2 — xem docs/context/API_CONTRACT.md
import logging
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.database import get_db
from database.models import AccessLog, User, StaffAccount
from api.deps import require_staff, require_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"], dependencies=[Depends(require_staff)])


def _record_audit(
    db: Session,
    staff: Any,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Ghi vết kiểm toán an toàn (CP-04 sẽ hoàn thiện dịch vụ audit_service)."""
    try:
        from services import audit_service
        audit_service.record(
            db,
            staff=staff,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    except Exception as e:
        logger.debug("Chưa nối audit_service hoặc ghi audit thất bại: %s", e)


class LogResponse(BaseModel):
    id: int
    timestamp: Optional[datetime] = None
    name: str
    similarity: Optional[float] = None
    liveness: Optional[bool] = None
    decision: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class LogsDeleteRequest(BaseModel):
    ids: Optional[List[int]] = None
    from_time: Optional[str] = Field(None, alias="from")
    to_time: Optional[str] = Field(None, alias="to")

    class Config:
        populate_by_name = True


class LogsDeleteResponse(BaseModel):
    deleted: int


@router.get("", response_model=List[LogResponse])
def get_logs(
    decision: Optional[str] = Query(None, description="Lọc theo kết quả: 'granted' hoặc 'denied'"),
    q: Optional[str] = Query(None, description="Tìm theo tên cư dân (không phân biệt hoa thường)"),
    from_time: Optional[str] = Query(None, alias="from", description="Thời điểm bắt đầu (ISO 8601)"),
    to_time: Optional[str] = Query(None, alias="to", description="Thời điểm kết thúc (ISO 8601)"),
    limit: int = Query(200, ge=1, le=1000, description="Số lượng dòng tối đa (mặc định 200, tối đa 1000)"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách nhật ký ra vào với các bộ lọc: decision, q, from, to.
    
    Khớp API CONTRACT: [{id, timestamp, name, similarity, liveness, decision, reason}].
    - Sắp xếp mới nhất trước (timestamp giảm dần, id giảm dần).
    - Người không xác định hiển thị 'Không xác định'.
    - Lọc tên không phân biệt chữ hoa/thường.
    """
    query = (
        db.query(AccessLog, User.full_name)
        .outerjoin(User, AccessLog.user_id == User.id)
    )

    # 1. Lọc theo decision (granted / denied)
    if isinstance(decision, str) and decision.strip():
        decision_clean = decision.strip().lower()
        if decision_clean in ("granted", "denied"):
            query = query.filter(AccessLog.decision == decision_clean)

    # 2. Lọc theo từ khóa tìm kiếm tên cư dân (q)
    if isinstance(q, str) and q.strip():
        q_clean = q.strip()
        name_condition = User.full_name.ilike(f"%{q_clean}%")
        q_lower = q_clean.lower()
        if "không xác định" in q_lower or "khong xac dinh" in q_lower or "người lạ" in q_lower or "nguoi la" in q_lower:
            query = query.filter(or_(name_condition, AccessLog.user_id.is_(None)))
        else:
            query = query.filter(name_condition)

    # 3. Lọc theo khoảng thời gian from - to
    if isinstance(from_time, str) and from_time.strip():
        try:
            dt_from = datetime.fromisoformat(from_time.strip().replace("Z", "+00:00"))
            if dt_from.tzinfo is not None:
                dt_from = dt_from.astimezone().replace(tzinfo=None)
            query = query.filter(AccessLog.timestamp >= dt_from)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng tham số 'from' không hợp lệ. Vui lòng dùng chuẩn ISO 8601 (ví dụ 2026-10-25T08:00:00).",
            )

    if isinstance(to_time, str) and to_time.strip():
        try:
            dt_to = datetime.fromisoformat(to_time.strip().replace("Z", "+00:00"))
            if dt_to.tzinfo is not None:
                dt_to = dt_to.astimezone().replace(tzinfo=None)
            query = query.filter(AccessLog.timestamp <= dt_to)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng tham số 'to' không hợp lệ. Vui lòng dùng chuẩn ISO 8601 (ví dụ 2026-10-25T08:00:00).",
            )

    limit_val = limit if isinstance(limit, int) else 200

    # 4. Sắp xếp mới nhất trước và giới hạn số lượng
    results = (
        query.order_by(AccessLog.timestamp.desc(), AccessLog.id.desc())
        .limit(limit_val)
        .all()
    )

    logs_list = []
    for log, full_name in results:
        logs_list.append(
            LogResponse(
                id=log.id,
                timestamp=log.timestamp,
                name=full_name if full_name is not None else "Không xác định",
                similarity=log.similarity,
                liveness=log.liveness,
                decision=log.decision,
                reason=log.reason,
            )
        )

    return logs_list


@router.post("/delete", response_model=LogsDeleteResponse, dependencies=[Depends(require_manager)])
def delete_logs(
    payload: LogsDeleteRequest,
    current_staff: StaffAccount = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Xóa nhật ký ra vào theo ids hoặc theo khoảng thời gian from/to (B16 CP-03).
    
    Quy tắc nghiệp vụ:
    - Yêu cầu vai trò manager.
    - Phải có ids (không rỗng, tối đa 1000) HOẶC cả from và to.
    - Thiếu cả hai hoặc thân rỗng trả 422 (KHÔNG BAO GIỜ xóa hết khi thân rỗng).
    - Thực hiện xóa trong một transaction duy nhất.
    - Chỉ xóa bảng access_logs, TUYỆT ĐỐI KHÔNG đụng audit_logs.
    - Trả về 200 {"deleted": n}.
    """
    has_ids = payload.ids is not None
    # Nếu chỉ có from hoặc chỉ có to mà không có ids thì không hợp lệ
    has_from = bool(payload.from_time and str(payload.from_time).strip())
    has_to = bool(payload.to_time and str(payload.to_time).strip())
    has_range = has_from and has_to

    # 1. Kiểm tra điều kiện phải có ids hoặc cả from và to
    if not has_ids and not has_range:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "reason": "invalid_request",
                "message": "Yêu cầu phải có danh sách 'ids' (tối đa 1000) hoặc đồng thời cả 'from' và 'to'",
            },
        )

    # 2. Validate ids nếu được cung cấp
    if has_ids:
        if len(payload.ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_request", "message": "Danh sách 'ids' không được để rỗng"},
            )
        if len(payload.ids) > 1000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_request", "message": "Danh sách 'ids' tối đa 1000 phần tử"},
            )

    # 3. Validate from và to nếu được cung cấp
    dt_from = None
    dt_to = None
    if has_range or (has_from and not has_ids) or (has_to and not has_ids):
        if not (has_from and has_to):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_request", "message": "Phải cung cấp đồng thời cả 'from' và 'to'"},
            )

        try:
            dt_from = datetime.fromisoformat(payload.from_time.strip().replace("Z", "+00:00"))
            if dt_from.tzinfo is not None:
                dt_from = dt_from.astimezone().replace(tzinfo=None)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_format", "message": "Định dạng thời điểm 'from' không hợp lệ"},
            )

        try:
            dt_to = datetime.fromisoformat(payload.to_time.strip().replace("Z", "+00:00"))
            if dt_to.tzinfo is not None:
                dt_to = dt_to.astimezone().replace(tzinfo=None)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_format", "message": "Định dạng thời điểm 'to' không hợp lệ"},
            )

        if dt_from > dt_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "invalid_range", "message": "Thời điểm 'from' không được lớn hơn 'to'"},
            )

    # 4. Thực thi xóa bảng access_logs trong một transaction duy nhất
    query = db.query(AccessLog)
    if has_ids and has_range:
        query = query.filter(
            AccessLog.id.in_(payload.ids),
            AccessLog.timestamp >= dt_from,
            AccessLog.timestamp <= dt_to,
        )
    elif has_ids:
        query = query.filter(AccessLog.id.in_(payload.ids))
    else:
        query = query.filter(
            AccessLog.timestamp >= dt_from,
            AccessLog.timestamp <= dt_to,
        )

    try:
        deleted_count = query.delete(synchronize_session=False)

        # 5. Ghi vết kiểm toán audit_logs TRONG CÙNG TRANSACTION với thao tác xóa
        audit_detail_parts = [f"Xóa {deleted_count} dòng access_logs"]
        if has_ids:
            audit_detail_parts.append(f"{len(payload.ids)} ids")
        if has_range:
            audit_detail_parts.append(f"từ {payload.from_time} đến {payload.to_time}")

        from services import audit_service
        audit_service.record(
            db,
            current_staff,
            "logs_deleted",
            target_type="access_logs",
            target_id=None,
            detail=", ".join(audit_detail_parts),
            commit=False,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Lỗi khi xóa nhật ký ra vào hoặc ghi audit: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"reason": "database_error", "message": "Không thể xóa nhật ký ra vào"},
        )

    return {"deleted": deleted_count}

