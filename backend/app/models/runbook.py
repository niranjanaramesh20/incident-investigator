from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.db.base import Base


class Runbook(Base):
    __tablename__ = "runbooks"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    last_updated = Column(DateTime, nullable=False)