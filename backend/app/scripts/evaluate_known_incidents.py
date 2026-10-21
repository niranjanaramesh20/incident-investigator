"""Run the small, versioned known-incident quality set against the live pipeline."""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.main import get_investigation_service
from app.db.database import SessionLocal
from app.models.evaluation_run import EvaluationRun
from app.models.investigation_feedback import InvestigationFeedback
from app.models.investigation import Investigation
from app.models.incident import Incident


DATASET = Path(__file__).resolve().parents[1] / "evaluations" / "known_incidents.json"


def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = list(dataset["cases"])
    # Analyst corrections become regression cases on subsequent runs.
    with SessionLocal() as db:
        corrections = (
            db.query(InvestigationFeedback, Investigation, Incident)
            .join(Investigation, Investigation.id == InvestigationFeedback.investigation_id)
            .join(Incident, Incident.id == Investigation.incident_id)
            .filter(InvestigationFeedback.corrected_cause.isnot(None))
            .order_by(InvestigationFeedback.id)
            .all()
        )
        for feedback, investigation, incident in corrections:
            cases.append({
                "id": f"analyst-correction-{feedback.id}",
                "incident": incident.description,
                "question": investigation.question,
                "service": (investigation.report or {}).get("filters", {}).get("service"),
                "expected_terms": [feedback.corrected_cause],
                "minimum_citations": 1,
            })
    service = get_investigation_service()
    results = []
    for case in cases:
        filters = {"service": case["service"]} if case.get("service") else None
        report = service.investigate(
            case["incident"],
            case["question"],
            filters=filters,
        )
        answer = report.get("investigation_result", "").lower()
        terms_found = [term for term in case["expected_terms"] if term.lower() in answer]
        citations = report.get("citations", [])
        passed = (
            bool(terms_found)
            and len(citations) >= case["minimum_citations"]
            and not report.get("citation_warnings")
        )
        results.append({
            "id": case["id"],
            "passed": passed,
            "expected_terms_found": terms_found,
            "expected_terms": case["expected_terms"],
            "citation_count": len(citations),
            "citation_warnings": report.get("citation_warnings", []),
            "confidence": report.get("confidence_score"),
            "validation_passed": report.get("validation", {}).get("is_valid", False),
        })

    passed_count = sum(item["passed"] for item in results)
    citation_count = sum(
        item["citation_count"] > 0 and not item["citation_warnings"] for item in results
    )
    output = {
        "dataset_version": dataset["version"],
        "run_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "cases": len(results),
            "passed": passed_count,
            "pass_rate": round(passed_count / len(results), 3) if results else 0,
            "mean_confidence": round(sum(item["confidence"] or 0 for item in results) / len(results), 3) if results else 0,
            "validation_rate": round(sum(item["validation_passed"] for item in results) / len(results), 3) if results else 0,
            "citation_rate": round(citation_count / len(results), 3) if results else 0,
        },
        "results": results,
    }
    with SessionLocal() as db:
        saved_run = EvaluationRun(
            dataset_version=dataset["version"],
            initiated_by="command line",
            case_count=len(results),
            passed_count=passed_count,
            pass_rate=output["summary"]["pass_rate"],
            mean_confidence=output["summary"]["mean_confidence"],
            validation_rate=output["summary"]["validation_rate"],
            citation_rate=output["summary"]["citation_rate"],
            results=results,
        )
        db.add(saved_run)
        db.commit()
        db.refresh(saved_run)
        output["run_id"] = saved_run.id
    print(json.dumps(output, indent=2))
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
