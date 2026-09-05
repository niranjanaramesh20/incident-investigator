from app.ingestion.runbook_loader import RunbookLoader

loader = RunbookLoader()

runbook = loader.load("data/runbooks/payment-service.md")

print(runbook)