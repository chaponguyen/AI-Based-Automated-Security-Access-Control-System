"""Kiểm thử toàn diện dịch vụ audit_service.py và route GET /api/audit (B16 CP-04).

Chạy:
  D:\\downloads\\AI-Security-Access-Control\\venv\\Scripts\\python.exe scripts/test_audit_api.py
"""

import sys
import os
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
from database.models import AccessLog, AuditLog, StaffAccount, User
from services import auth_service, audit_service
from api.audit import get_audit_logs
from api.deps import require_staff, require_manager
from main import app


def cleanup(db):
    """Xóa dữ liệu thử nghiệm có tiền tố TEST_ hoặc test_."""
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


def make_request(method: str = "GET", path: str = "/api/audit", cookie_str: str = "") -> Request:
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

    print("=== BẮT ĐẦU KIỂM THỬ B16 CP-04 (AUDIT SERVICE & GET /API/AUDIT) ===")

    try:
        # 1. Tạo tài khoản manager và security
        mgr_pw_hash = auth_service.hash_password("ManagerPass123")
        sec_pw_hash = auth_service.hash_password("SecurityPass123")

        mgr = StaffAccount(
            username="test_mgr_audit",
            full_name="Quản lý kiểm toán",
            password_hash=mgr_pw_hash,
            role="manager",
            is_active=True,
        )
        sec = StaffAccount(
            username="test_sec_audit",
            full_name="An ninh kiểm toán",
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
        # TEST 1: Kiểm tra ghi nhận các sự kiện bắt buộc qua audit_service.record
        # -----------------------------------------------------------
        actions_to_test = [
            ("login", "auth", str(mgr.id), "Đăng nhập thành công"),
            ("login_locked", "auth", str(sec.id), "Khóa tài khoản 5 phút do sai 5 lần"),
            ("logout", "auth", str(mgr.id), "Đăng xuất thành công"),
            ("resident_registered", "resident", "101", "Đăng ký cư dân TEST_A (USR000101)"),
            ("resident_status_changed", "resident", "101", "Đổi trạng thái TEST_A sang inactive"),
            ("resident_deleted", "resident", "101", "Xóa cư dân TEST_A (USR000101)"),
            ("staff_created", "staff", "202", "Tạo tài khoản test_sec_new vai trò security"),
            ("staff_updated", "staff", "202", "Cập nhật họ tên, đổi vai trò"),
            ("staff_deleted", "staff", "202", "Xóa tài khoản test_sec_new"),
            ("logs_deleted", "access_logs", None, "Xóa 5 dòng access_logs theo ids"),
            ("door_open", "door", None, "Mở cửa thủ công (Lý do: Khách bấm chuông)"),
        ]

        created_audits = []
        for action, target_type, target_id, detail in actions_to_test:
            rec = audit_service.record(
                db,
                staff=mgr,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=detail,
            )
            assert rec.id > 0
            assert rec.staff_username == mgr.username
            assert rec.action == action
            created_audits.append(rec)

        print(f"✓ Test 1: Đã ghi nhận đầy đủ 11 hành vi bắt buộc qua audit_service.record")

        # -----------------------------------------------------------
        # TEST 2: Sao chép staff_username độc lập kể cả khi tài khoản bị xóa
        # -----------------------------------------------------------
        # Tạo 1 staff tạm, ghi audit, sau đó xóa staff đó
        temp_staff = StaffAccount(
            username="test_temp_to_delete",
            full_name="Nhân viên tạm thời",
            password_hash=sec_pw_hash,
            role="security",
            is_active=True,
        )
        db.add(temp_staff)
        db.commit()
        db.refresh(temp_staff)

        temp_audit = audit_service.record(
            db,
            staff=temp_staff,
            action="test_temp_action",
            target_type="test",
            target_id="999",
            detail="Hành động của tài khoản tạm",
        )
        temp_audit_id = temp_audit.id

        # Xóa temp_staff
        db.delete(temp_staff)
        db.commit()

        # Kiểm tra bản ghi audit: staff_id chuyển thành None (SET NULL) nhưng staff_username vẫn còn nguyên
        audit_check = db.query(AuditLog).filter(AuditLog.id == temp_audit_id).first()
        assert audit_check is not None, "AuditLog không được phép bị mất khi xóa nhân viên"
        assert audit_check.staff_id is None, "staff_id phải chuyển thành NULL khi xóa staff"
        assert audit_check.staff_username == "test_temp_to_delete", "staff_username phải được giữ lại vĩnh viễn"
        print("✓ Test 2: Dấu vết kiểm toán bất biến: staff_username còn nguyên khi tài khoản bị xóa (SET NULL)")

        # -----------------------------------------------------------
        # TEST 3: Phân quyền GET /api/audit (401 unauth, 403 security, 200 manager)
        # -----------------------------------------------------------
        req_unauth = make_request("GET", "/api/audit", "")
        try:
            require_staff(req_unauth, db)
            assert False, "Chưa đăng nhập phải ném 401"
        except HTTPException as exc:
            assert exc.status_code == 401
            assert exc.detail == {"reason": "not_authenticated"}
        print("✓ Test 3a: Chưa đăng nhập gọi GET /api/audit bị chặn 401 not_authenticated")

        req_sec = make_request("GET", "/api/audit", f"session={sec_token}")
        sec_user = require_staff(req_sec, db)
        try:
            require_manager(sec_user)
            assert False, "Security gọi GET /api/audit phải ném 403"
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail == {"reason": "forbidden"}
        print("✓ Test 3b: Security gọi GET /api/audit bị chặn 403 forbidden")

        req_mgr = make_request("GET", "/api/audit", f"session={mgr_token}")
        mgr_user = require_staff(req_mgr, db)
        mgr_checked = require_manager(mgr_user)
        assert mgr_checked.role == "manager"
        print("✓ Test 3c: Manager xác thực thành công vào route GET /api/audit")

        # -----------------------------------------------------------
        # TEST 4: Các tính năng truy vấn GET /api/audit (limit, action, q, sắp xếp mới nhất)
        # -----------------------------------------------------------
        # 4a. Sắp xếp mới nhất trước
        audits_all = get_audit_logs(limit=200, current_staff=mgr, db=db)
        assert len(audits_all) >= 12
        # Kiểm tra thứ tự giảm dần
        for idx in range(len(audits_all) - 1):
            assert audits_all[idx].timestamp >= audits_all[idx + 1].timestamp

        # 4b. Lọc theo action
        audits_login = get_audit_logs(action="login", current_staff=mgr, db=db)
        for a in audits_login:
            assert a.action == "login"
        assert any(a.staff_username == mgr.username for a in audits_login)
        print("✓ Test 4a: Lọc theo action chính xác và sắp xếp mới nhất trước")

        # 4c. Tìm kiếm tự do theo q
        audits_q = get_audit_logs(q="Lý do: Khách bấm chuông", current_staff=mgr, db=db)
        assert len(audits_q) >= 1
        assert "Khách bấm chuông" in audits_q[0].detail
        print("✓ Test 4b: Tìm kiếm theo từ khóa q hoạt động chính xác")

        # 4d. Giới hạn limit
        audits_limit = get_audit_logs(limit=5, current_staff=mgr, db=db)
        assert len(audits_limit) == 5
        print("✓ Test 4c: Giới hạn số lượng limit hoạt động chính xác")

        # -----------------------------------------------------------
        # TEST 5: KIỂM TRA BẢO MẬT OPENAPI: KHÔNG CÓ BẤT KỲ ROUTE NÀO SỬA/XÓA AUDIT
        # -----------------------------------------------------------
        openapi_schema = app.openapi()
        paths = openapi_schema.get("paths", {})

        audit_methods = {}
        for path_name, path_item in paths.items():
            if "audit" in path_name.lower():
                audit_methods[path_name] = list(path_item.keys())

        # Đường dẫn liên quan audit chỉ có thể là GET /api/audit
        assert "/api/audit" in audit_methods, "Phải có đường dẫn /api/audit trong OpenAPI"
        methods = audit_methods["/api/audit"]
        assert methods == ["get"], f"Chỉ cho phép GET trên /api/audit, nhưng lại có {methods}"

        # Quét toàn bộ các route trong hệ thống xem có route nào chứa phương thức PUT/PATCH/DELETE đụng tới audit không
        for p, methods_map in paths.items():
            for m in methods_map:
                if "audit" in p.lower():
                    assert m.upper() == "GET", f"LỖ HỔNG: Tìm thấy route sửa/xóa audit: {m.upper()} {p}"

        print("✓ Test 5: Xác thực tuyệt đối từ openapi.json: KHÔNG tồn tại bất kỳ route nào sửa hoặc xóa audit_logs!")

        # -----------------------------------------------------------
        # TEST 6: MÔ PHỎNG LỖI GHI AUDIT KHI XÓA NHẬT KÝ -> ROLLBACK, KHÔNG CÓ DÒNG NÀO BỊ XÓA
        # -----------------------------------------------------------
        test_rollback_log = AccessLog(
            user_id=None,
            similarity=0.88,
            liveness=True,
            decision="granted",
            reason="TEST_Log_Rollback_Sim",
            timestamp=datetime.utcnow(),
        )
        db.add(test_rollback_log)
        db.commit()
        db.refresh(test_rollback_log)
        rollback_log_id = test_rollback_log.id

        # Monkeypatch audit_service.record để mô phỏng lỗi ghi audit
        orig_record = audit_service.record
        try:
            def failing_record(*args, **kwargs):
                raise RuntimeError("Mô phỏng sự cố cơ sở dữ liệu khi ghi audit log")

            audit_service.record = failing_record

            from api.logs import delete_logs, LogsDeleteRequest
            try:
                delete_logs(LogsDeleteRequest(ids=[rollback_log_id]), mgr, db)
                assert False, "delete_logs phải ném HTTPException 500 khi audit_service lỗi"
            except HTTPException as exc:
                assert exc.status_code == 500
                assert exc.detail.get("reason") == "database_error"

            # Xác minh dòng log vẫn tồn tại nguyên vẹn trong DB do đã rollback
            db.rollback()
            persisted_log = db.query(AccessLog).filter(AccessLog.id == rollback_log_id).first()
            assert persisted_log is not None, "Thao tác xóa phải bị rollback hoàn toàn khi ghi audit lỗi!"
            print("✓ Test 6: Mô phỏng lỗi ghi audit khi xóa nhật ký -> Rollback thành công, 0 dòng bị xóa!")
        finally:
            audit_service.record = orig_record

    finally:
        cleanup(db)
        db.close()
        print("✓ Đã dọn sạch toàn bộ dữ liệu thử nghiệm TEST_* và test_*")

    print("=== TẤT CẢ KIỂM THỬ B16 CP-04 ĐẠT 100% ===")


if __name__ == "__main__":
    main()
