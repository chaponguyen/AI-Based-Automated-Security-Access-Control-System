# Agent 2 — xem docs/context/API_CONTRACT.md
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.database import get_db
from database.models import AccessLog, User

router = APIRouter(prefix="/api/logs", tags=["logs"])


class LogResponse(BaseModel):
    timestamp: Optional[datetime] = None
    name: str
    similarity: Optional[float] = None
    liveness: Optional[bool] = None
    decision: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


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
    
    Khớp API CONTRACT: [{timestamp, name, similarity, liveness, decision, reason}].
    - Sắp xếp mới nhất trước (timestamp giảm dần).
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
            query = query.filter(AccessLog.timestamp >= dt_from)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng tham số 'from' không hợp lệ. Vui lòng dùng chuẩn ISO 8601 (ví dụ 2026-10-25T08:00:00).",
            )

    if isinstance(to_time, str) and to_time.strip():
        try:
            dt_to = datetime.fromisoformat(to_time.strip().replace("Z", "+00:00"))
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
                timestamp=log.timestamp,
                name=full_name if full_name is not None else "Không xác định",
                similarity=log.similarity,
                liveness=log.liveness,
                decision=log.decision,
                reason=log.reason,
            )
        )

    return logs_list
