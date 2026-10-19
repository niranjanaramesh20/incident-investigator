from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json


def parse_validation_response(content: str) -> dict:
    """Parse and validate the model's JSON response, failing closed."""
    fallback = {
        "is_valid": False,
        "reason": "Unable to parse validation result.",
        "supporting_evidence": [],
    }
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return fallback

    if (
        not isinstance(result, dict)
        or not isinstance(result.get("is_valid"), bool)
        or not isinstance(result.get("reason"), str)
        or not isinstance(result.get("supporting_evidence"), list)
        or any(not isinstance(item, int) or isinstance(item, bool)
               for item in result["supporting_evidence"])
    ):
        return fallback
    return result


class EvidenceValidator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
        )

    def validate(
            self,
            investigation_result: str,
            evidence: list
    ) -> dict:

        if not evidence:
            return {
                "is_valid": False,
                "reason": "No evidence was provided.",
                "supporting_evidence": []
            }

        evidence_text = "\n\n".join(
            [
                f"[Evidence {i + 1}]\n{doc.page_content}"
                for i, doc in enumerate(evidence)
            ]
        )

        prompt = ChatPromptTemplate.from_template(             
            """
You are an evidence validation system.

Check whether the investigation result is supported by
the provided evidence.

Investigation Result:
{investigation_result}

Evidence:
{evidence}

Rules:
1. Only use the provided evidence.
2. Do not assume missing information.
3. Mark the result as valid only if the main conclusion is supported.
4. supporting_evidence must contain only the numeric IDs of evidence items
   that directly support the conclusion.

Return ONLY valid JSON in this format:

{{
    "is_valid": true,
    "reason": "Explanation of validation result",
    "supporting_evidence": [1, 2]
}}
"""
        )

        chain = prompt | self.llm

        response = chain.invoke({
            "investigation_result": investigation_result,
            "evidence": evidence_text
        })

        result = parse_validation_response(response.content)
        supporting_ids = result["supporting_evidence"]
        invalid_ids = [item for item in supporting_ids if item < 1 or item > len(evidence)]
        result["supporting_evidence"] = list(dict.fromkeys(
            item for item in supporting_ids if 1 <= item <= len(evidence)
        ))
        if invalid_ids:
            result["is_valid"] = False
            result["reason"] = (
                "The validator returned evidence IDs outside the provided evidence range."
            )
        elif result["is_valid"] and not result["supporting_evidence"]:
            result["is_valid"] = False
            result["reason"] = "No supporting evidence IDs were returned."
        return result

