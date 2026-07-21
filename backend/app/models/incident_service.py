from sqlalchemy import Column, Integer, ForeignKey
from app.db.base import Base


class IncidentService(Base):
    __tablename__ = "incident_services"

    incident_id = Column(
        Integer,
        ForeignKey("incidents.id"),
        primary_key=True
    )

    service_id = Column(
        Integer,
        ForeignKey("services.id"),
        primary_key=True
    )