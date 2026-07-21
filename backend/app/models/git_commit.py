from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.db.base import Base


class GitCommit(Base):
    __tablename__ = "git_commits"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    hash = Column(String(64), unique=True, nullable=False)
    author = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    branch = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False)