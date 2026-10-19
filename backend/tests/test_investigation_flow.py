from types import SimpleNamespace
from unittest.mock import Mock

from app.investigation.confidence_scorer import ConfidenceScorer
from app.investigation.evidence_validator import (
    EvidenceValidator,
    parse_validation_response,
)
from app.investigation.report_generator import ReportGenerator
from app.services.investigation_service import InvestigationService


def build_service(evidence, validation_result):
    query_processor = Mock()
    query_processor.process.return_value = "processed question"

    retriever = Mock()
    retriever.retrieve.return_value = evidence

    reranker = Mock()
    reranker.rerank.return_value = evidence

    investigation_engine = Mock()
    investigation_engine.investigate.return_value = "Likely cause: database timeouts [Evidence 1]."

    evidence_validator = Mock()
    evidence_validator.validate.return_value = validation_result

    service = InvestigationService(
        query_processor=query_processor,
        retriever=retriever,
        reranker=reranker,
        investigation_engine=investigation_engine,
        evidence_validator=evidence_validator,
        confidence_scorer=ConfidenceScorer(),
        report_generator=ReportGenerator(),
    )
    return service, query_processor, retriever, reranker, investigation_engine


def test_investigation_flow_returns_report_with_sources():
    evidence = [
        SimpleNamespace(
            page_content="Database connection timeout in payment-service.",
            metadata={"source_type": "log", "source_id": "trace-42"},
        )
    ]
    service, processor, retriever, reranker, engine = build_service(
        evidence,
        {
            "is_valid": True,
            "reason": "The log supports the proposed cause.",
            "supporting_evidence": [1],
        },
    )

    report = service.investigate("Payment errors", "Why did payments fail?")

    assert report["investigation_result"].endswith("[Evidence 1].")
    assert report["confidence_score"] == 1.0
    assert report["evidence"][0]["metadata"]["source_id"] == "trace-42"
    assert report["citations"][0]["citation_id"] == "E1"
    assert report["citations"][0]["source_id"] == "trace-42"
    assert report["citations"][0]["excerpt"] == evidence[0].page_content
    assert report["citations"][0]["validated_as_supporting"] is True
    processor.process.assert_called_once_with("Why did payments fail?")
    retriever.retrieve.assert_called_once_with("processed question")
    reranker.rerank.assert_called_once_with("processed question", evidence)
    engine.investigate.assert_called_once_with(
        "Payment errors", "processed question", evidence
    )


def test_conflicting_evidence_produces_low_confidence_report():
    evidence = [
        SimpleNamespace(
            page_content="Deployment succeeded at 10:00.",
            metadata={"source_type": "deployment", "source_id": "deploy-1"},
        ),
        SimpleNamespace(
            page_content="No deployment was recorded for this service.",
            metadata={"source_type": "log", "source_id": "log-2"},
        ),
    ]
    service, *_ = build_service(
        evidence,
        {
            "is_valid": False,
            "reason": "The evidence conflicts about whether a deployment occurred.",
            "supporting_evidence": [],
        },
    )

    report = service.investigate("Payment errors", "Was a deployment involved?")

    assert report["validation"]["is_valid"] is False
    assert "conflicts" in report["validation"]["reason"]
    assert report["confidence_score"] == 0.3


def test_validator_returns_clear_failure_when_evidence_is_empty():
    validator = EvidenceValidator.__new__(EvidenceValidator)

    result = validator.validate("A proposed conclusion", [])

    assert result == {
        "is_valid": False,
        "reason": "No evidence was provided.",
        "supporting_evidence": [],
    }


def test_malformed_model_response_fails_closed():
    result = parse_validation_response("not valid JSON")

    assert result["is_valid"] is False
    assert result["supporting_evidence"] == []
    assert result["reason"] == "Unable to parse validation result."


def test_model_response_with_wrong_shape_fails_closed():
    result = parse_validation_response('{"is_valid": "yes", "supporting_evidence": []}')

    assert result["is_valid"] is False
    assert result["supporting_evidence"] == []


def test_report_warns_when_answer_cites_missing_evidence():
    evidence = [
        SimpleNamespace(
            page_content="Database connection timeout.",
            metadata={"source_type": "log", "source_id": "trace-42"},
        )
    ]

    report = ReportGenerator().generate(
        "Payment errors",
        "The cause was a timeout [Evidence 4].",
        {"is_valid": False, "reason": "No support.", "supporting_evidence": []},
        0.3,
        evidence,
    )

    assert report["citations"] == []
    assert "E4" in report["citation_warnings"][0]


def test_report_timeline_sorts_timestamped_evidence():
    evidence = [
        SimpleNamespace(
            page_content="Deployment completed.",
            metadata={"source_type": "deployment", "timestamp": "2026-07-25T10:15:00"},
        ),
        SimpleNamespace(
            page_content="Error rate increased.",
            metadata={"source_type": "alert", "timestamp": "2026-07-25T10:00:00"},
        ),
        SimpleNamespace(
            page_content="Runbook suggests checking database health.",
            metadata={"source_type": "runbook"},
        ),
    ]

    report = ReportGenerator().generate(
        "Payment errors",
        "The alert followed deployment [Evidence 1].",
        {"is_valid": True, "reason": "Supported.", "supporting_evidence": [1, 2]},
        1.0,
        evidence,
    )

    assert [event["evidence_id"] for event in report["timeline"]] == [2, 1]
