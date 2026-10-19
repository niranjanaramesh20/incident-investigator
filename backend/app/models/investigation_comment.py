from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class InvestigationComment(Base):
    __tablename__ = "investigation_comments"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
