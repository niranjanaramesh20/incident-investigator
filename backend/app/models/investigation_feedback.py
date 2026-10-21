from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class InvestigationFeedback(Base):
    __tablename__ = "investigation_feedback"
    __table_args__ = (UniqueConstraint("investigation_id", "user_id", name="uq_feedback_investigation_user"),)

    id = Column(Integer, primary_key=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(String(20), nullable=False)
    comment = Column(Text)
    correction_target = Column(String(500))
    corrected_cause = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
