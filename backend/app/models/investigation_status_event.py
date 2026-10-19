from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class InvestigationStatusEvent(Base):
    __tablename__ = "investigation_status_events"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status = Column(String(30), nullable=False)
    new_status = Column(String(30), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
