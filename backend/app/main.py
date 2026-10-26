import asyncio
import ipaddress
import os
import hashlib
import json
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from app.ingestion.sample_data import load_sample_documents
from app.investigation.confidence_scorer import ConfidenceScorer
from app.investigation.evidence_validator import EvidenceValidator
from app.investigation.investigation_engine import InvestigationEngine
from app.investigation.report_generator import ReportGenerator
from app.auth import create_session_token, current_user, get_db, hash_password, require_admin, require_analyst, require_analyst_or_public, verify_password
from app.models.incident import Incident
from app.models.investigation import Investigation
from app.models.investigation_feedback import InvestigationFeedback
from app.models.evaluation_run import EvaluationRun
from app.models.evaluation_case_set import EvaluationCaseSet
from app.models.investigation_status_event import InvestigationStatusEvent
from app.models.investigation_comment import InvestigationComment
from app.models.investigation_activity import InvestigationActivity
from app.models.notification import Notification
from app.models.user import User
from app.notifications import send_external_notification
from app.preprocessing.data_preprocessing import DataPreprocessor
from app.rag.query_processor import QueryProcessor
from app.rag.reranker import Reranker
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.investigation_service import InvestigationService
from app.evaluations.runner import get_or_create_case_set, execute_run

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(
    title="Incident Investigation System",
    version="1.0.0",
    description="Investigate incidents using indexed logs, alerts, deployments, commits, and runbooks.",
)

_public_rate_limit_requests: dict[str, deque[float]] = {}
_public_investigation_lock = asyncio.Lock()
_public_rate_limit_last_cleanup = 0.0


@app.middleware("http")
async def limit_public_investigations(request: Request, call_next):
    global _public_rate_limit_last_cleanup
    is_public = os.getenv("ALLOW_PUBLIC_ACCESS", "false").lower() == "true"
    if not is_public or request.method != "POST" or request.url.path not in {"/investigate", "/evidence"}:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
        proxy_ip = request.headers.get("x-real-ip", "").strip()
        try:
            client_ip = str(ipaddress.ip_address(proxy_ip))
        except ValueError:
            pass

    def configured_limit(name: str, default: int) -> int:
        try:
            return max(1, int(os.getenv(name, str(default))))
        except ValueError:
            return default

    if request.url.path == "/investigate":
        window_seconds = 60
        per_window = configured_limit("PUBLIC_INVESTIGATIONS_PER_MINUTE", 5)
        per_day = configured_limit("PUBLIC_INVESTIGATIONS_PER_DAY", 30)
    else:
        window_seconds = 3_600
        per_window = configured_limit("PUBLIC_EVIDENCE_UPLOADS_PER_HOUR", 2)
        per_day = configured_limit("PUBLIC_EVIDENCE_UPLOADS_PER_DAY", 10)
    now = time.monotonic()

    async with _public_investigation_lock:
        if now - _public_rate_limit_last_cleanup >= 60:
            for address, timestamps in list(_public_rate_limit_requests.items()):
                while timestamps and now - timestamps[0] >= 86_400:
                    timestamps.popleft()
                if not timestamps:
                    del _public_rate_limit_requests[address]
            _public_rate_limit_last_cleanup = now

        bucket_key = f"{request.url.path}:{client_ip}"
        event_times = _public_rate_limit_requests.setdefault(bucket_key, deque())
        window_requests = [stamp for stamp in event_times if now - stamp < window_seconds]
        if len(window_requests) >= per_window or len(event_times) >= per_day:
            retry_after = (
                event_times[0] + 86_400 - now
                if len(event_times) >= per_day
                else window_requests[0] + window_seconds - now
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Public request limit reached. Please try again later."},
                headers={"Retry-After": str(max(1, int(retry_after)))}
            )
        event_times.append(now)
        remaining = min(per_window - len(window_requests) - 1, per_day - len(event_times))

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    return response


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
_vector_store = None


