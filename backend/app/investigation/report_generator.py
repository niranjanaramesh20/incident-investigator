from datetime import datetime, timezone
import re


class ReportGenerator:

    def generate(
        self,
        incident: str,
        investigation_result: str,
        validation_result: dict,
        confidence_score: float,
        evidence: list
    ) -> dict:

        evidence_list = []
        evidence_by_id = {}
        timeline = []

        for i, document in enumerate(evidence):
            evidence_id = i + 1
            metadata = document.metadata or {}
            evidence_item = {
                "evidence_id": evidence_id,
                "content": document.page_content,
                "metadata": metadata,
            }
            evidence_list.append(evidence_item)
            evidence_by_id[evidence_id] = evidence_item
            timestamp = metadata.get("timestamp")
            if timestamp:
                try:
                    parsed_timestamp = datetime.fromisoformat(
                        str(timestamp).replace("Z", "+00:00")
                    )
                except ValueError:
                    parsed_timestamp = None
                if parsed_timestamp is not None:
                    if parsed_timestamp.tzinfo is None:
                        parsed_timestamp = parsed_timestamp.replace(tzinfo=timezone.utc)
                    parsed_timestamp = parsed_timestamp.astimezone(timezone.utc)
                    summary = " ".join(document.page_content.split())
                    if len(summary) > 240:
                        summary = summary[:237].rstrip() + "..."
                    timeline.append(
                        (
                            parsed_timestamp,
                            {
                                "evidence_id": evidence_id,
                                "timestamp": parsed_timestamp.isoformat(),
                                "source_type": metadata.get("source_type"),
                                "source_id": metadata.get("source_id"),
                                "service": metadata.get("service"),
                                "summary": summary,
                            },
                        )
                    )
        timeline.sort(key=lambda entry: (entry[0], entry[1]["evidence_id"]))

        cited_ids = list(
            dict.fromkeys(
                int(match)
                for match in re.findall(
                    r"\[Evidence\s+(\d+)\]",
                    investigation_result,
                    flags=re.IGNORECASE,
                )
            )
        )
        supporting_ids = validation_result.get("supporting_evidence", [])
        valid_supporting_ids = list(dict.fromkeys(
            item for item in supporting_ids
            if isinstance(item, int) and not isinstance(item, bool)
        ))
        citation_ids = list(dict.fromkeys(cited_ids + list(valid_supporting_ids)))
        citations = []
        for evidence_id in citation_ids:
            evidence_item = evidence_by_id.get(evidence_id)
            if evidence_item is None:
                continue
            metadata = evidence_item["metadata"]
            citations.append(
                {
                    "citation_id": f"E{evidence_id}",
                    "evidence_id": evidence_id,
                    "source_type": metadata.get("source_type"),
                    "source_id": metadata.get("source_id"),
                    "source_path": metadata.get("source_path"),
                    "service": metadata.get("service"),
                    "timestamp": metadata.get("timestamp"),
                    "excerpt": evidence_item["content"],
                    "cited_in_answer": evidence_id in cited_ids,
                    "validated_as_supporting": evidence_id in valid_supporting_ids,
                }
            )

        citation_warnings = []
        unresolved_ids = [item for item in cited_ids if item not in evidence_by_id]
        if unresolved_ids:
            citation_warnings.append(
                "The answer references evidence IDs that were not returned: "
                + ", ".join(f"E{item}" for item in unresolved_ids)
                + "."
            )
        if not cited_ids and investigation_result.strip():
            citation_warnings.append("The answer contains no evidence citations.")
        unsupported_ids = [
            item for item in cited_ids
            if item in evidence_by_id and item not in valid_supporting_ids
        ]
        if unsupported_ids:
            citation_warnings.append(
                "These cited evidence items were not confirmed as supporting: "
                + ", ".join(f"E{item}" for item in unsupported_ids)
                + "."
            )

        report = {
            "incident": incident,

            "investigation_result": investigation_result,

            "validation": {
                "is_valid": validation_result.get(
                    "is_valid",
                    False
                ),
                "reason": validation_result.get(
                    "reason",
                    ""
                ),
                "supporting_evidence": validation_result.get(
                    "supporting_evidence",
                    []
                )
            },

            "confidence_score": confidence_score,

            "evidence": evidence_list,
            "timeline": [event for _, event in timeline],
            "citations": citations,
            "citation_warnings": citation_warnings,
        }

        return report
