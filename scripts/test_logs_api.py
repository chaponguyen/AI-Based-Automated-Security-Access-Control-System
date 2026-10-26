"""Kiểm thử tự động cho router logs: thêm id vào GET và POST /api/logs/delete (B16 CP-03).

Chạy:
  D:\\downloads\\AI-Security-Access-Control\\venv\\Scripts\\python.exe scripts/test_logs_api.py
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
from services import auth_service
from api.logs import get_logs, delete_logs, LogsDeleteRequest
from api.deps import require_staff, require_manager


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


def make_request(method: str = "GET", path: str = "/api/logs", cookie_str: str = "") -> Request:
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

    print("=== BẮT ĐẦU KIỂM THỬ B16 CP-03 (GET LOGS CÓ ID & POST LOGS/DELETE) ===")

    try:
        # 1. Tạo tài khoản manager và security
        mgr_pw_hash = auth_service.hash_password("ManagerPass123")
        sec_pw_hash = auth_service.hash_password("SecurityPass123")

        mgr = StaffAccount(
            username="test_mgr_logs",
            full_name="Quản lý xóa log",
            password_hash=mgr_pw_hash,
            role="manager",
            is_active=True,
        )
        sec = StaffAccount(
            username="test_sec_logs",
            full_name="An ninh thử nghiệm log",
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

        # Tạo user test để liên kết với logs
        test_user = User(
            full_name="TEST_User_Logs",
            age=30,
            apartment_number="TEST_LOG_101",
            status="active",
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        # Tạo mẫu 10 dòng access_logs TEST_ ở các mốc thời gian khác nhau
        now = datetime.utcnow()
        created_log_ids = []
        for i in range(10):
            t = now - timedelta(days=10 - i, hours=i)
            entry = AccessLog(
                user_id=test_user.id,
                similarity=0.75 + (i * 0.02),
                liveness=True,
                decision="granted" if i % 2 == 0 else "denied",
                reason=f"TEST_Log_Item_{i}",
                timestamp=t,
            )
            db.add(entry)
            db.flush()
            created_log_ids.append((entry.id, t))
        db.commit()

        # Tạo 1 dòng audit_logs để xác minh không bao giờ bị đụng tới
        test_audit_entry = AuditLog(
            staff_id=mgr.id,
            staff_username=mgr.username,
            action="test_action",
            target_type="test",
            target_id="1",
            detail="Bản ghi kiểm toán thử nghiệm",
            timestamp=now,
        )
        db.add(test_audit_entry)
        db.commit()
        audit_count_before = db.query(AuditLog).count()

        # -----------------------------------------------------------
        # TEST 1: GET /api/logs phải có trường 'id' trong mỗi dòng
        # -----------------------------------------------------------
        # Kiểm tra require_staff cho GET
        req_unauth = make_request("GET", "/api/logs", "")
        try:
            require_staff(req_unauth, db)
            assert False, "GET logs chưa đăng nhập phải ném 401"
        except HTTPException as exc:
            assert exc.status_code == 401
            assert exc.detail == {"reason": "not_authenticated"}
        print("✓ Test 1a: Chưa đăng nhập gọi GET /api/logs bị chặn 401 not_authenticated")

        # Gọi get_logs
        logs_res = get_logs(q="TEST_User_Logs", db=db)
        assert len(logs_res) == 10, f"Phải tìm thấy 10 dòng test, thực tế {len(logs_res)}"
        for item in logs_res:
            assert hasattr(item, "id") and item.id is not None, "Mỗi dòng trong get_logs phải có trường 'id'"
            assert isinstance(item.id, int)
            assert item.decision in ("granted", "denied")
        print(f"✓ Test 1b: GET /api/logs trả về đầy đủ trường 'id' cho mỗi dòng (mẫu id={logs_res[0].id})")

        # -----------------------------------------------------------
        # TEST 2: Phân quyền POST /api/logs/delete (401 unauth, 403 security)
        # -----------------------------------------------------------
        req_del_unauth = make_request("POST", "/api/logs/delete", "")
        try:
            require_staff(req_del_unauth, db)
            assert False, "Chưa đăng nhập gọi delete logs phải ném 401"
        except HTTPException as exc:
            assert exc.status_code == 401
            assert exc.detail == {"reason": "not_authenticated"}
        print("✓ Test 2a: Chưa đăng nhập gọi POST /api/logs/delete bị chặn 401 not_authenticated")

        req_del_sec = make_request("POST", "/api/logs/delete", f"session={sec_token}")
        sec_user = require_staff(req_del_sec, db)
        try:
            require_manager(sec_user)
            assert False, "Security gọi delete logs phải ném 403"
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail == {"reason": "forbidden"}
        print("✓ Test 2b: Security gọi POST /api/logs/delete bị chặn 403 forbidden")

        # -----------------------------------------------------------
        # TEST 3: Validation POST /api/logs/delete (422)
        # -----------------------------------------------------------
        # 3a. Thân yêu cầu rỗng hoàn toàn -> 422 (KHÔNG BAO GIỜ xóa hết)
        try:
            delete_logs(LogsDeleteRequest(), mgr, db)
            assert False, "Thân rỗng phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail.get("reason") == "invalid_request"

        # 3b. ids rỗng -> 422
        try:
            delete_logs(LogsDeleteRequest(ids=[]), mgr, db)
            assert False, "ids rỗng phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail.get("reason") == "invalid_request"

        # 3c. ids vượt quá 1000 phần tử -> 422
        try:
            delete_logs(LogsDeleteRequest(ids=list(range(1001))), mgr, db)
            assert False, "ids > 1000 phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail.get("reason") == "invalid_request"

        # 3d. Chỉ có from mà không có to -> 422
        try:
            delete_logs(LogsDeleteRequest(from_time="2026-10-20T00:00:00"), mgr, db)
            assert False, "Chỉ có from phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422

        # 3e. Chỉ có to mà không có from -> 422
        try:
            delete_logs(LogsDeleteRequest(to_time="2026-10-20T00:00:00"), mgr, db)
            assert False, "Chỉ có to phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422

        # 3f. Sai định dạng ISO -> 422
        try:
            delete_logs(LogsDeleteRequest(from_time="ngay-hom-qua", to_time="ngay-mai"), mgr, db)
            assert False, "Sai định dạng ngày phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail.get("reason") == "invalid_format"

        # 3g. from > to -> 422
        try:
            delete_logs(LogsDeleteRequest(from_time="2026-10-25T12:00:00", to_time="2026-10-20T12:00:00"), mgr, db)
            assert False, "from > to phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail.get("reason") == "invalid_range"
        print("✓ Test 3: Toàn bộ điều kiện validation POST /api/logs/delete đạt 422 chính xác")

        # -----------------------------------------------------------
        # TEST 4: Xóa theo ids cụ thể -> 200 {"deleted": n}
        # -----------------------------------------------------------
        target_ids_to_del = [created_log_ids[0][0], created_log_ids[1][0], created_log_ids[2][0]]
        res_del_ids = delete_logs(LogsDeleteRequest(ids=target_ids_to_del), mgr, db)
        assert res_del_ids == {"deleted": 3}, f"Phải xóa đúng 3 dòng, thực tế {res_del_ids}"

        # Kiểm tra trong DB các id này đã biến mất
        remaining_target_ids = db.query(AccessLog).filter(AccessLog.id.in_(target_ids_to_del)).count()
        assert remaining_target_ids == 0
        print("✓ Test 4: Xóa log theo danh sách ids thành công ({deleted: 3})")

        # -----------------------------------------------------------
        # TEST 5: Xóa theo khoảng thời gian from - to -> 200 {"deleted": n}
        # -----------------------------------------------------------
        # Chọn khoảng thời gian bao trùm 4 dòng kế tiếp: created_log_ids[3..6]
        start_t = created_log_ids[3][1] - timedelta(minutes=10)
        end_t = created_log_ids[6][1] + timedelta(minutes=10)
        ids_in_range = [created_log_ids[i][0] for i in range(3, 7)]

        res_del_range = delete_logs(
            LogsDeleteRequest(
                from_time=start_t.isoformat(),
                to_time=end_t.isoformat(),
            ),
            mgr,
            db,
        )
        assert res_del_range == {"deleted": 4}, f"Phải xóa đúng 4 dòng trong khoảng, thực tế {res_del_range}"

        remaining_range = db.query(AccessLog).filter(AccessLog.id.in_(ids_in_range)).count()
        assert remaining_range == 0
        print(f"✓ Test 5: Xóa log theo khoảng thời gian thành công ({res_del_range})")

        # -----------------------------------------------------------
        # TEST 6: BẢO VỆ TUYỆT ĐỐI audit_logs: KHÔNG BAO GIỜ BỊ ĐỤNG TỚI
        # -----------------------------------------------------------
        audit_count_after = db.query(AuditLog).count()
        assert audit_count_after == audit_count_before, f"Bảng audit_logs không được thay đổi số lượng ({audit_count_before} vs {audit_count_after})"
        audit_exists = db.query(AuditLog).filter(AuditLog.id == test_audit_entry.id).first()
        assert audit_exists is not None, "Dòng audit_logs thử nghiệm phải còn nguyên vẹn"
        print(f"✓ Test 6: Bảng audit_logs bất biến tuyệt đối (trước: {audit_count_before}, sau: {audit_count_after})")

    finally:
        cleanup(db)
        db.close()
        print("✓ Đã dọn sạch toàn bộ dữ liệu thử nghiệm TEST_* và test_*")

    print("=== TẤT CẢ KIỂM THỬ B16 CP-03 ĐẠT 100% ===")


if __name__ == "__main__":
    main()
