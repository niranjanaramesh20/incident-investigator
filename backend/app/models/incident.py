from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    severity = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())