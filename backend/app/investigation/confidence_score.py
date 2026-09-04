class ConfidenceScorer:

    def calculate(
            self,
            validation_result: dict,
            evidence_count: int
    ) -> float:

        if evidence_count == 0:
            return 0.0

        if not validation_result.get("is_valid", False):
            return 0.3 

        supporting_evidence = validation_result.get(
            "supporting_evidence", []
        )

        supporting_count = len(supporting_evidence)

        support_ratio = supporting_count / evidence_count

        confidence = 0.6 + (0.4 * support_ratio)

        return round(min(confidence, 1.0), 2)