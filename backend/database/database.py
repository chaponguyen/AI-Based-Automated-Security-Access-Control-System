# Agent 2
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()
# Nạp thêm từ file .env trong thư mục backend nếu chạy từ thư mục gốc
_backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False) if engine else None
Base = declarative_base()


def get_db():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL chưa được cấu hình trong .env")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

