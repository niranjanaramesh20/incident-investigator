# Incident Investigation System

A FastAPI service that searches incident evidence and returns an AI generated
investigation report. The initial demo indexes the sample logs, alerts,
deployments, commits, and runbooks included in `backend/app/sample_data`.

## Run locally

Requirements: Python 3.10 or newer, Docker, and an OpenAI API key. The first
investigation downloads the reranker model and creates a local Chroma database.

Copy `.env.example` to `.env` in the repository root and fill in your OpenAI
key. Generate a shared API access token with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Put the generated value in `.env` as `API_ACCESS_TOKEN=...`. Protected API routes
require this bearer token; the UI asks for it and keeps it in memory only. The
example database URL matches the local PostgreSQL container below.
Start PostgreSQL from the repository root:

```bash
docker compose -f docker/docker-compose.yml up -d
```

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Apply the database migrations before starting the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API docs are at
`http://127.0.0.1:8000/docs`. Open the browser interface at
`http://127.0.0.1:8000/ui/`, enter the generated token, and connect to submit
investigations, inspect citations, and reopen saved reports.

## Investigate an incident

Send a `POST` request to `/investigate` with an incident description and a
question. On the first request, the service indexes bundled sample data in
`backend/data/chroma_db`. Later requests reuse that local index.

```bash
export API_ACCESS_TOKEN='paste-the-generated-token-here'
curl -X POST http://127.0.0.1:8000/investigate \
  -H "Authorization: Bearer $API_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "incident": "Payment transactions began failing after a production deployment.",
    "question": "What is the most likely cause of the failures?"
  }'
```

The response includes the investigation, a validation result, a confidence
score, and the evidence documents with their source metadata. The model may
report that the evidence is insufficient; treat the report as an aid for
investigation and verify its citations against the returned sources.
The `citations` array maps each `[Evidence N]` reference to its source metadata
and excerpt. `citation_warnings` flags references that do not resolve to
retrieved evidence or were not confirmed by evidence validation.
Timestamped evidence is also shown in chronological order in the report
timeline; each timeline item links back to its retrieved evidence.

You can narrow retrieval by adding optional `service`, `source_type`,
`start_time`, and `end_time` fields to the request. Source types are `alert`,
`deployment`, `git_commit`, `log`, and `runbook`; time values use ISO 8601.
For example, add `"service": "payment-service"` and
`"source_type": "log"` to search payment service logs only. The applied filters
are included in the saved report.

Set `CHROMA_PERSIST_DIRECTORY` to change where the local vector index is stored.

`GET /health` reports whether PostgreSQL, the OpenAI key, API token, and local
vector index are ready. The vector index is created when the first
investigation runs. `/health` remains public; investigation and saved-report
routes require `Authorization: Bearer <API_ACCESS_TOKEN>`.

Each successful `POST /investigate` is saved with its incident description,
question, answer, confidence, and full report. Use `GET /investigations` to list
saved investigations (`limit` and `offset` are supported), and
`GET /investigations/{investigation_id}` to retrieve a full saved report.

## Run automated tests

The unit tests use stubbed retrieval and model results, so they do not call the
OpenAI API:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
```