def source_identity(record: dict) -> str:
    for key in ("source_id", "hash", "id", "file_path"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    canonical_record = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_record.encode("utf-8")).hexdigest()


class EvidenceIngestionRequest(BaseModel):
    source_type: Literal["alert", "deployment", "git_commit", "log", "runbook", "mixed"]
    records: list[dict] = Field(min_length=1, max_length=250)

    @model_validator(mode="after")
    def validate_records(self):
        required_fields_by_type = {
            "alert": ("message", "timestamp"),
            "deployment": ("version", "status", "timestamp"),
            "git_commit": ("hash", "message"),
            "log": ("message", "timestamp"),
            "runbook": ("file_path", "content"),
        }
        identities = set()
        total_size = 0

        for record in self.records:
            record_source_type = (
                record.get("source_type") if self.source_type == "mixed" else self.source_type
            )
            if record_source_type not in required_fields_by_type:
                raise ValueError("Each mixed evidence record requires a supported source_type.")
            required_fields = required_fields_by_type[record_source_type]
            for field in required_fields:
                value = record.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Each {self.source_type} record requires {field}.")
            if any(
                isinstance(value, str) and len(value) > 20_000
                for value in record.values()
            ):
                raise ValueError("Each record field must be 20,000 characters or fewer.")

            total_size += len(json.dumps(record, ensure_ascii=False))
            identity = (record_source_type, source_identity(record))
            if len(identity) > 256:
                raise ValueError("A source identity must be 256 characters or fewer.")
            if identity in identities:
                raise ValueError("Records in one request must have unique source identities.")
            identities.add(identity)
            timestamp = record.get("timestamp")
            if timestamp:
                try:
                    datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                except ValueError as error:
                    raise ValueError("Record timestamps must use ISO 8601 format.") from error

        if total_size > 1_000_000:
            raise ValueError("The total request data must be 1 MB or smaller.")
        return self


class InvestigationStatusUpdate(BaseModel):
    status: Literal["open", "investigating", "resolved"]


class InvestigationAssigneeUpdate(BaseModel):
    assigned_to: str | None = Field(default=None, max_length=254)

    @field_validator("assigned_to")
    @classmethod
    def normalize_assignee(cls, value: str | None) -> str | None:
        value = value.strip().lower() if value else None
        return value or None


class InvestigationCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5_000)

    @field_validator("body")
    @classmethod
    def strip_comment_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class NotificationReadUpdate(BaseModel):
    is_read: bool = True


class InvestigationFeedbackRequest(BaseModel):
    rating: Literal["helpful", "incorrect"]
    comment: str | None = Field(default=None, max_length=2_000)
    correction_target: str | None = Field(default=None, max_length=500)
    corrected_cause: str | None = Field(default=None, max_length=2_000)

    @field_validator("comment")
    @classmethod
    def clean_feedback_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("correction_target", "corrected_cause")
    @classmethod
    def clean_correction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_correction_pair(self):
        has_target = bool(self.correction_target)
        has_cause = bool(self.corrected_cause)
        if has_target != has_cause:
            raise ValueError("Provide both the finding or citation and its corrected cause.")
        if has_target and self.rating != "incorrect":
            raise ValueError("Corrections can only be submitted with an incorrect rating.")
        return self


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "analyst", "viewer"] = "viewer"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class UserUpdate(BaseModel):
    role: Literal["admin", "analyst", "viewer"] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.role is None and self.is_active is None:
            raise ValueError("Provide a role or active-state change.")
        return self


def add_collaboration_event(
    db: Session,
    investigation_id: int,
    event_type: str,
    details: str,
    actor: str | None = None,
    user_id: int | None = None,
    recipient_user_id: int | None = None,
) -> None:
    db.add(
        InvestigationActivity(
            investigation_id=investigation_id,
            event_type=event_type,
            actor=actor,
            user_id=user_id,
            details=details,
        )
    )
    db.add(
        Notification(
            investigation_id=investigation_id,
            recipient_user_id=recipient_user_id,
            message=details,
        )
    )


