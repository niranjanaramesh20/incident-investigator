from app.rag.vector_store import VectorStore

class Retriever:

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def retrieve(self, query: str, k: int = 10, filters: dict | None = None):
        return self.vector_store.search(
            query=query,
            k=k,
            where=filters,
        )
