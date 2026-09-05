from ..rag.query_processor import QueryProcessor
from ..rag.retriever import Retriever
from ..rag.reranker import Reranker
from investigation_engine import InvestigationEngine
from evidence_validator import EvidenceValidator
from confidence_scorer import ConfidenceScorer
from report_generator import ReportGenerator


class InvestigationService:

    def __init__(
        self,
        query_processor: QueryProcessor,
        retriever: Retriever,
        reranker: Reranker,
        investigation_engine: InvestigationEngine,
        evidence_validator: EvidenceValidator,
        confidence_scorer: ConfidenceScorer,
        report_generator: ReportGenerator
    ):
        self.query_processor = query_processor
        self.retriever = retriever
        self.reranker = reranker
        self.investigation_engine = investigation_engine
        self.evidence_validator = evidence_validator
        self.confidence_scorer = confidence_scorer
        self.report_generator = report_generator

    def investigate(self, incident: str, question: str):

        processed_question = self.query_processor.process(question)

        evidence = self.retriever.retrieve(processed_question)

        ranked_evidence = self.reranker.rerank(
            processed_question,
            evidence
        )

        investigation_result = self.investigation_engine.investigate(
            incident,
            processed_question,
            ranked_evidence
        )

        validation_result = self.evidence_validator.validate(
            investigation_result,
            ranked_evidence
        )

        confidence_score = self.confidence_scorer.calculate(
            validation_result,
            len(ranked_evidence)
        )

        report = self.report_generator.generate(
            incident,
            investigation_result,
            validation_result,
            confidence_score,
            ranked_evidence
        )

        return report