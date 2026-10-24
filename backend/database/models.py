# Agent 2 — cấu trúc chính thức: docs/context/DB_SCHEMA.md
from sqlalchemy import (Column, Integer, String, Float, Boolean, ForeignKey,
                        DateTime, ARRAY, CheckConstraint, func)
from sqlalchemy.orm import relationship
from database.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(150), nullable=False)
    age = Column(Integer, nullable=False)
    apartment_number = Column(String(20), nullable=False, index=True)
    status = Column(String(10), nullable=False, default="active")   # active | inactive
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (CheckConstraint("status in ('active','inactive')"),)
    embeddings = relationship("FaceEmbedding", cascade="all, delete-orphan")

    @property
    def user_code(self):                      # hiển thị USR000001, không lưu cột riêng
        return f"USR{self.id:06d}"

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(ARRAY(Float), nullable=False)       # 512 chiều, đã chuẩn hóa L2
    quality = Column(Float)                                # điểm chất lượng khung hình
    model_version = Column(String(30), nullable=False)     # ví dụ buffalo_sc
    created_at = Column(DateTime, server_default=func.now())

class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)   # NULL: không xác định
    similarity = Column(Float)
    liveness = Column(Boolean)
    decision = Column(String(10), nullable=False)          # granted | denied
    reason = Column(String(80))
    timestamp = Column(DateTime, server_default=func.now(), index=True)
