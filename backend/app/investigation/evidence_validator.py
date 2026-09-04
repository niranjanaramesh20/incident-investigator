from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

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
                "supporting_evidnce": []
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
3. Mark the result as valid only if the main conclusion
   is supported by the evidence.

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

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "is_valid": False,
                "reason": "Unable to parse validation result.",
                "supporting_evidence": []
            }
        