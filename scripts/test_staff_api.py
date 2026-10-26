"""Kiểm thử tự động cho router quản lý nhân viên backend/api/staff.py (B16 CP-01).

Chạy:
  D:\\downloads\\AI-Security-Access-Control\\venv\\Scripts\\python.exe scripts/test_staff_api.py
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm backend vào sys.path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from starlette.requests import Request
from fastapi import HTTPException
from database.database import SessionLocal
from database.models import StaffAccount, StaffSession
from services import auth_service
from api import staff
from api.deps import require_staff, require_manager


def cleanup(db):
    """Xóa các tài khoản thử nghiệm có tiền tố test_."""
    test_staffs = db.query(StaffAccount).filter(StaffAccount.username.like("test_%")).all()
    for s in test_staffs:
        db.delete(s)
    db.commit()


def make_request(cookie_str: str = "") -> Request:
    headers = []
    if cookie_str:
        headers.append((b"cookie", cookie_str.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/staff",
        "headers": headers,
    }
    return Request(scope)


def main():
    db = SessionLocal()
    cleanup(db)

    print("=== BẮT ĐẦU KIỂM THỬ B16 CP-01 (API STAFF) ===")

    try:
        # 1. Tạo 2 tài khoản thử nghiệm: 1 manager, 1 security
        mgr_pw_hash = auth_service.hash_password("ManagerPass123")
        sec_pw_hash = auth_service.hash_password("SecurityPass123")

        mgr1 = StaffAccount(
            username="test_mgr_1",
            full_name="Quản lý kiểm thử 1",
            password_hash=mgr_pw_hash,
            role="manager",
            is_active=True,
        )
        sec1 = StaffAccount(
            username="test_sec_1",
            full_name="An ninh kiểm thử 1",
            password_hash=sec_pw_hash,
            role="security",
            is_active=True,
        )
        db.add_all([mgr1, sec1])
        db.commit()
        db.refresh(mgr1)
        db.refresh(sec1)

        # Tạo token phiên cho cả 2
        mgr1_token, _ = auth_service.create_session(db, mgr1.id)
        sec1_token, _ = auth_service.create_session(db, sec1.id)

        # -----------------------------------------------------------
        # TEST 1: Chưa đăng nhập (không cookie hoặc cookie sai) -> 401
        # -----------------------------------------------------------
        req_unauth = make_request("")
        try:
            require_staff(req_unauth, db)
            assert False, "Chưa đăng nhập phải ném HTTPException 401"
        except HTTPException as exc:
            assert exc.status_code == 401
            assert exc.detail == {"reason": "not_authenticated"}
        print("✓ Test 1: Chưa đăng nhập bị chặn 401 not_authenticated")

        # -----------------------------------------------------------
        # TEST 2: Security gọi require_manager -> 403
        # -----------------------------------------------------------
        req_sec = make_request(f"session={sec1_token}")
        sec_user = require_staff(req_sec, db)
        assert sec_user.role == "security"
        try:
            require_manager(sec_user)
            assert False, "Security phải ném HTTPException 403 khi vào route manager"
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail == {"reason": "forbidden"}
        print("✓ Test 2: Security gọi route require_manager bị chặn 403 forbidden")

        # -----------------------------------------------------------
        # TEST 3: Manager gọi get_staff_list -> 200 danh sách
        # -----------------------------------------------------------
        req_mgr = make_request(f"session={mgr1_token}")
        mgr_user = require_staff(req_mgr, db)
        assert mgr_user.role == "manager"
        mgr_checked = require_manager(mgr_user)
        assert mgr_checked.id == mgr1.id

        staff_list = staff.get_staff_list(db)
        assert isinstance(staff_list, list) and len(staff_list) >= 2
        # Kiểm tra serialize StaffResponse không chứa password hay password_hash
        for s in staff_list:
            res_dict = staff.StaffResponse.from_orm(s).dict()
            assert "password" not in res_dict
            assert "password_hash" not in res_dict
            assert "username" in res_dict
            assert "role" in res_dict
        print(f"✓ Test 3: Manager gọi get_staff_list thành công ({len(staff_list)} tài khoản, StaffResponse không lộ mật khẩu)")

        # -----------------------------------------------------------
        # TEST 4: Validation POST /api/staff (422)
        # -----------------------------------------------------------
        # 4a. Username ngắn (<3 ký tự)
        try:
            staff.create_staff(staff.StaffCreateRequest(username="ab", full_name="Tên hợp lệ", password="Password123", role="security"), mgr1, db)
            assert False, "Username ngắn phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422

        # 4b. Username chứa ký tự hoa hoặc ký tự không hợp lệ
        try:
            staff.create_staff(staff.StaffCreateRequest(username="user@test!", full_name="Tên hợp lệ", password="Password123", role="security"), mgr1, db)
            assert False, "Username có ký tự lạ phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422

        # 4c. Họ tên ngắn (<2 ký tự)
        try:
            staff.create_staff(staff.StaffCreateRequest(username="test_valid_u", full_name="A", password="Password123", role="security"), mgr1, db)
            assert False, "Họ tên ngắn phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422

        # 4d. Mật khẩu ngắn (<8 ký tự)
        try:
            staff.create_staff(staff.StaffCreateRequest(username="test_valid_u", full_name="Tên hợp lệ", password="123", role="security"), mgr1, db)
            assert False, "Mật khẩu ngắn phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422

        # 4e. Vai trò sai
        try:
            staff.create_staff(staff.StaffCreateRequest(username="test_valid_u", full_name="Tên hợp lệ", password="Password123", role="admin"), mgr1, db)
            assert False, "Vai trò sai phải ném 422"
        except HTTPException as exc:
            assert exc.status_code == 422
        print("✓ Test 4: Toàn bộ validation POST /api/staff hoạt động chuẩn xác (422)")

        # -----------------------------------------------------------
        # TEST 5: Tạo thành công POST /api/staff -> 201
        # -----------------------------------------------------------
        new_staff = staff.create_staff(
            staff.StaffCreateRequest(
                username="test_created_user",
                full_name="Nhân viên vừa tạo",
                password="PasswordTest123",
                role="security",
            ),
            mgr1,
            db,
        )
        assert new_staff.id > 0
        assert new_staff.username == "test_created_user"
        assert new_staff.role == "security"
        assert new_staff.is_active is True
        created_id = new_staff.id
        print(f"✓ Test 5: Tạo tài khoản mới thành công 201 (id={created_id})")

        # -----------------------------------------------------------
        # TEST 6: Trùng username -> 409 username_taken
        # -----------------------------------------------------------
        try:
            staff.create_staff(
                staff.StaffCreateRequest(
                    username="test_created_user",
                    full_name="Nhân viên trùng",
                    password="PasswordTest123",
                    role="security",
                ),
                mgr1,
                db,
            )
            assert False, "Trùng username phải ném 409"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "username_taken"}
        print("✓ Test 6: Trùng username trả 409 username_taken")

        # -----------------------------------------------------------
        # TEST 7: Luật tự bảo vệ (self_protected) trên PATCH
        # -----------------------------------------------------------
        # 7a. Tự tắt chính mình
        try:
            staff.update_staff(mgr1.id, staff.StaffUpdateRequest(is_active=False), mgr1, db)
            assert False, "Tự tắt tài khoản phải ném 409 self_protected"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "self_protected"}

        # 7b. Tự hạ quyền chính mình
        try:
            staff.update_staff(mgr1.id, staff.StaffUpdateRequest(role="security"), mgr1, db)
            assert False, "Tự hạ quyền tài khoản phải ném 409 self_protected"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "self_protected"}
        print("✓ Test 7: Luật tự bảo vệ self_protected chặn tự tắt và tự hạ quyền")

        # -----------------------------------------------------------
        # TEST 8: Luật tự bảo vệ trên DELETE
        # -----------------------------------------------------------
        try:
            staff.delete_staff(mgr1.id, mgr1, db)
            assert False, "Tự xóa tài khoản phải ném 409 self_protected"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "self_protected"}
        print("✓ Test 8: Luật tự bảo vệ self_protected chặn tự xóa chính mình")

        # -----------------------------------------------------------
        # TEST 9: Luật bảo vệ last_manager (khi chỉ còn 1 active manager)
        # -----------------------------------------------------------
        # Tạo thêm 1 manager test thứ 2
        mgr2 = StaffAccount(
            username="test_mgr_2",
            full_name="Quản lý kiểm thử 2",
            password_hash=mgr_pw_hash,
            role="manager",
            is_active=True,
        )
        db.add(mgr2)
        db.commit()
        db.refresh(mgr2)

        # Giả lập tình huống chỉ có 1 manager active duy nhất là mgr2 bằng cách tạm deact các manager khác
        other_active_mgrs = db.query(StaffAccount).filter(
            StaffAccount.role == "manager",
            StaffAccount.is_active == True,
            StaffAccount.id != mgr2.id,
        ).all()
        for m in other_active_mgrs:
            m.is_active = False
        db.commit()

        # Lúc này active manager chỉ có đúng mgr2 (count = 1)
        # Giả sử mgr2 bị ai đó hoặc thao tác nào đó hạ quyền hoặc tắt:
        # Giả lập gọi update_staff cho mgr2 với caller là 1 mock manager khác (nhưng hiện caller là mgr2)
        # Nếu caller là tài khoản khác mà cố tắt mgr2:
        mock_external_mgr = StaffAccount(id=999999, role="manager", is_active=True)
        try:
            staff.update_staff(mgr2.id, staff.StaffUpdateRequest(is_active=False), mock_external_mgr, db)
            assert False, "Tắt manager cuối cùng phải ném 409 last_manager"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "last_manager"}

        try:
            staff.update_staff(mgr2.id, staff.StaffUpdateRequest(role="security"), mock_external_mgr, db)
            assert False, "Hạ quyền manager cuối cùng phải ném 409 last_manager"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "last_manager"}

        try:
            staff.delete_staff(mgr2.id, mock_external_mgr, db)
            assert False, "Xóa manager cuối cùng phải ném 409 last_manager"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {"reason": "last_manager"}

        # Khôi phục trạng thái active cho các manager khác
        for m in other_active_mgrs:
            m.is_active = True
        db.commit()
        print("✓ Test 9: Luật bảo vệ last_manager chặn tắt, hạ quyền hoặc xóa manager cuối cùng")

        # -----------------------------------------------------------
        # TEST 10: PATCH đổi mật khẩu / đổi vai trò / tắt tài khoản THU HỒI PHIÊN
        # -----------------------------------------------------------
        # Tạo phiên cho test_created_user
        sec_created = db.query(StaffAccount).filter(StaffAccount.id == created_id).first()
        auth_service.create_session(db, sec_created.id)
        auth_service.create_session(db, sec_created.id)

        count_before = db.query(StaffSession).filter(StaffSession.staff_id == sec_created.id).count()
        assert count_before == 2, f"Phải có 2 phiên, thực tế {count_before}"

        # 10a. Đổi mật khẩu
        updated_staff = staff.update_staff(
            sec_created.id,
            staff.StaffUpdateRequest(password="NewPassword888"),
            mgr1,
            db,
        )
        assert updated_staff.id == sec_created.id
        count_after_pw = db.query(StaffSession).filter(StaffSession.staff_id == sec_created.id).count()
        assert count_after_pw == 0, f"Đổi mật khẩu phải thu hồi 100% phiên (thực tế còn {count_after_pw})"
        print("✓ Test 10a: Đổi mật khẩu đã thu hồi toàn bộ phiên làm việc")

        # 10b. Đổi vai trò
        auth_service.create_session(db, sec_created.id)
        updated_staff = staff.update_staff(
            sec_created.id,
            staff.StaffUpdateRequest(role="manager"),
            mgr1,
            db,
        )
        assert updated_staff.role == "manager"
        count_after_role = db.query(StaffSession).filter(StaffSession.staff_id == sec_created.id).count()
        assert count_after_role == 0, f"Đổi vai trò phải thu hồi 100% phiên (thực tế còn {count_after_role})"
        print("✓ Test 10b: Đổi vai trò đã thu hồi toàn bộ phiên làm việc")

        # 10c. Vô hiệu hóa tài khoản (is_active=False)
        auth_service.create_session(db, sec_created.id)
        updated_staff = staff.update_staff(
            sec_created.id,
            staff.StaffUpdateRequest(is_active=False),
            mgr1,
            db,
        )
        assert updated_staff.is_active is False
        count_after_deact = db.query(StaffSession).filter(StaffSession.staff_id == sec_created.id).count()
        assert count_after_deact == 0, f"Vô hiệu hóa phải thu hồi 100% phiên (thực tế còn {count_after_deact})"
        print("✓ Test 10c: Vô hiệu hóa tài khoản đã thu hồi toàn bộ phiên làm việc")

        # -----------------------------------------------------------
        # TEST 11: DELETE /api/staff/{id}
        # -----------------------------------------------------------
        # 11a. Xóa ID không tồn tại -> 404
        try:
            staff.delete_staff(999999, mgr1, db)
            assert False, "Xóa ID không tồn tại phải ném 404"
        except HTTPException as exc:
            assert exc.status_code == 404
            assert exc.detail == {"reason": "not_found"}
        print("✓ Test 11a: Xóa tài khoản không tồn tại trả 404 not_found")

        # 11b. Xóa tài khoản hợp lệ -> 200 {"ok": True}
        res_del = staff.delete_staff(sec_created.id, mgr1, db)
        assert res_del == {"ok": True}
        check_del = db.query(StaffAccount).filter(StaffAccount.id == sec_created.id).first()
        assert check_del is None
        print("✓ Test 11b: Xóa tài khoản thành công trả 200 {'ok': True}")

    finally:
        cleanup(db)
        db.close()
        print("✓ Đã dọn dẹp sạch toàn bộ tài khoản thử nghiệm test_*")

    print("=== TẤT CẢ KIỂM THỬ B16 CP-01 ĐẠT 100% ===")


if __name__ == "__main__":
    main()
