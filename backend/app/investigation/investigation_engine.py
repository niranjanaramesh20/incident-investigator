from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

class InvestigationEngine:

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
        )

    def investigate(
            self,
            incident: str,
            query: str,
            evidence: list
    ) -> str:

    evidence_text = "\n\n".join(
        [
            f"[Evidence{i + 1}]\n{doc.page_content}"
            for i, doc in enumerate(evidence)
        ]
    )

    prompt = ChatPromptTemplate.from_template(
        """
        You are an AI incident investigation assistant.

Analyze the incident using ONLY the provided evidence.

Incident:
{incident}

Investigation Question:
{query}

Evidence:
{evidence}

Instructions:
1. Identify the most likely root cause.
2. Explain the reasoning.
3. Reference the relevant evidence.
4. Do not invent information.
5. If the evidence is insufficient, clearly say so.
"""
     
    )
    chain = prompt | self.llm

    response = chain.invoke({
        "incident": incident,
        "query": query,
        "evidence": evidence_text
    })

    return response.content