def user_id(user) -> int | None:
    return getattr(user, "id", None)


def user_email(user) -> str:
    return user.email


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


def get_vector_store():
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is required to index evidence.",
        )

    try:
        _vector_store = VectorStore()
        if _vector_store.is_empty():
            sample_documents = load_sample_documents()
            if sample_documents:
                _vector_store.add_documents(sample_documents)
        return _vector_store
    except Exception as error:
        _vector_store = None
        raise HTTPException(
            status_code=503,
            detail=f"Could not initialize the vector store: {error}",
        ) from error


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
        vector_store = get_vector_store()

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
        "session_secret": (
            "configured" if len(os.getenv("SESSION_SECRET", "")) >= 32 else "missing_or_too_short"
        ),
        "vector_store": vector_status,
    }
    ready = (
        database_status == "ok"
        and checks["openai_api_key"] == "configured"
        and (
            checks["session_secret"] == "configured"
            or (
                os.getenv("ALLOW_LEGACY_API_TOKEN", "false").lower() == "true"
                and checks["api_access_token"] == "configured"
            )
        )
        and vector_status == "initialized"
    )
    return {"status": "ready" if ready else "degraded", "ready": ready, "checks": checks}


@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {
        "access_token": create_session_token(user.id),
        "token_type": "bearer",
        "expires_in": 43200,
        "user": {"email": user.email, "role": user.role},
    }


@app.get("/auth/check")
def check_authentication(user=Depends(current_user)):
    return {"authenticated": True, "email": user.email, "role": user.role}


@app.get("/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    return [
        {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active}
        for user in db.query(User).order_by(User.email).all()
    ]


@app.post("/users", status_code=201, dependencies=[Depends(require_admin)])
def create_user(request: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=request.email, password_hash=hash_password(request.password), role=request.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active}


@app.patch("/users/{target_user_id}", dependencies=[Depends(require_admin)])
def update_user(
    target_user_id: int,
    update: UserUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_admin),
):
    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == user_id(actor):
        raise HTTPException(status_code=409, detail="Use another administrator account to change your own access.")
    would_remove_admin = target.role == "admin" and target.is_active and (
        update.role in {"analyst", "viewer"} or update.is_active is False
    )
    if would_remove_admin:
        other_admins = db.query(User).filter(
            User.role == "admin", User.is_active.is_(True), User.id != target.id
        ).count()
        if not other_admins:
            raise HTTPException(status_code=409, detail="Keep at least one active administrator account.")
    if update.role is not None:
        target.role = update.role
    if update.is_active is not None:
        target.is_active = update.is_active
    db.commit()
    return {"id": target.id, "email": target.email, "role": target.role, "is_active": target.is_active}


@app.post("/evidence", dependencies=[Depends(require_analyst_or_public)])
def ingest_evidence(request: EvidenceIngestionRequest):
    """Validate and index one or mixed-source evidence records."""
    try:
        records_by_type: dict[str, list[dict]] = {}
        for record in request.records:
            source_type = record.get("source_type") if request.source_type == "mixed" else request.source_type
            normalized = {key: value for key, value in record.items() if key != "source_type"}
            normalized["source_id"] = source_identity(normalized)
            records_by_type.setdefault(source_type, []).append(normalized)
        preprocessor = DataPreprocessor()
        documents = [
            document
            for source_type, records in records_by_type.items()
            for document in preprocessor.process(records, source_type)
        ]
        result = get_vector_store().upsert_documents(documents)
        return {
            "source_type": request.source_type,
            "record_count": len(documents),
            **result,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not ingest evidence: {error}",
        ) from error


@app.post("/investigate", dependencies=[Depends(require_analyst_or_public)])
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


