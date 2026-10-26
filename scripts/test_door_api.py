"""Kiểm thử dịch vụ cửa mô phỏng door_service.py và router api/door (B16 CP-05).

Chạy:
  D:\\downloads\\AI-Security-Access-Control\\venv\\Scripts\\python.exe scripts/test_door_api.py
"""

import sys
import os
import time
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from starlette.requests import Request
from fastapi import HTTPException
from database.database import SessionLocal
from database.models import AuditLog, StaffAccount
from services import auth_service, door_service
from services.door_service import get_door_service
from api.door import open_door, get_door_status, DoorOpenRequest
from api.deps import require_staff, require_manager


def cleanup(db):
    test_audit = db.query(AuditLog).filter(AuditLog.staff_username.like("test_%")).all()
    for a in test_audit:
        db.delete(a)
    test_staffs = db.query(StaffAccount).filter(StaffAccount.username.like("test_%")).all()
    for s in test_staffs:
        db.delete(s)
    db.commit()


def make_request(method: str = "GET", path: str = "/api/door/status", cookie_str: str = "") -> Request:
    headers = []
    if cookie_str:
        headers.append((b"cookie", cookie_str.encode("utf-8")))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
    }
    return Request(scope)


def main():
    db = SessionLocal()
    cleanup(db)

    print("=== BẮT ĐẦU KIỂM THỬ B16 CP-05 (DỊCH VỤ CỬA MÔ PHỎNG & API DOOR) ===")

    door_svc = get_door_service()
    door_svc.shutdown()  # Đảm bảo cửa đang đóng ban đầu

    try:
        # 1. Tạo tài khoản manager và security
        mgr_pw_hash = auth_service.hash_password("ManagerPass123")
        sec_pw_hash = auth_service.hash_password("SecurityPass123")

        mgr = StaffAccount(
            username="test_mgr_door",
            full_name="Quản lý cửa",
            password_hash=mgr_pw_hash,
            role="manager",
            is_active=True,
        )
        sec = StaffAccount(
            username="test_sec_door",
            full_name="An ninh cửa",
            password_hash=sec_pw_hash,
            role="security",
            is_active=True,
        )
        db.add_all([mgr, sec])
        db.commit()
        db.refresh(mgr)
        db.refresh(sec)

        mgr_token, _ = auth_service.create_session(db, mgr.id)
        sec_token, _ = auth_service.create_session(db, sec.id)

        # -----------------------------------------------------------
        # TEST 1: Phân quyền API /api/door (401 unauth, 200 security, 200 manager)
        # -----------------------------------------------------------
        req_unauth = make_request("GET", "/api/door/status", "")
        try:
            require_staff(req_unauth, db)
            assert False, "Chưa đăng nhập phải ném 401"
        except HTTPException as exc:
            assert exc.status_code == 401
            assert exc.detail == {"reason": "not_authenticated"}
        print("✓ Test 1a: Chưa đăng nhập bị chặn 401 not_authenticated")

        req_sec = make_request("GET", "/api/door/status", f"session={sec_token}")
        sec_user = require_staff(req_sec, db)
        assert sec_user.role == "security"
        print("✓ Test 1b: Security được phép truy cập route door (require_staff)")

        req_mgr = make_request("GET", "/api/door/status", f"session={mgr_token}")
        mgr_user = require_staff(req_mgr, db)
        assert mgr_user.role == "manager"
        print("✓ Test 1c: Manager được phép truy cập route door (require_staff)")

        # -----------------------------------------------------------
        # TEST 2: Trạng thái ban đầu: cửa đóng
        # -----------------------------------------------------------
        status_init = get_door_status(current_staff=sec)
        assert status_init["state"] == "closed"
        assert status_init["until"] is None
        assert status_init["by"] is None
        print("✓ Test 2: Trạng thái ban đầu cửa đóng (closed, until=None, by=None)")

        # -----------------------------------------------------------
        # TEST 3: Mở cửa thành công (POST /api/door/open)
        # -----------------------------------------------------------
        reason_sample = "Khách bấm chuông tầng 5 \x00\x1f\x08"
        t_before = datetime.utcnow()
        res_open = open_door(
            payload=DoorOpenRequest(reason=reason_sample),
            current_staff=sec,
            db=db,
        )
        t_after = datetime.utcnow()

        assert res_open["state"] == "open"
        assert res_open["open_seconds"] == 10
        assert res_open["already_open"] is False
        until_dt = datetime.fromisoformat(res_open["until"])
        # Thời điểm until phải xấp xỉ t_before + 10s (sai số dưới 1s)
        expected_until = t_before + timedelta(seconds=10)
        diff_s = abs((until_dt - expected_until).total_seconds())
        assert diff_s < 1.0, f"Sai số thời điểm mở cửa phải dưới 1 giây, thực tế {diff_s}s"
        print(f"✓ Test 3a: Mở cửa thành công, open_seconds=10, already_open=False, sai số {diff_s:.3f}s")

        # Kiểm tra GET /api/door/status khi đang mở
        status_opened = get_door_status(current_staff=mgr)
        assert status_opened["state"] == "open"
        assert status_opened["by"] == sec.username
        assert status_opened["until"] == res_open["until"]
        print(f"✓ Test 3b: GET /api/door/status phản ánh đúng trạng thái mở (by={sec.username})")

        # Kiểm tra audit_logs đã được ghi
        door_audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "door_open", AuditLog.staff_username == sec.username)
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert door_audit is not None
        assert door_audit.target_type == "door"
        assert "Khách bấm chuông tầng 5" in door_audit.detail
        assert "\x00" not in door_audit.detail, "Ký tự điều khiển phải bị loại bỏ"
        print("✓ Test 3c: Ghi audit_logs door_open kèm lý do sạch sẽ, loại bỏ ký tự điều khiển")

        # -----------------------------------------------------------
        # TEST 4: Bấm mở lần hai khi cửa đang mở: already_open=True, KHÔNG kéo dài
        # -----------------------------------------------------------
        res_open_second = open_door(
            payload=DoorOpenRequest(reason="Bấm thêm lần nữa"),
            current_staff=mgr,
            db=db,
        )
        assert res_open_second["state"] == "open"
        assert res_open_second["already_open"] is True
        # until phải giữ nguyên tuyệt đối, không được kéo dài
        assert res_open_second["until"] == res_open["until"], "until không được phép bị kéo dài khi cửa đang mở"
        print("✓ Test 4: Bấm mở lần 2 khi đang mở trả already_open=True và KHÔNG kéo dài until")

        # -----------------------------------------------------------
        # TEST 5: Cắt ngắn lý do ở 200 ký tự
        # -----------------------------------------------------------
        long_reason = "A" * 350
        res_clean = door_service._clean_reason(long_reason)
        assert len(res_clean) == 200
        print("✓ Test 5: Lý do mở cửa được cắt đúng tối đa 200 ký tự")

        # -----------------------------------------------------------
        # TEST 6: Sự kiện WebSocket door_state gửi đúng cấu trúc
        # -----------------------------------------------------------
        ws_event = door_svc.get_door_state_event_payload()
        assert ws_event["state"] == "open"
        assert ws_event["open_seconds"] == 10
        assert ws_event["until"] == res_open["until"]
        assert ws_event["by"] == sec.username
        print("✓ Test 6: Cấu trúc sự kiện WS door_state đầy đủ {state, until, open_seconds, by, reason}")

        # -----------------------------------------------------------
        # TEST 7: Hết giờ tự động đóng (mô phỏng auto_close hoặc chờ)
        # -----------------------------------------------------------
        # Gọi trực tiếp _auto_close để kiểm tra logic đóng cửa an toàn
        door_svc._auto_close()
        status_closed = get_door_status(current_staff=sec)
        assert status_closed["state"] == "closed"
        assert status_closed["until"] is None
        assert status_closed["by"] is None
        print("✓ Test 7: Hết giờ tự động đóng cửa (state=closed, until=None, by=None)")

        # -----------------------------------------------------------
        # TEST 8: Shutdown hủy timer sạch sẽ
        # -----------------------------------------------------------
        door_svc.open(by="test_shutdown")
        assert door_svc.get_status()["state"] == "open"
        door_svc.shutdown()
        assert door_svc.get_status()["state"] == "closed"
        assert door_svc._timer is None
        print("✓ Test 8: Shutdown hủy timer và đưa trạng thái về closed sạch sẽ")

    finally:
        cleanup(db)
        db.close()
        door_svc.shutdown()
        print("✓ Đã dọn sạch dữ liệu thử nghiệm và đóng dịch vụ cửa")

    print("=== TẤT CẢ KIỂM THỬ B16 CP-05 ĐẠT 100% ===")


if __name__ == "__main__":
    main()
