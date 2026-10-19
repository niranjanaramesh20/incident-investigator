from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


class InvestigationEngine:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

    def investigate(self, incident: str, query: str, evidence: list) -> str:
        evidence_text = "\n\n".join(
            f"[Evidence {index + 1}]\n{document.page_content}"
            for index, document in enumerate(evidence)
        )
        prompt = ChatPromptTemplate.from_template(
            """You are an AI incident investigation assistant.

Analyze the incident using only the provided evidence.

Incident:
{incident}

Investigation question:
{query}

Evidence:
{evidence}

Identify the most likely root cause and explain your reasoning. Attach one or
more exact citations in the form [Evidence N] to every factual claim about the
incident. Only cite IDs shown in the evidence section. Do not invent information.
If evidence is insufficient, say so clearly."""
        )
        response = (prompt | self.llm).invoke(
            {"incident": incident, "query": query, "evidence": evidence_text}
        )
        return response.content