@app.get("/investigations", dependencies=[Depends(current_user)])
def list_investigations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, min_length=1, max_length=200),
    service: str | None = Query(default=None, min_length=1, max_length=100),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    max_confidence: float | None = Query(default=None, ge=0, le=1),
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    status: Literal["open", "investigating", "resolved"] | None = None,
    assignee: str | None = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    """Search saved investigations by text, service, confidence, and date."""
    if min_confidence is not None and max_confidence is not None:
        if min_confidence > max_confidence:
            raise HTTPException(
                status_code=422,
                detail="min_confidence must be less than or equal to max_confidence.",
            )

    query = db.query(Investigation, Incident).join(
        Incident, Investigation.incident_id == Incident.id
    )
    if q:
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Incident.title.ilike(search_term),
                Incident.description.ilike(search_term),
                Investigation.question.ilike(search_term),
                Investigation.generated_answer.ilike(search_term),
            )
        )
    if service:
        query = query.filter(
            Investigation.report["filters"]["service"].as_string()
            == service.strip().lower()
        )
    if min_confidence is not None:
        query = query.filter(Investigation.confidence >= min_confidence)
    if max_confidence is not None:
        query = query.filter(Investigation.confidence <= max_confidence)
    if status:
        query = query.filter(Investigation.status == status)
    if assignee:
        query = query.filter(Investigation.assignee.ilike(assignee.strip()))
    if created_after:
        if created_after.tzinfo is None:
            created_after = created_after.replace(tzinfo=timezone.utc)
        query = query.filter(Investigation.created_at >= created_after)
    if created_before:
        if created_before.tzinfo is None:
            created_before = created_before.replace(tzinfo=timezone.utc)
        query = query.filter(Investigation.created_at <= created_before)

    records = query.order_by(
        Investigation.created_at.desc(), Investigation.id.desc()
    ).offset(offset).limit(limit).all()
    return [
        {
            "investigation_id": investigation.id,
            "incident_id": incident.id,
            "incident": incident.description,
            "question": investigation.question,
            "investigation_result": investigation.generated_answer,
            "confidence_score": investigation.confidence,
            "status": investigation.status,
            "assignee": investigation.assignee,
            "created_at": investigation.created_at.isoformat()
            if investigation.created_at
            else None,
        }
        for investigation, incident in records
    ]


@app.get(
    "/investigations/{investigation_id}",
    dependencies=[Depends(current_user)],
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
        "status": investigation.status,
        "assignee": investigation.assignee,
        "created_at": investigation.created_at.isoformat()
        if investigation.created_at
        else None,
        "report": investigation.report,
    }


