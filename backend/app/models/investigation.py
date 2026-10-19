from sqlalchemy import Column, Integer, Text, Float, DateTime, ForeignKey, JSON, String
from sqlalchemy.sql import func
from app.db.base import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    question = Column(Text, nullable=False)
    generated_answer = Column(Text)
    confidence = Column(Float)
    report = Column(JSON)
    status = Column(String(30), nullable=False, default="open", server_default="open")
    assignee = Column(String(254))
    assignee_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
