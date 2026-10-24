# Agent 2 — cấu trúc chính thức: docs/context/DB_SCHEMA.md
from sqlalchemy import Column, Integer, String
from database.database import Base


class User(Base):
    """Bảng lưu thông tin cư dân chung cư (CP-01)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    age = Column(Integer, nullable=False)
    apartment_number = Column(String(20), nullable=False, index=True)
