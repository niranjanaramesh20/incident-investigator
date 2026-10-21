from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from app.db.base import Base


class EvaluationCaseSet(Base):
    __tablename__ = "evaluation_case_sets"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False, unique=True)
    cases = Column(JSON, nullable=False)
    change_summary = Column(String(500), nullable=False)
    created_by = Column(String(254), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
