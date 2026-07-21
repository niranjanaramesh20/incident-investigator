from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("investigations.id"),
        nullable=False
    )
    source_type = Column(String(50), nullable=False)
    source_id = Column(Integer, nullable=False)
    relevance_score = Column(Float)