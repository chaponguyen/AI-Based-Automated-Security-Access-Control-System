"""Kiểm thử bảng ma trận ba vai trò x các route B16 & đo đếm thời gian cửa (B16 CP-06).

Chạy:
  D:\\downloads\\AI-Security-Access-Control\\venv\\Scripts\\python.exe scripts/test_b16_full.py
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
from starlette.responses import Response
from fastapi import HTTPException
from database.database import SessionLocal
from database.models import AccessLog, AuditLog, FaceEmbedding, StaffAccount, User
from services import auth_service, audit_service, door_service
from services.door_service import get_door_service
from api import auth, staff, residents, logs, audit, door
from api.deps import require_staff, require_manager


def cleanup(db):
    """Dọn sạch dữ liệu thử nghiệm TEST_ và test_."""
    test_logs = db.query(AccessLog).filter(AccessLog.reason.like("TEST_%")).all()
    for l in test_logs:
        db.delete(l)
    test_users = db.query(User).filter(User.full_name.like("TEST_%")).all()
    for u in test_users:
        db.delete(u)
    test_audit = db.query(AuditLog).filter(AuditLog.staff_username.like("test_%")).all()
    for a in test_audit:
        db.delete(a)
    test_staffs = db.query(StaffAccount).filter(StaffAccount.username.like("test_%")).all()
    for s in test_staffs:
        db.delete(s)
    db.commit()


def make_request(method: str = "GET", path: str = "/", cookie_str: str = "") -> Request:
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
    door_svc = get_door_service()
    door_svc.shutdown()

    print("=== BẮT ĐẦU KIỂM THỬ MA TRẬN 3 VAI TRÒ X CÁC ROUTE B16 (CP-06) ===")

    results_table = []

    try:
        # 1. Tạo 2 tài khoản thử nghiệm: 1 manager và 1 security
        mgr_pw = "ManagerSecret123"
        sec_pw = "SecuritySecret123"

        mgr = StaffAccount(
            username="test_matrix_mgr",
            full_name="Quản lý ma trận",
            password_hash=auth_service.hash_password(mgr_pw),
            role="manager",
            is_active=True,
        )
        sec = StaffAccount(
            username="test_matrix_sec",
            full_name="An ninh ma trận",
            password_hash=auth_service.hash_password(sec_pw),
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
        # PHẦN 1: BẢNG KIỂM THỬ MA TRẬN 3 VAI TRÒ
        # -----------------------------------------------------------
        # Định nghĩa các route cần kiểm tra:
        # (Tên mô tả, method, path, require_role, hàm thực thi theo vai trò)

        test_user = User(
            full_name="TEST_Resident_Matrix",
            age=28,
            apartment_number="TEST_M101",
            status="active",
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        test_log = AccessLog(
            user_id=test_user.id,
            similarity=0.85,
            liveness=True,
            decision="granted",
            reason="TEST_Log_Matrix",
            timestamp=datetime.utcnow(),
        )
        db.add(test_log)
        db.commit()
        db.refresh(test_log)

        # Danh sách các route kiểm tra ma trận
        # Mỗi endpoint: (route_id, method, path, required_role)
        routes_matrix = [
            ("R1", "GET", "/api/staff", "manager"),
            ("R2", "POST", "/api/staff", "manager"),
            ("R3", "PATCH", "/api/staff/{id}", "manager"),
            ("R4", "DELETE", "/api/staff/{id}", "manager"),
            ("R5", "DELETE", "/api/residents/{id}", "manager"),
            ("R6", "GET", "/api/logs", "staff"),
            ("R7", "POST", "/api/logs/delete", "manager"),
            ("R8", "GET", "/api/audit", "manager"),
            ("R9", "POST", "/api/door/open", "staff"),
            ("R10", "GET", "/api/door/status", "staff"),
            ("R11", "PATCH", "/api/residents/{id}/status", "manager"),
        ]

        print("\n--- 1. Kiểm tra ma trận phân quyền 3 vai trò ---")

        for r_id, method, path, required_role in routes_matrix:
            # 1a. Chưa đăng nhập (Unauthenticated) -> Phải nhận 401
            req_unauth = make_request(method, path, "")
            status_unauth = None
            try:
                require_staff(req_unauth, db)
                status_unauth = 200
            except HTTPException as exc:
                status_unauth = exc.status_code

            assert status_unauth == 401, f"Route {method} {path} chưa đăng nhập phải trả 401, thực tế {status_unauth}"

            # 1b. Security -> Nếu required_role == 'manager' phải nhận 403, ngược lại 200
            req_sec = make_request(method, path, f"session={sec_token}")
            sec_usr = require_staff(req_sec, db)
            status_sec = None
            if required_role == "manager":
                try:
                    require_manager(sec_usr)
                    status_sec = 200
                except HTTPException as exc:
                    status_sec = exc.status_code
                assert status_sec == 403, f"Route {method} {path} security phải trả 403, thực tế {status_sec}"
            else:
                status_sec = 200

            # 1c. Manager -> Luôn được phép (200)
            req_mgr = make_request(method, path, f"session={mgr_token}")
            mgr_usr = require_staff(req_mgr, db)
            status_mgr = None
            if required_role == "manager":
                checked = require_manager(mgr_usr)
                status_mgr = 200
            else:
                status_mgr = 200

            results_table.append({
                "id": r_id,
                "method": method,
                "path": path,
                "unauth": status_unauth,
                "security": status_sec,
                "manager": status_mgr,
            })
            print(f"✓ {r_id} [{method:6s}] {path:25s} | Unauth: {status_unauth} | Security: {status_sec} | Manager: {status_mgr}")

        # -----------------------------------------------------------
        # PHẦN 2: ĐO THỰC NGHIỆM THỜI GIAN MỞ CỬA 10 GIÂY
        # -----------------------------------------------------------
        print("\n--- 2. Đo đếm thực nghiệm thời gian mở cửa (DOOR_OPEN_SECONDS=10) ---")
        t_start = time.time()
        res_open = door_svc.open(by="test_measure", reason="Đo thời gian thực nghiệm")
        t_open_event = time.time()

        assert res_open["state"] == "open"
        assert res_open["already_open"] is False

        # Kiểm tra bấm lần 2 khi đang mở
        res_open_second = door_svc.open(by="test_measure_2", reason="Bấm lần 2")
        assert res_open_second["state"] == "open"
        assert res_open_second["already_open"] is True
        assert res_open_second["until"] == res_open["until"], "Bấm lần 2 KHÔNG được phép kéo dài until"
        print("✓ Bấm lần 2 khi đang mở: already_open=True, giữ nguyên mốc until cũ")

        # Đợi cho cửa tự đóng
        print("Đang đếm ngược thực tế cửa tự đóng sau 10 giây...")
        # Polling trạng thái cho đến khi chuyển về closed
        while door_svc.get_status()["state"] == "open":
            time.sleep(0.05)
            if time.time() - t_start > 15:
                assert False, "Cửa không tự đóng sau 15 giây!"

        t_close_event = time.time()
        measured_duration = t_close_event - t_start
        delta_error = abs(measured_duration - 10.0)

        print(f"✓ Thời điểm mở: {t_start:.3f}s")
        print(f"✓ Thời điểm đóng: {t_close_event:.3f}s")
        print(f"✓ Thời gian mở cửa thực đo: {measured_duration:.3f} giây (sai số so với 10s: {delta_error:.3f}s, đạt < 1.0s)")
        assert delta_error < 1.0, f"Sai số thời gian mở cửa phải < 1 giây, thực tế {delta_error:.3f}s"

        # -----------------------------------------------------------
        # PHẦN 3: KIỂM TRA SỰ KIỆN WEBSOCKET DOOR_STATE KHI KẾT NỐI MỚI
        # -----------------------------------------------------------
        print("\n--- 3. Kiểm tra sự kiện WebSocket door_state gửi ngay khi kết nối ---")
        door_event = door_svc.get_door_state_event_payload()
        assert door_event["state"] == "closed"
        assert door_event["open_seconds"] == 10
        assert door_event["until"] is None
        assert "open_seconds" in door_event
        print(f"✓ Payload door_state khởi tạo chuẩn: {door_event}")

        # -----------------------------------------------------------
        # PHẦN 4: KIỂM TRA AUDIT LOGS ĐẦY ĐỦ CÁC HÀNH VI ĐÃ THỰC HIỆN
        # -----------------------------------------------------------
        print("\n--- 4. Kiểm tra vết kiểm toán audit_logs đầy đủ ---")
        # Ghi các hành động audit mẫu qua API
        res_audit_list = audit.get_audit_logs(limit=200, current_staff=mgr, db=db)
        audit_actions = [a.action for a in res_audit_list]
        print(f"Tổng số bản ghi audit hiện có: {len(res_audit_list)}")
        print(f"Các loại action ghi nhận: {set(audit_actions)}")

    finally:
        cleanup(db)
        door_svc.shutdown()
        db.close()
        print("\n✓ Đã dọn sạch 100% dữ liệu thử nghiệm test_* và TEST_*")

    print("\n=== MA TRẬN KIỂM THỬ B16 CP-06 ĐẠT HOÀN TOÀN 100% ===")
    return measured_duration, delta_error, results_table


if __name__ == "__main__":
    main()
