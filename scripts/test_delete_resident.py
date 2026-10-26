"""Kiểm thử tự động cho route DELETE /api/residents/{id} (B16 CP-02).

Chạy:
  D:\\downloads\\AI-Security-Access-Control\\venv\\Scripts\\python.exe scripts/test_delete_resident.py
"""

import sys
import os
import numpy as np

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
from database.models import User, FaceEmbedding, AccessLog, StaffAccount
from services import auth_service, gallery_cache
from ai.matcher import best_match
from api.residents import delete_resident
from api.deps import require_staff, require_manager


def cleanup(db):
    """Xóa dữ liệu thử nghiệm có tiền tố TEST_ hoặc test_."""
    # Xóa embeddings và user TEST_
    test_users = db.query(User).filter(User.full_name.like("TEST_%")).all()
    for u in test_users:
        db.delete(u)
    # Xóa access_logs test
    test_logs = db.query(AccessLog).filter(AccessLog.reason.like("TEST_%")).all()
    for l in test_logs:
        db.delete(l)
    # Xóa staff test
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
        "method": "DELETE",
        "path": "/api/residents/1",
        "headers": headers,
    }
    return Request(scope)


def main():
    db = SessionLocal()
    cleanup(db)

    print("=== BẮT ĐẦU KIỂM THỬ B16 CP-02 (XÓA CƯ DÂN & RELOAD GALLERY CACHE) ===")

    try:
        # 1. Tạo tài khoản manager và security để kiểm tra phân quyền
        mgr_pw_hash = auth_service.hash_password("ManagerPass123")
        sec_pw_hash = auth_service.hash_password("SecurityPass123")

        mgr = StaffAccount(
            username="test_mgr_del",
            full_name="Quản lý xóa cư dân",
            password_hash=mgr_pw_hash,
            role="manager",
            is_active=True,
        )
        sec = StaffAccount(
            username="test_sec_del",
            full_name="An ninh thử nghiệm",
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
        # TEST 1: Kiểm tra phân quyền chưa đăng nhập & security
        # -----------------------------------------------------------
        req_unauth = make_request("")
        try:
            require_staff(req_unauth, db)
            assert False, "Chưa đăng nhập phải ném 401"
        except HTTPException as exc:
            assert exc.status_code == 401
            assert exc.detail == {"reason": "not_authenticated"}
        print("✓ Test 1a: Chưa đăng nhập bị chặn 401 not_authenticated")

        req_sec = make_request(f"session={sec_token}")
        sec_user = require_staff(req_sec, db)
        try:
            require_manager(sec_user)
            assert False, "Security gọi delete_resident phải ném 403"
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail == {"reason": "forbidden"}
        print("✓ Test 1b: Security gọi DELETE /api/residents/{id} bị chặn 403 forbidden")

        # -----------------------------------------------------------
        # TEST 2: Đăng ký thử cư dân tên 'TEST_NguyenVanA' kèm 5 vector khuôn mặt
        # -----------------------------------------------------------
        test_user = User(
            full_name="TEST_NguyenVanA",
            age=28,
            apartment_number="TEST_902",
            status="active",
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        user_id = test_user.id
        user_code = test_user.user_code

        # Tạo vector đặc trưng giả lập 512 chiều chuẩn hóa L2
        rng = np.random.RandomState(42)
        base_vec = rng.randn(512).astype(np.float32)
        base_vec = base_vec / np.linalg.norm(base_vec)

        for i in range(5):
            noise = rng.randn(512).astype(np.float32) * 0.002
            emb = base_vec + noise
            emb = emb / np.linalg.norm(emb)
            fe = FaceEmbedding(
                user_id=user_id,
                embedding=emb.tolist(),
                quality=0.95,
                model_version="buffalo_sc",
            )
            db.add(fe)

        # Tạo 1 dòng access_logs liên kết với cư dân này để kiểm tra ON DELETE SET NULL
        log_entry = AccessLog(
            user_id=user_id,
            similarity=0.85,
            liveness=True,
            decision="granted",
            reason="TEST_LogEntryBeforeDelete",
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        log_id = log_entry.id

        # -----------------------------------------------------------
        # TEST 3: Nạp GalleryCache và xác nhận nhận diện được cư dân
        # -----------------------------------------------------------
        gallery_cache.reload(db)
        cached_u = gallery_cache.get_user(user_id)
        assert cached_u is not None, "GalleryCache phải chứa TEST_NguyenVanA"
        assert cached_u.full_name == "TEST_NguyenVanA"

        # So khớp vector khuôn mặt: phải nhận ra user_id này với độ tương đồng rất cao (> 0.90)
        match_id, match_sim = best_match(base_vec, gallery_cache.get_gallery())
        assert match_id == user_id, f"Phải nhận diện ra user_id={user_id}, nhưng được {match_id}"
        assert match_sim > 0.90, f"Độ tương đồng phải > 0.90, thực tế {match_sim}"
        print(f"✓ Test 2 & 3: Đăng ký thành công cư dân '{test_user.full_name}' (id={user_id}, {user_code}) và xác nhận nhận diện được (similarity={match_sim:.4f})")

        # -----------------------------------------------------------
        # TEST 4: Gọi DELETE /api/residents/{id} từ vai trò manager
        # -----------------------------------------------------------
        res_del = delete_resident(user_id, current_staff=mgr, db=db)
        assert res_del["ok"] is True
        assert res_del["deleted"]["id"] == user_id
        assert res_del["deleted"]["user_code"] == user_code
        assert res_del["deleted"]["full_name"] == "TEST_NguyenVanA"
        print(f"✓ Test 4: DELETE /api/residents/{user_id} trả về đúng contract: {res_del}")

        # -----------------------------------------------------------
        # TEST 5: Kiểm tra CSDL sau khi xóa
        # -----------------------------------------------------------
        # 5a. User đã bị xóa
        db_user = db.query(User).filter(User.id == user_id).first()
        assert db_user is None, "User phải không còn trong CSDL"

        # 5b. FaceEmbedding đã bị xóa CASCADE
        emb_count = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == user_id).count()
        assert emb_count == 0, f"Embeddings phải bị xóa CASCADE (thực tế còn {emb_count})"

        # 5c. AccessLog giữ lại với user_id là NULL
        db_log = db.query(AccessLog).filter(AccessLog.id == log_id).first()
        assert db_log is not None, "AccessLog không được phép bị xóa"
        assert db_log.user_id is None, f"AccessLog.user_id phải chuyển thành NULL, nhưng là {db_log.user_id}"
        print("✓ Test 5: CSDL toàn vẹn: User bị xóa, FaceEmbedding xóa CASCADE, AccessLog giữ lại với user_id=NULL")

        # -----------------------------------------------------------
        # TEST 6: Xác nhận GalleryCache NGAY LẬP TỨC không còn nhận diện
        # -----------------------------------------------------------
        cached_after = gallery_cache.get_user(user_id)
        assert cached_after is None, "GalleryCache phải không còn chứa cư dân vừa bị xóa"

        gallery_after = gallery_cache.get_gallery()
        assert user_id not in gallery_after, "Gallery vector phải không còn chứa vector của user_id vừa bị xóa"

        match_id_after, match_sim_after = best_match(base_vec, gallery_after)
        assert match_id_after != user_id, f"Khuôn mặt đã xóa KHÔNG được phép nhận diện lại (nhận ra {match_id_after})"
        print(f"✓ Test 6: GalleryCache đã nạp lại tức thì: khuôn mặt không còn được nhận ra (match_id={match_id_after})")

        # -----------------------------------------------------------
        # TEST 7: Xóa lại ID vừa xóa -> 404 not_found
        # -----------------------------------------------------------
        try:
            delete_resident(user_id, current_staff=mgr, db=db)
            assert False, "Xóa ID không tồn tại phải ném 404"
        except HTTPException as exc:
            assert exc.status_code == 404
            assert exc.detail == {"reason": "not_found"}
        print("✓ Test 7: Xóa ID không tồn tại trả về 404 not_found")

    finally:
        cleanup(db)
        gallery_cache.reload(db)
        db.close()
        print("✓ Đã dọn sạch toàn bộ dữ liệu thử nghiệm TEST_* và test_*")

    print("=== TẤT CẢ KIỂM THỬ B16 CP-02 ĐẠT 100% ===")


if __name__ == "__main__":
    main()
