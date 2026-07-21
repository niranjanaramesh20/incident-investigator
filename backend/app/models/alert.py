from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    metric = Column(String(100))
    timestamp = Column(DateTime, nullable=False)