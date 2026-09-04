from rag.embeddings import EmbeddingService

embedding_service = EmbeddingService()

text = "Database Connection failed after deployment"

vector = embedding_service.generate(text)

print("Vector length:", len(vector))
print(vector[:5])
