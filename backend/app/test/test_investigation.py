from ..rag.query_processor import QueryProcessor
from ..rag.vector_store import VectorStore
from ..rag.retriever import Retriever
from ..rag.reranker import Reranker

from ..investigation.investigation_engine import InvestigationEngine
from ..investigation.evidence_validator import EvidenceValidator
from ..investigation.confidence_scorer import ConfidenceScorer
from ..investigation.report_generator import ReportGenerator

from ..services.investigation_service import InvestigationService


query_processor = QueryProcessor()

vector_store = VectorStore()
retriever = Retriever(vector_store)

reranker = Reranker()

investigation_engine = InvestigationEngine()
evidence_validator = EvidenceValidator()
confidence_scorer = ConfidenceScorer()
report_generator = ReportGenerator()


investigation_service = InvestigationService(
    query_processor=query_processor,
    retriever=retriever,
    reranker=reranker,
    investigation_engine=investigation_engine,
    evidence_validator=evidence_validator,
    confidence_scorer=confidence_scorer,
    report_generator=report_generator
)


incident = """
Payment service experienced a sudden increase in failed transactions.
The incident started shortly after a deployment.
"""

question = """
Why did the payment service experience increased transaction failures?
"""


report = investigation_service.investigate(
    incident,
    question
)

print(report)