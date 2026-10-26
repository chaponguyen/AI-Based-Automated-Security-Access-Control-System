#!/usr/bin/env python3
"""Script tạo tài khoản quản lý (manager) đầu tiên cho hệ thống (B15 CP-05).

Quy tắc bảo mật:
- Hỏi username, họ tên, và nhập mật khẩu 2 lần qua getpass (không lộ ký tự).
- Không đặt mật khẩu mặc định, không nhận mật khẩu qua tham số dòng lệnh.
- Từ chối nếu username đã tồn tại hoặc mật khẩu dưới 8 ký tự.
- Từ chối nếu hai lần nhập mật khẩu không khớp nhau.
- Chỉ tạo tài khoản với role='manager'.
- Tuyệt đối không in mật khẩu ra màn hình hoặc ghi log.
"""

import getpass
import os
import sys

# Thiết lập đường dẫn thư mục backend
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database.database import SessionLocal
from database.models import StaffAccount
from services import auth_service


def create_manager_interactive():
    print("=" * 60)
    print(" KHỞI TẠO TÀI KHOẢN QUẢN LÝ (ROLE: MANAGER) — B15 CP-05")
    print("=" * 60)

    # 1. Nhập username
    try:
        raw_username = input("Tên đăng nhập (username): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy thao tác.")
        sys.exit(0)

    if not raw_username:
        print("Lỗi: Tên đăng nhập không được để trống.", file=sys.stderr)
        sys.exit(1)

    username = raw_username.lower()

    # 2. Kiểm tra tồn tại trong CSDL
    db = SessionLocal()
    try:
        existing = db.query(StaffAccount).filter(StaffAccount.username == username).first()
        if existing:
            print(f"Lỗi: Tên đăng nhập '{username}' đã tồn tại trong hệ thống.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Lỗi truy vấn CSDL: {e}", file=sys.stderr)
        print("Gợi ý: Vui lòng đảm bảo CSDL đã chạy migration tạo bảng staff_accounts ('alembic upgrade head').", file=sys.stderr)
        sys.exit(1)

    # 3. Nhập họ tên
    try:
        full_name = input("Họ và tên đầy đủ: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy thao tác.")
        sys.exit(0)

    if not full_name:
        print("Lỗi: Họ và tên không được để trống.", file=sys.stderr)
        sys.exit(1)

    # 4. Nhập mật khẩu 2 lần bằng getpass
    try:
        password = getpass.getpass("Mật khẩu (tối thiểu 8 ký tự): ")
        password_confirm = getpass.getpass("Xác nhận lại mật khẩu: ")
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy thao tác.")
        sys.exit(0)

    # 5. Kiểm tra mật khẩu
    if len(password) < 8:
        print("Lỗi: Mật khẩu phải có độ dài tối thiểu 8 ký tự.", file=sys.stderr)
        sys.exit(1)

    if password != password_confirm:
        print("Lỗi: Hai lần nhập mật khẩu không khớp nhau.", file=sys.stderr)
        sys.exit(1)

    # 6. Băm mật khẩu scrypt và lưu vào CSDL
    try:
        pwd_hash = auth_service.hash_password(password)
        account = StaffAccount(
            username=username,
            full_name=full_name,
            password_hash=pwd_hash,
            role="manager",
            is_active=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        print("-" * 60)
        print(f"Tạo tài khoản quản lý thành công!")
        print(f"- ID: {account.id}")
        print(f"- Tên đăng nhập: {account.username}")
        print(f"- Họ tên: {account.full_name}")
        print(f"- Vai trò: {account.role}")
        print(f"- Trạng thái: active")
        print("-" * 60)
    except Exception as e:
        db.rollback()
        print(f"Lỗi khi lưu tài khoản vào CSDL: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_manager_interactive()
