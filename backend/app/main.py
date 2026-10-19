import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.ingestion.sample_data import load_sample_documents
from app.investigation.confidence_scorer import ConfidenceScorer
from app.investigation.evidence_validator import EvidenceValidator
from app.investigation.investigation_engine import InvestigationEngine
from app.investigation.report_generator import ReportGenerator
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


class InvestigationRequest(BaseModel):
    incident: str = Field(min_length=1, max_length=10_000)
    question: str = Field(min_length=1, max_length=2_000)

    @field_validator("incident", "question")
    @classmethod
    def strip_and_validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


_investigation_service = None


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


@app.post("/investigate")
def investigate(request: InvestigationRequest):
    """Return a root-cause report for an incident and investigation question."""
    try:
        service = get_investigation_service()
        return service.investigate(request.incident.strip(), request.question.strip())
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"The investigation could not be completed: {error}",
        ) from error
