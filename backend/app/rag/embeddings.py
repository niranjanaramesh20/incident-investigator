from langchain_openai import OpenAIEmbeddings

class EmbeddingService:
    def __init__(self):
        self.embedding_model = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )

    def generate(self, text: str):
        return self.embedding_model.embed_query(text)

    def generate_documents(self, texts: list[str]):
        return self.embedding_model.embed_documents(texts)