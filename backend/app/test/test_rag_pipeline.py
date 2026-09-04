from langchain_core.documents import Document

from rag.vector_store import VectorStore
from rag.retriever import Retriever
from rag.reranker import Reranker
from rag.query_processor import QueryProcessor


# 1. Sample incident data
documents = [
    Document(
        page_content="Database connection timeout occurred in payment service.",
        metadata={"source_type": "log"}
    ),
    Document(
        page_content="Payment service version 2.1 was deployed at 10:25.",
        metadata={"source_type": "deployment"}
    ),
    Document(
        page_content="High error rate alert triggered for payment service.",
        metadata={"source_type": "alert"}
    ),
]


# 2. Store documents
vector_store = VectorStore()
vector_store.add_documents(documents)


# 3. Process query
processor = QueryProcessor()

query = processor.process(
    "Why did the payment service fail?"
)


# 4. Retrieve documents
retriever = Retriever(vector_store)

retrieved_documents = retriever.retrieve(
    query,
    k=5
)


# 5. Rerank documents
reranker = Reranker()

best_evidence = reranker.rerank(
    query,
    retrieved_documents,
    top_k=3
)


# 6. Display results
print("\\nBEST EVIDENCE:\\n")

for i, document in enumerate(best_evidence, start=1):
    print(f"{i}. {document.page_content}")
    print(document.metadata)
    print()