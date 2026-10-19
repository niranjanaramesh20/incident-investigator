from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.sql import func

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message = Column(String(300), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
