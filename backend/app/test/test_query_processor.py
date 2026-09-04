from rag.query_processor import QueryProcessor


processor = QueryProcessor()

query = processor.process(
    "   Why did payment service fail?   "
)

print(query)