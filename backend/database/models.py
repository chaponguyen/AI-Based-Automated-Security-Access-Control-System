# Agent 2 — cấu trúc chính thức: docs/context/DB_SCHEMA.md
from sqlalchemy import Column, Integer, String, DateTime, CheckConstraint, func
from database.database import Base


class User(Base):
    """Bảng lưu thông tin cư dân chung cư (CP-01, CP-02)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    age = Column(Integer, nullable=False)
    apartment_number = Column(String(20), nullable=False, index=True)

    # CP-02: Trạng thái và thời gian tạo
    status = Column(String(10), nullable=False, default="active", server_default="active")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("status in ('active','inactive')", name="ck_users_status"),
    )

    @property
    def user_code(self):
        """Mã định danh cư dân dạng USR000001 (property hiển thị, không lưu cột riêng)."""
        if self.id is None:
            return None
        return f"USR{self.id:06d}"
