# Agent 2 — cấu trúc chính thức: docs/context/DB_SCHEMA.md
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    CheckConstraint,
    ForeignKey,
    ARRAY,
    func,
)
from sqlalchemy.orm import relationship
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

    # CP-04: Quan hệ 1-N với FaceEmbedding (xóa user thì xóa embeddings theo)
    embeddings = relationship(
        "FaceEmbedding",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def user_code(self):
        """Mã định danh cư dân dạng USR000001 (property hiển thị, không lưu cột riêng)."""
        if self.id is None:
            return None
        return f"USR{self.id:06d}"


class FaceEmbedding(Base):
    """Bảng lưu vector đặc trưng khuôn mặt (CP-03, CP-04)."""
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(ARRAY(Float), nullable=False)  # 512 chiều, đã chuẩn hóa L2, không dùng pgvector

    # CP-04: Điểm chất lượng, phiên bản model và thời gian tạo
    quality = Column(Float, nullable=True)
    model_version = Column(String(30), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="embeddings")
