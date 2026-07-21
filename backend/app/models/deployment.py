from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.base import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    version = Column(String(50), nullable=False)
    environment = Column(String(50), nullable=False)
    deployed_by = Column(String(100))
    timestamp = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)