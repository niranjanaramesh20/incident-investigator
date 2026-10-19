import hashlib
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
        self.upsert_documents(documents)

    def upsert_documents(self, documents: list) -> dict:
        if not documents:
            return {"inserted": 0, "updated": 0}

        ids = []
        for document in documents:
            metadata = document.metadata or {}
            source_type = str(metadata.get("source_type", "evidence"))
            source_id = str(
                metadata.get("source_id")
                or hashlib.sha256(document.page_content.encode("utf-8")).hexdigest()
            )
            ids.append(
                hashlib.sha256(f"{source_type}:{source_id}".encode("utf-8")).hexdigest()
            )

        existing_ids = set(
            self.vector_store._collection.get(ids=ids, include=["metadatas"])["ids"]
        )
        embeddings = self.embedding_model.embed_documents(
            [document.page_content for document in documents]
        )
        self.vector_store._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=[document.page_content for document in documents],
            metadatas=[document.metadata for document in documents],
        )
        return {
            "inserted": len(ids) - len(existing_ids),
            "updated": len(existing_ids),
        }

    def is_empty(self) -> bool:
        return self.vector_store._collection.count() == 0

    def search(self, query: str, k: int = 5, where: dict | None = None):
        return self.vector_store.similarity_search(
            query=query,
            k=k,
            filter=where,
        )
