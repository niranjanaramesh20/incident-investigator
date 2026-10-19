import json
from pathlib import Path

from app.preprocessing.data_preprocessing import DataPreprocessor


SAMPLE_DATA_DIR = Path(__file__).resolve().parents[1] / "sample_data"


def load_sample_documents():
    """Load the bundled JSON and runbook files as searchable documents."""
    preprocessor = DataPreprocessor()
    documents = []

    sources = (
        ("alerts/alerts.json", "alert"),
        ("deployments/deployments.json", "deployment"),
        ("commits/commits.json", "git_commit"),
        ("logs/logs.json", "log"),
    )
    for relative_path, source_type in sources:
        with (SAMPLE_DATA_DIR / relative_path).open(encoding="utf-8") as data_file:
            records = json.load(data_file)
        documents.extend(preprocessor.process(records, source_type))

    for runbook_path in sorted((SAMPLE_DATA_DIR / "runbooks").glob("*.md")):
        documents.extend(
            preprocessor.process(
                [
                    {
                        "file_path": str(runbook_path.relative_to(SAMPLE_DATA_DIR)),
                        "content": runbook_path.read_text(encoding="utf-8"),
                    }
                ],
                "runbook",
            )
        )
    return documents
