from sqlalchemy import Boolean, Column, DateTime, Integer, String, true
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(300), nullable=False)
    role = Column(String(20), nullable=False, default="viewer", server_default="viewer")
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
