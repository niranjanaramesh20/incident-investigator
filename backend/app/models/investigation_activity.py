from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class InvestigationActivity(Base):
    __tablename__ = "investigation_activities"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type = Column(String(30), nullable=False)
    actor = Column(String(100))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    details = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
