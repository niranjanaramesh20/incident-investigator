from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Float
from sqlalchemy.sql import func

from app.db.base import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True)
    dataset_version = Column(Integer, nullable=False)
    initiated_by = Column(String(254), nullable=False)
    case_count = Column(Integer, nullable=False)
    passed_count = Column(Integer, nullable=False)
    pass_rate = Column(Float, nullable=False)
    mean_confidence = Column(Float, nullable=False)
    validation_rate = Column(Float, nullable=False)
    citation_rate = Column(Float, nullable=False)
    results = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="queued", server_default="queued")
    completed_cases = Column(Integer, nullable=False, default=0, server_default="0")
    current_case = Column(String(200))
    error = Column(String(2_000))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
