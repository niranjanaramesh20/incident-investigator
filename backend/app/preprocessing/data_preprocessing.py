from langchain_core.documents import Document


class DataPreprocessor:

    def process(self, records: list, source_type: str):
        documents = []

        for record in records:
            content = self._create_content(record, source_type)

            document = Document(
                page_content=content,
                metadata={
                    "source_type": source_type
                }
            )

            documents.append(document)

        return documents

    def _create_content(self, record: dict, source_type: str):
        if source_type == "git_commit":
            return (
                f"Commit: {record.get('hash')}\n"
                f"Author: {record.get('author')}\n"
                f"Branch: {record.get('branch')}\n"
                f"Message: {record.get('message')}\n"
                f"Timestamp: {record.get('timestamp')}"
            )

        if source_type == "log":
            return (
                f"Timestamp: {record.get('timestamp')}\n"
                f"Level: {record.get('level')}\n"
                f"Host: {record.get('host')}\n"
                f"Trace ID: {record.get('trace_id')}\n"
                f"Message: {record.get('message')}"
            )

        if source_type == "deployment":
            return (
                f"Service ID: {record.get('service_id')}\n"
                f"Version: {record.get('version')}\n"
                f"Environment: {record.get('environment')}\n"
                f"Deployed By: {record.get('deployed_by')}\n"
                f"Timestamp: {record.get('timestamp')}\n"
                f"Status: {record.get('status')}"
            )

        if source_type == "alert":
            return (
                f"Service ID: {record.get('service_id')}\n"
                f"Severity: {record.get('severity')}\n"
                f"Metric: {record.get('metric')}\n"
                f"Message: {record.get('message')}\n"
                f"Timestamp: {record.get('timestamp')}"
            )

        if source_type == "runbook":
            return record.get("content", "")

        raise ValueError(f"Unsupported source type: {source_type}")