from app.ingestion.git_loader import GitLoader

loader = GitLoader()

commits = loader.load(".")

for commit in commits[:5]:
    print(commit)