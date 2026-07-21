from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.base import Base

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    host = Column(String(100))
    trace_id = Column(String(100))