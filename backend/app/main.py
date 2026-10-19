import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles

from app.ingestion.sample_data import load_sample_documents
from app.investigation.confidence_scorer import ConfidenceScorer
from app.investigation.evidence_validator import EvidenceValidator
from app.investigation.investigation_engine import InvestigationEngine
from app.investigation.report_generator import ReportGenerator
from app.db.database import SessionLocal
from app.models.incident import Incident
from app.models.investigation import Investigation
from app.rag.query_processor import QueryProcessor
from app.rag.reranker import Reranker
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.investigation_service import InvestigationService

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(
    title="Incident Investigation System",
    version="1.0.0",
    description="Investigate incidents using indexed logs, alerts, deployments, commits, and runbooks.",
)
bearer_auth = HTTPBearer(auto_error=False)


class InvestigationRequest(BaseModel):
    incident: str = Field(min_length=1, max_length=10_000)
    question: str = Field(min_length=1, max_length=2_000)
    service: str | None = Field(default=None, min_length=1, max_length=100)
    source_type: Literal["alert", "deployment", "git_commit", "log", "runbook"] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    @field_validator("incident", "question")
    @classmethod
    def strip_and_validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("service")
    @classmethod
    def strip_service(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            raise ValueError("service cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.start_time and self.end_time:
            start_time = self.start_time
            end_time = self.end_time
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            if start_time > end_time:
                raise ValueError("start_time must be earlier than or equal to end_time.")
        return self


_investigation_service = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
):
    configured_token = os.getenv("API_ACCESS_TOKEN", "")
    if len(configured_token) < 32:
        raise HTTPException(
            status_code=503,
            detail="Set API_ACCESS_TOKEN to a random value of at least 32 characters.",
        )
    if credentials is None or not secrets.compare_digest(
        credentials.credentials, configured_token
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def build_evidence_filters(request: InvestigationRequest) -> dict | None:
    filters = []
    if request.service:
        filters.append({"service": request.service})
    if request.source_type:
        filters.append({"source_type": request.source_type})

    time_filter = {}
    if request.start_time:
        start_time = request.start_time
        if start_time.tzinfo:
            start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        time_filter["$gte"] = start_time.isoformat()
    if request.end_time:
        end_time = request.end_time
        if end_time.tzinfo:
            end_time = end_time.astimezone(timezone.utc).replace(tzinfo=None)
        time_filter["$lte"] = end_time.isoformat()
    if time_filter:
        filters.append({"timestamp": time_filter})

    if not filters:
        return None
    return filters[0] if len(filters) == 1 else {"$and": filters}


def get_investigation_service():
    global _investigation_service
    if _investigation_service is not None:
        return _investigation_service
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is required to run an investigation.",
        )

    try:
        vector_store = VectorStore()
        if vector_store.is_empty():
            sample_documents = load_sample_documents()
            if sample_documents:
                vector_store.add_documents(sample_documents)

        _investigation_service = InvestigationService(
            query_processor=QueryProcessor(),
            retriever=Retriever(vector_store),
            reranker=Reranker(),
            investigation_engine=InvestigationEngine(),
            evidence_validator=EvidenceValidator(),
            confidence_scorer=ConfidenceScorer(),
            report_generator=ReportGenerator(),
        )
        return _investigation_service
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not initialize the investigation pipeline: {error}",
        ) from error

@app.get("/")
async def root():
    return {
        "message": "Incident Investigation API"
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Report database, API-key, and local vector-index readiness."""
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "unavailable"
        db.rollback()

    vector_path = Path(
        os.getenv(
            "CHROMA_PERSIST_DIRECTORY",
            str(Path(__file__).resolve().parents[1] / "data" / "chroma_db"),
        )
    )
    vector_status = (
        "initialized"
        if vector_path.is_dir() and any(vector_path.iterdir())
        else "not_initialized"
    )
    checks = {
        "database": database_status,
        "openai_api_key": "configured" if os.getenv("OPENAI_API_KEY") else "missing",
        "api_access_token": (
            "configured"
            if len(os.getenv("API_ACCESS_TOKEN", "")) >= 32
            else "missing_or_too_short"
        ),
        "vector_store": vector_status,
    }
    ready = (
        database_status == "ok"
        and checks["openai_api_key"] == "configured"
        and checks["api_access_token"] == "configured"
        and vector_status == "initialized"
    )
    return {"status": "ready" if ready else "degraded", "ready": ready, "checks": checks}


@app.get("/auth/check", dependencies=[Depends(require_api_token)])
def check_authentication():
    """Verify that the supplied bearer token is accepted."""
    return {"authenticated": True}


@app.post("/investigate", dependencies=[Depends(require_api_token)])
def investigate(request: InvestigationRequest, db: Session = Depends(get_db)):
    """Return a root-cause report for an incident and investigation question."""
    try:
        service = get_investigation_service()
        evidence_filters = build_evidence_filters(request)
        report = service.investigate(
            request.incident,
            request.question,
            filters=evidence_filters,
        )
        report["filters"] = {
            "service": request.service,
            "source_type": request.source_type,
            "start_time": request.start_time.isoformat() if request.start_time else None,
            "end_time": request.end_time.isoformat() if request.end_time else None,
        }

        incident = Incident(
            title=request.incident.splitlines()[0][:200],
            description=request.incident,
            severity="unknown",
            status="investigating",
            start_time=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(incident)
        db.flush()

        investigation = Investigation(
            incident_id=incident.id,
            question=request.question,
            generated_answer=report["investigation_result"],
            confidence=report["confidence_score"],
            report=report,
        )
        db.add(investigation)
        db.commit()
        db.refresh(investigation)
        return {
            **report,
            "investigation_id": investigation.id,
            "incident_id": incident.id,
            "created_at": investigation.created_at.isoformat()
            if investigation.created_at
            else None,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=f"The investigation could not be completed or saved: {error}",
        ) from error


@app.get("/investigations", dependencies=[Depends(require_api_token)])
def list_investigations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List saved investigations, newest first."""
    records = (
        db.query(Investigation, Incident)
        .join(Incident, Investigation.incident_id == Incident.id)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "investigation_id": investigation.id,
            "incident_id": incident.id,
            "incident": incident.description,
            "question": investigation.question,
            "investigation_result": investigation.generated_answer,
            "confidence_score": investigation.confidence,
            "created_at": investigation.created_at.isoformat()
            if investigation.created_at
            else None,
        }
        for investigation, incident in records
    ]


@app.get(
    "/investigations/{investigation_id}",
    dependencies=[Depends(require_api_token)],
)
def get_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    """Return a saved report, including its evidence, by investigation ID."""
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    incident = db.get(Incident, investigation.incident_id)
    return {
        "investigation_id": investigation.id,
        "incident_id": investigation.incident_id,
        "incident": incident.description if incident else None,
        "question": investigation.question,
        "investigation_result": investigation.generated_answer,
        "confidence_score": investigation.confidence,
        "created_at": investigation.created_at.isoformat()
        if investigation.created_at
        else None,
        "report": investigation.report,
    }


app.mount(
    "/ui",
    StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True),
    name="ui",
)