@app.get("/investigations/{investigation_id}/feedback", dependencies=[Depends(current_user)])
def get_investigation_feedback(
    investigation_id: int,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    entries = db.query(InvestigationFeedback).filter(
        InvestigationFeedback.investigation_id == investigation_id
    ).all()
    mine = next((entry for entry in entries if entry.user_id == user_id(user)), None)
    return {
        "investigation_id": investigation_id,
        "helpful": sum(entry.rating == "helpful" for entry in entries),
        "incorrect": sum(entry.rating == "incorrect" for entry in entries),
        "my_feedback": {
            "rating": mine.rating,
            "comment": mine.comment,
            "correction_target": mine.correction_target,
            "corrected_cause": mine.corrected_cause,
        } if mine else None,
    }


@app.put("/investigations/{investigation_id}/feedback", dependencies=[Depends(require_analyst)])
def submit_investigation_feedback(
    investigation_id: int,
    update: InvestigationFeedbackRequest,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    if user_id(user) is None:
        raise HTTPException(status_code=401, detail="A signed-in account is required for feedback.")
    entry = db.query(InvestigationFeedback).filter_by(
        investigation_id=investigation_id, user_id=user_id(user)
    ).one_or_none()
    if entry is None:
        entry = InvestigationFeedback(
            investigation_id=investigation_id,
            user_id=user_id(user),
            rating=update.rating,
            comment=update.comment,
            correction_target=update.correction_target,
            corrected_cause=update.corrected_cause,
        )
        db.add(entry)
    else:
        entry.rating = update.rating
        entry.comment = update.comment
        entry.correction_target = update.correction_target
        entry.corrected_cause = update.corrected_cause
    db.commit()
    return {
        "investigation_id": investigation_id,
        "rating": entry.rating,
        "comment": entry.comment,
        "correction_target": entry.correction_target,
        "corrected_cause": entry.corrected_cause,
    }


@app.post("/evaluations/runs", status_code=202, dependencies=[Depends(require_analyst)])
def start_evaluation_run(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor=Depends(require_analyst),
):
    case_set = get_or_create_case_set(db, user_email(actor))
    run = EvaluationRun(
        dataset_version=case_set.version,
        initiated_by=user_email(actor),
        case_count=len(case_set.cases),
        passed_count=0,
        pass_rate=0,
        mean_confidence=0,
        validation_rate=0,
        citation_rate=0,
        results=[],
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(execute_run, run.id)
    return {"run_id": run.id, "dataset_version": run.dataset_version, "status": run.status}


@app.get("/evaluations/corrections", dependencies=[Depends(require_analyst)])
def list_reviewable_corrections(
    db: Session = Depends(get_db),
    actor=Depends(require_analyst),
):
    case_set = get_or_create_case_set(db, user_email(actor))
    approved_ids = {
        case.get("source_feedback_id")
        for case in case_set.cases
        if case.get("source_feedback_id") is not None
    }
    records = (
        db.query(InvestigationFeedback, Investigation, Incident)
        .join(Investigation, Investigation.id == InvestigationFeedback.investigation_id)
        .join(Incident, Incident.id == Investigation.incident_id)
        .filter(InvestigationFeedback.corrected_cause.isnot(None))
        .order_by(InvestigationFeedback.updated_at.desc())
        .all()
    )
    return [
        {
            "feedback_id": feedback.id,
            "investigation_id": investigation.id,
            "incident": incident.description,
            "question": investigation.question,
            "service": (investigation.report or {}).get("filters", {}).get("service"),
            "correction_target": feedback.correction_target,
            "corrected_cause": feedback.corrected_cause,
            "comment": feedback.comment,
            "approved": feedback.id in approved_ids,
        }
        for feedback, investigation, incident in records
    ]


@app.post("/evaluations/corrections/{feedback_id}/approve", status_code=201, dependencies=[Depends(require_analyst)])
def approve_evaluation_correction(
    feedback_id: int,
    db: Session = Depends(get_db),
    actor=Depends(require_analyst),
):
    feedback = db.get(InvestigationFeedback, feedback_id)
    if feedback is None or not feedback.corrected_cause or not feedback.correction_target:
        raise HTTPException(status_code=404, detail="A complete analyst correction was not found.")
    case_set = get_or_create_case_set(db, user_email(actor))
    if any(case.get("source_feedback_id") == feedback.id for case in case_set.cases):
        raise HTTPException(status_code=409, detail="This correction is already in the current evaluation set.")
    investigation = db.get(Investigation, feedback.investigation_id)
    incident = db.get(Incident, investigation.incident_id) if investigation else None
    if investigation is None or incident is None:
        raise HTTPException(status_code=404, detail="The corrected investigation was not found.")

    cases = list(case_set.cases)
    cases.append({
        "id": f"analyst-correction-{feedback.id}",
        "source_feedback_id": feedback.id,
        "incident": incident.description,
        "question": investigation.question,
        "service": (investigation.report or {}).get("filters", {}).get("service"),
        "correction_target": feedback.correction_target,
        "expected_terms": [feedback.corrected_cause],
        "minimum_citations": 1,
    })
    new_set = EvaluationCaseSet(
        version=case_set.version + 1,
        cases=cases,
        change_summary=f"Added correction from investigation #{investigation.id}",
        created_by=user_email(actor),
    )
    db.add(new_set)
    db.commit()
    db.refresh(new_set)
    return {
        "dataset_version": new_set.version,
        "case_count": len(new_set.cases),
        "change_summary": new_set.change_summary,
    }


@app.get("/evaluations/runs/{run_id}", dependencies=[Depends(current_user)])
def get_evaluation_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found.")
    return {
        "id": run.id,
        "dataset_version": run.dataset_version,
        "initiated_by": run.initiated_by,
        "case_count": run.case_count,
        "passed_count": run.passed_count,
        "pass_rate": run.pass_rate,
        "mean_confidence": run.mean_confidence,
        "validation_rate": run.validation_rate,
        "citation_rate": run.citation_rate,
        "status": run.status,
        "completed_cases": run.completed_cases,
        "current_case": run.current_case,
        "error": run.error,
        "results": run.results,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@app.get("/evaluations/case-sets/{version}", dependencies=[Depends(current_user)])
def get_evaluation_case_set(version: int, db: Session = Depends(get_db)):
    case_set = db.query(EvaluationCaseSet).filter_by(version=version).one_or_none()
    if case_set is None:
        raise HTTPException(status_code=404, detail="Evaluation case set not found.")
    return {
        "version": case_set.version,
        "change_summary": case_set.change_summary,
        "created_by": case_set.created_by,
        "created_at": case_set.created_at.isoformat() if case_set.created_at else None,
        "case_count": len(case_set.cases),
        "cases": case_set.cases,
    }


@app.get("/evaluations/runs", dependencies=[Depends(current_user)])
def list_evaluation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    runs = db.query(EvaluationRun).order_by(
        EvaluationRun.created_at.desc(), EvaluationRun.id.desc()
    ).limit(limit).all()
    return [
        {
            "id": run.id,
            "dataset_version": run.dataset_version,
            "initiated_by": run.initiated_by,
            "case_count": run.case_count,
            "passed_count": run.passed_count,
            "pass_rate": run.pass_rate,
            "mean_confidence": run.mean_confidence,
            "validation_rate": run.validation_rate,
            "citation_rate": run.citation_rate,
            "status": run.status,
            "completed_cases": run.completed_cases,
            "current_case": run.current_case,
            "error": run.error,
            "results": run.results,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
        for run in runs
    ]


@app.patch(
    "/investigations/{investigation_id}/status",
    dependencies=[Depends(require_analyst)],
)
def update_investigation_status(
    investigation_id: int,
    update: InvestigationStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor=Depends(require_analyst),
):
    """Change the workflow status of a saved investigation."""
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    previous_status = investigation.status
    if previous_status == update.status:
        return {"investigation_id": investigation.id, "status": investigation.status}
    investigation.status = update.status
    event = InvestigationStatusEvent(
        investigation_id=investigation.id,
        previous_status=previous_status,
        new_status=update.status,
        changed_by=user_email(actor),
    )
    db.add(event)
    add_collaboration_event(
        db,
        investigation.id,
        "status",
        f"Status changed from {previous_status} to {update.status}.",
        actor=user_email(actor),
        user_id=user_id(actor),
        recipient_user_id=investigation.assignee_user_id,
    )
    assigned_user = db.get(User, investigation.assignee_user_id) if investigation.assignee_user_id else None
    background_tasks.add_task(
        send_external_notification,
        f"Investigation #{investigation.id} status changed to {update.status}.",
        investigation.id,
        assigned_user.email if assigned_user else None,
    )
    db.commit()
    db.refresh(investigation)
    return {"investigation_id": investigation.id, "status": investigation.status}


@app.get(
    "/investigations/{investigation_id}/status-history",
    dependencies=[Depends(current_user)],
)
def get_investigation_status_history(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    """List recorded status changes, oldest first."""
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    events = (
        db.query(InvestigationStatusEvent)
        .filter(InvestigationStatusEvent.investigation_id == investigation_id)
        .order_by(InvestigationStatusEvent.changed_at, InvestigationStatusEvent.id)
        .all()
    )
    return [
        {
            "previous_status": event.previous_status,
            "new_status": event.new_status,
            "changed_by": event.changed_by,
            "changed_at": event.changed_at.isoformat() if event.changed_at else None,
        }
        for event in events
    ]


@app.patch(
    "/investigations/{investigation_id}/assignee",
    dependencies=[Depends(require_analyst)],
)
def update_investigation_assignee(
    investigation_id: int,
    update: InvestigationAssigneeUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor=Depends(require_analyst),
):
    """Assign or unassign a saved investigation."""
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    previous_assignee = investigation.assignee
    if previous_assignee == update.assigned_to:
        return {"investigation_id": investigation.id, "assigned_to": investigation.assignee}

    assignee_user = None
    if update.assigned_to:
        assignee_user = db.query(User).filter(
            User.email == update.assigned_to.strip().lower(), User.is_active.is_(True)
        ).first()
        if assignee_user is None:
            raise HTTPException(status_code=404, detail="Active teammate account not found.")

    investigation.assignee = update.assigned_to
    investigation.assignee_user_id = assignee_user.id if assignee_user else None
    if update.assigned_to:
        if previous_assignee:
            details = f"Reassigned from {previous_assignee} to {update.assigned_to}."
        else:
            details = f"Assigned to {update.assigned_to}."
    elif previous_assignee:
        details = f"Unassigned from {previous_assignee}."
    else:
        details = "Investigation assignment cleared."
    add_collaboration_event(
        db,
        investigation.id,
        "assignment",
        details,
        actor=user_email(actor),
        user_id=user_id(actor),
        recipient_user_id=assignee_user.id if assignee_user else None,
    )
    if assignee_user:
        background_tasks.add_task(
            send_external_notification,
            f"You were assigned investigation #{investigation.id}.",
            investigation.id,
            assignee_user.email,
        )
    db.commit()
    return {"investigation_id": investigation.id, "assigned_to": investigation.assignee}


@app.get(
    "/investigations/{investigation_id}/comments",
    dependencies=[Depends(current_user)],
)
def list_investigation_comments(investigation_id: int, db: Session = Depends(get_db)):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    comments = (
        db.query(InvestigationComment)
        .filter(InvestigationComment.investigation_id == investigation_id)
        .order_by(InvestigationComment.created_at, InvestigationComment.id)
        .all()
    )
    return [
        {
            "id": comment.id,
            "author": comment.author,
            "body": comment.body,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
        }
        for comment in comments
    ]


@app.post(
    "/investigations/{investigation_id}/comments",
    dependencies=[Depends(require_analyst)],
)
def create_investigation_comment(
    investigation_id: int,
    comment: InvestigationCommentCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_analyst),
):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    saved_comment = InvestigationComment(
        investigation_id=investigation_id,
        user_id=user_id(actor),
        author=user_email(actor),
        body=comment.body,
    )
    db.add(saved_comment)
    investigation = db.get(Investigation, investigation_id)
    add_collaboration_event(
        db,
        investigation_id,
        "comment",
        f"{user_email(actor)} added a comment.",
        actor=user_email(actor),
        user_id=user_id(actor),
        recipient_user_id=investigation.assignee_user_id,
    )
    db.commit()
    db.refresh(saved_comment)
    return {
        "id": saved_comment.id,
        "author": saved_comment.author,
        "body": saved_comment.body,
        "created_at": saved_comment.created_at.isoformat() if saved_comment.created_at else None,
    }


@app.get("/investigations/{investigation_id}/activity", dependencies=[Depends(current_user)])
def list_investigation_activity(investigation_id: int, db: Session = Depends(get_db)):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    events = (
        db.query(InvestigationActivity)
        .filter(InvestigationActivity.investigation_id == investigation_id)
        .order_by(InvestigationActivity.created_at, InvestigationActivity.id)
        .all()
    )
    return [
        {
            "event_type": event.event_type,
            "actor": event.actor,
            "details": event.details,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in events
    ]


@app.get("/notifications")
def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    visibility_filter = (
        Notification.recipient_user_id.is_(None)
        if user_id(user) is None
        else or_(Notification.recipient_user_id == user_id(user), Notification.recipient_user_id.is_(None))
    )
    unread_count = (
        db.query(Notification)
        .filter(visibility_filter, Notification.is_read.is_(False))
        .count()
    )
    notifications = (
        db.query(Notification)
        .filter(visibility_filter)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "unread_count": unread_count,
        "items": [
            {
                "id": item.id,
                "investigation_id": item.investigation_id,
                "message": item.message,
                "is_read": item.is_read,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in notifications
        ],
    }


@app.patch("/notifications/{notification_id}")
def update_notification(
    notification_id: int,
    update: NotificationReadUpdate,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if notification.recipient_user_id not in (None, user_id(user)) and user.role != "admin":
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification.is_read = update.is_read
    db.commit()
    return {"id": notification.id, "is_read": notification.is_read}


@app.get(
    "/investigations/{investigation_id}/export",
    dependencies=[Depends(current_user)],
)
def export_investigation(investigation_id: int, db: Session = Depends(get_db)):
    """Download a saved investigation as a Markdown report."""
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    incident = db.get(Incident, investigation.incident_id)
    report = investigation.report or {}
    title = incident.title if incident else f"Investigation #{investigation.id}"
    confidence = investigation.confidence or 0
    lines = [
        f"# {title}",
        "",
        f"- Investigation ID: {investigation.id}",
        f"- Incident ID: {investigation.incident_id}",
        f"- Created: {investigation.created_at.isoformat() if investigation.created_at else 'Unknown'}",
        f"- Confidence: {confidence:.0%}",
        "",
        "## Incident",
        "",
        incident.description if incident and incident.description else "No incident description.",
        "",
        "## Investigation question",
        "",
        investigation.question,
        "",
        "## Findings",
        "",
        investigation.generated_answer or "No findings were saved.",
        "",
        "## Validation",
        "",
    ]

    validation = report.get("validation") or {}
    lines.extend([
        f"- Evidence supported: {'Yes' if validation.get('is_valid') else 'Needs review'}",
        f"- Details: {validation.get('reason') or 'No validation details.'}",
        "",
        "## Evidence timeline",
        "",
    ])
    timeline = report.get("timeline") or []
    if timeline:
        for event in timeline:
            source = " · ".join(
                str(value) for value in (event.get("service"), event.get("source_type")) if value
            )
            suffix = f" ({source})" if source else ""
            lines.append(
                f"- {event.get('timestamp', 'Unknown time')}{suffix}: "
                f"{event.get('summary', 'No summary')} [E{event.get('evidence_id', '?')}]"
            )
    else:
        lines.append("No timestamped evidence was retrieved.")

    lines.extend(["", "## Citations", ""])
    citations = report.get("citations") or []
    if citations:
        for citation in citations:
            citation_id = citation.get("citation_id") or f"E{citation.get('evidence_id', '?')}"
            source = " · ".join(
                str(value)
                for value in (
                    citation.get("source_type"),
                    citation.get("service"),
                    citation.get("source_id") or citation.get("source_path"),
                )
                if value
            )
            lines.append(f"- **[{citation_id}]** {source or 'Source details unavailable'}")
            if citation.get("timestamp"):
                lines.append(f"  - Timestamp: {citation['timestamp']}")
            if citation.get("excerpt"):
                lines.append(f"  - Excerpt: {citation['excerpt']}")
    else:
        lines.append("No evidence citations were returned.")

    filename = f"investigation-{investigation.id}.md"
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app.mount(
    "/ui",
    StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True),
    name="ui",
)
