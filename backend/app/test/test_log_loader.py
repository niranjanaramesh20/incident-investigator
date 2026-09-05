from app.ingestion.log_loader import LogLoader

loader = LogLoader()

logs = loader.load("data/logs/application.jsonl")

for log in logs[:5]:
    print(log)