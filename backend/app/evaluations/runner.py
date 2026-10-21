"""Shared evaluator used by the API background task and the CLI command."""
import json
from pathlib import Path

from sqlalchemy import func

from app.db.database import SessionLocal
from app.models.evaluation_case_set import EvaluationCaseSet
from app.models.evaluation_run import EvaluationRun


DATASET_PATH = Path(__file__).with_name("known_incidents.json")


def get_or_create_case_set(db, created_by: str) -> EvaluationCaseSet:
    case_set = db.query(EvaluationCaseSet).order_by(EvaluationCaseSet.version.desc()).first()
    if case_set:
        return case_set
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    previous_version = db.query(func.max(EvaluationRun.dataset_version)).scalar() or 0
    case_set = EvaluationCaseSet(
        version=max(dataset["version"], previous_version + 1),
        cases=dataset["cases"],
        change_summary="Initial known incident evaluation cases",
        created_by=created_by,
    )
    db.add(case_set)
    db.commit()
    db.refresh(case_set)
    return case_set


def execute_run(run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(EvaluationRun, run_id)
        if run is None:
            return
        run.status = "running"
        db.commit()
        try:
            case_set = db.query(EvaluationCaseSet).filter_by(version=run.dataset_version).one()
            cases = case_set.cases
            run.case_count = len(cases)
            run.current_case = None
            db.commit()

            from app.main import get_investigation_service

            service = get_investigation_service()
            results = []
            for index, case in enumerate(cases):
                run.current_case = case["id"]
                db.commit()
                filters = {"service": case["service"]} if case.get("service") else None
                report = service.investigate(case["incident"], case["question"], filters=filters)
                answer = report.get("investigation_result", "").lower()
                terms_found = [term for term in case["expected_terms"] if term.lower() in answer]
                citations = report.get("citations", [])
                warnings = report.get("citation_warnings", [])
                results.append({
                    "id": case["id"],
                    "passed": bool(terms_found)
                    and len(citations) >= case.get("minimum_citations", 1)
                    and not warnings,
                    "expected_terms_found": terms_found,
                    "expected_terms": case["expected_terms"],
                    "citation_count": len(citations),
                    "citation_warnings": warnings,
                    "confidence": report.get("confidence_score"),
                    "validation_passed": report.get("validation", {}).get("is_valid", False),
                })
                run.completed_cases = index + 1
                run.results = list(results)
                db.commit()

            count = len(results)
            passed = sum(item["passed"] for item in results)
            citation_passed = sum(item["citation_count"] > 0 and not item["citation_warnings"] for item in results)
            run.passed_count = passed
            run.pass_rate = passed / count if count else 0
            run.mean_confidence = sum(item["confidence"] or 0 for item in results) / count if count else 0
            run.validation_rate = sum(item["validation_passed"] for item in results) / count if count else 0
            run.citation_rate = citation_passed / count if count else 0
            run.status = "completed"
            run.current_case = None
            run.error = None
            db.commit()
        except Exception as error:
            db.rollback()
            run = db.get(EvaluationRun, run_id)
            if run:
                run.status = "failed"
                run.error = str(error)[:2_000]
                run.current_case = None
                db.commit()
