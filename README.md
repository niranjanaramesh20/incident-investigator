# Incident Investigation System

A FastAPI service that searches incident evidence and returns an AI generated
investigation report. The initial demo indexes the sample logs, alerts,
deployments, commits, and runbooks included in `backend/app/sample_data`.

## Run locally

Requirements: Python 3.10 or newer and an OpenAI API key. The first investigation
downloads the reranker model and creates a local Chroma database.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set `OPENAI_API_KEY` before starting the API. You can copy `.env.example` to
`.env` in the repository root and fill in your key; the application loads that
file automatically.

```bash
export OPENAI_API_KEY="your-openai-api-key"
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API docs are at
`http://127.0.0.1:8000/docs`.

## Investigate an incident

Send a `POST` request to `/investigate` with an incident description and a
question. On the first request, the service indexes bundled sample data in
`backend/data/chroma_db`. Later requests reuse that local index.

```bash
curl -X POST http://127.0.0.1:8000/investigate \
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

Set `CHROMA_PERSIST_DIRECTORY` to change where the local vector index is stored.
