import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

class VectorStore:

    def __init__(self):
        self.embedding_model = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        self.vector_store = Chroma(
            collection_name="incident_evidence",
            embedding_function=self.embedding_model,
            persist_directory=os.getenv(
                "CHROMA_PERSIST_DIRECTORY",
                str(Path(__file__).resolve().parents[2] / "data" / "chroma_db"),
            ),
        )

    def add_documents(self, documents: list):
        self.vector_store.add_documents(documents)

    def is_empty(self) -> bool:
        return self.vector_store._collection.count() == 0

    def search(self, query: str, k: int=5): #search for 5 relevant results
        return self.vector_store.similarity_search(
            query=query,
            k=k
        )
