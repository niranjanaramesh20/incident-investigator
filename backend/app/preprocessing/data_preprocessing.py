from langchain_core.documents import Document


class DataPreprocessor:

    def process(self, records: list, source_type: str):
        documents = []

        for record in records:
            content = self._create_content(record, source_type)
            metadata = {
                "source_type": source_type,
                "source_id": str(
                    record.get("source_id")
                    or record.get("hash")
                    or record.get("id")
                    or record.get("timestamp")
                    or record.get("file_path")
                    or len(documents) + 1
                ),
            }
            service = (
                record.get("service")
                or record.get("service_name")
                or record.get("service_id")
            )
            if service:
                metadata["service"] = str(service).strip().lower()
            if record.get("service_id") is not None:
                metadata["service_id"] = str(record["service_id"])
            if record.get("timestamp"):
                metadata["timestamp"] = str(record["timestamp"])
            if record.get("environment"):
                metadata["environment"] = str(record["environment"])
            if record.get("level"):
                metadata["level"] = str(record["level"])
            if source_type == "runbook":
                metadata["service"] = str(record.get("service") or "unknown").strip().lower()
                if record.get("file_path"):
                    metadata["source_path"] = str(record["file_path"])

            document = Document(
                page_content=content,
                metadata=metadata,
            )

            documents.append(document)

        return documents

    def _create_content(self, record: dict, source_type: str):
        if source_type == "git_commit":
            return (
                f"Service: {record.get('service') or record.get('service_id')}\n"
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
                f"Service: {record.get('service') or record.get('service_id')}\n"
                f"Version: {record.get('version')}\n"
                f"Environment: {record.get('environment')}\n"
                f"Deployed By: {record.get('deployed_by')}\n"
                f"Timestamp: {record.get('timestamp')}\n"
                f"Status: {record.get('status')}"
            )

        if source_type == "alert":
            return (
                f"Service: {record.get('service') or record.get('service_id')}\n"
                f"Severity: {record.get('severity')}\n"
                f"Metric: {record.get('metric')}\n"
                f"Message: {record.get('message')}\n"
                f"Timestamp: {record.get('timestamp')}"
            )

        if source_type == "runbook":
            return record.get("content", "")

        raise ValueError(f"Unsupported source type: {source_type}")
