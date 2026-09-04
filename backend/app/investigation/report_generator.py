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

        for i, document in enumerate(evidence):
            evidence_list.append({
                "evidence_id": i + 1,
                "content": document.page_content,
                "metadata": document.metadata
            })

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

            "evidence": evidence_list
        }

        return report
