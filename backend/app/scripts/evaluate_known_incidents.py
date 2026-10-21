"""Run and persist the current reviewed evaluation case set."""
import json

from app.db.database import SessionLocal
from app.evaluations.runner import execute_run, get_or_create_case_set
from app.models.evaluation_run import EvaluationRun


def main() -> int:
    with SessionLocal() as db:
        case_set = get_or_create_case_set(db, "command line")
        run = EvaluationRun(
            dataset_version=case_set.version,
            initiated_by="command line",
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
        run_id = run.id

    execute_run(run_id)
    with SessionLocal() as db:
        run = db.get(EvaluationRun, run_id)
        print(json.dumps({
            "run_id": run.id,
            "dataset_version": run.dataset_version,
            "status": run.status,
            "summary": {
                "cases": run.case_count,
                "passed": run.passed_count,
                "pass_rate": round(run.pass_rate, 3),
                "mean_confidence": round(run.mean_confidence, 3),
                "validation_rate": round(run.validation_rate, 3),
                "citation_rate": round(run.citation_rate, 3),
            },
            "results": run.results,
            "error": run.error,
        }, indent=2))
        return 0 if run.status == "completed" and run.passed_count == run.case_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
