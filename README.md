# Incident Investigation System

A FastAPI service that searches incident evidence and returns an AI generated
investigation report. The initial demo indexes the sample logs, alerts,
deployments, commits, and runbooks included in `backend/app/sample_data`.

## Run locally

Requirements: Python 3.10 or newer, Docker, and an OpenAI API key. The first
investigation downloads the reranker model and creates a local Chroma database.

Copy `.env.example` to `.env` in the repository root, add your OpenAI key, and
generate a session signing secret:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Put the generated value in `.env` as `SESSION_SECRET=...`. After applying the
migrations, create the first administrator account with `BOOTSTRAP_ADMIN_EMAIL`
and `BOOTSTRAP_ADMIN_PASSWORD` set in `.env`. Use a unique password of at least
12 characters; the setup command reads these values and stores only a password
hash.

The example database URL matches the local PostgreSQL container below.
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
python -m app.scripts.create_admin
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API docs are at
`http://127.0.0.1:8000/docs`. Open `http://127.0.0.1:8000/ui/` and sign in with
the administrator account. Admins can create analyst and viewer accounts with
`POST /users`; account passwords must have at least 12 characters. Analysts
can investigate, ingest evidence, assign work, update status, and comment.
Viewers can read saved reports and history. Sessions last 12 hours and the UI
keeps the session token in memory only.

## Run the React frontend

A separate React application lives in `frontend/`. Keep the FastAPI server
running on port 8000, then start the React development server in another
terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies API requests to the FastAPI server;
the existing backend-served interface at `/ui/` remains available as well.
Build the standalone frontend with `npm run build` from `frontend/`.

## Investigate an incident

Send a `POST` request to `/investigate` with an incident description and a
question. On the first request, the service indexes bundled sample data in
`backend/data/chroma_db`. Later requests reuse that local index.

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"your-admin-password"}'
```

Copy the returned `access_token` into `SESSION_TOKEN`, then:

```bash
export SESSION_TOKEN='paste-the-access-token-here'
curl -X POST http://127.0.0.1:8000/investigate \
  -H "Authorization: Bearer $SESSION_TOKEN" \
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

`GET /health` reports whether PostgreSQL, the OpenAI key, session signing secret, and local
vector index are ready. The vector index is created when the first
investigation runs. `/health` remains public; protected routes require a signed
account session in `Authorization: Bearer <session-token>`. The old shared API
token is disabled by default. Set `ALLOW_LEGACY_API_TOKEN=true` only during a
controlled migration; it grants administrator access to anyone holding that
token.

## Add or refresh evidence

Use the UI's **Add or refresh evidence** panel or call the authenticated
`POST /evidence` endpoint. Submit a JSON array with one source type per request.
The endpoint accepts up to 250 records and a 1 MB request body. Use a stable
`source_id` (or commit `hash` / runbook `file_path`) so updates replace the
matching indexed source instead of adding a duplicate.

```bash
curl -X POST http://127.0.0.1:8000/evidence \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "source_type": "log",
    "records": [{
      "source_id": "trace-104",
      "service": "payment-service",
      "timestamp": "2026-07-25T10:40:00",
      "level": "ERROR",
      "message": "Database connection timeout"
    }]
  }'
```

Records require source-specific fields and ISO 8601 timestamps where supplied.
Logs and alerts require `message` and `timestamp`; deployments require `version`,
`status`, and `timestamp`; commits require `hash` and `message`; runbooks require
`file_path` and `content`. The response reports how many documents were
inserted or updated.

Each successful `POST /investigate` is saved with its incident description,
question, answer, confidence, and full report. Use `GET /investigations` to list
saved investigations (`limit` and `offset` are supported). The history endpoint
also accepts `q` to search incident titles, descriptions, questions, and answers;
`service` to filter by service name; `min_confidence` and `max_confidence` from
0 to 1; and ISO 8601 `created_after` and `created_before` timestamps. For example:

```text
GET /investigations?q=payment&service=payment-service&min_confidence=0.6&created_after=2026-10-01T00:00:00Z
```

The web interface exposes text, service, minimum-confidence, and date filters.
Use
`GET /investigations/{investigation_id}` to retrieve a full saved report.
Download a Markdown copy, including findings, validation, timeline, and citations,
from the authenticated `GET /investigations/{investigation_id}/export` endpoint.
The saved reports list in the web interface has an **Export Markdown** button
for each report. Investigations have an `open`, `investigating`, or `resolved`
status (new reports start as `open`). Filter the history with the `status` query
parameter, update one with authenticated `PATCH /investigations/{investigation_id}/status`
and a JSON body such as `{"status":"resolved"}`, or change it from the status
selector beside a saved report in the web interface. Apply the new database
migrations with `alembic upgrade head` from the `backend` directory. Each actual
status transition is recorded with its previous status, new status, and timestamp;
retrieve the audit trail with authenticated
`GET /investigations/{investigation_id}/status-history` or expand **Status history**
on a saved report in the web interface. Selecting the current status again does
not create a duplicate event.

Admins create accounts with `POST /users`, for example:

```json
{"email":"analyst@example.com","password":"a-unique-password-at-least-12-chars","role":"analyst"}
```

Roles are `admin`, `analyst`, and `viewer`. Admins can manage accounts in the
web interface's **Team accounts** panel or use the API. They can list accounts
with `GET /users` and change a user's role or active state with `PATCH /users/{id}`.
Each status event and collaboration action records the signed-in account as its
actor. Accounts are disabled immediately when an admin sets `is_active` to false.

Investigations can also be assigned to a teammate using
`PATCH /investigations/{investigation_id}/assignee` with
`{"assigned_to":"analyst@example.com"}` (send `null` to unassign), and filtered with the
`assignee` query parameter on `GET /investigations`. Add and list handoff notes
with `POST` and `GET /investigations/{investigation_id}/comments`; submit a comment
body such as `{"body":"Restarted the worker; monitoring error rate."}`. The
comment author comes from the signed-in account. The **Comments and activity** panel
shows collaboration notes and the audit trail. Assignment, comment, and status
changes also create in-app notifications, available from authenticated
`GET /notifications`; mark an item read with `PATCH /notifications/{id}` and
`{"is_read":true}`. Notifications are delivered to the assigned account where
applicable. For optional external alerts, configure `SLACK_WEBHOOK_URL` for a
Slack incoming webhook, or `NOTIFICATION_SMTP_HOST`, `NOTIFICATION_EMAIL_FROM`,
and the related SMTP settings in `.env`. Delivery is disabled when those values
are blank; external messages are sent only after a configured assignment or
status change.

Analysts can rate a saved report as `helpful` or `incorrect` in the report view.
Feedback comments explain what should change. For incorrect reports, analysts
can also record the specific finding or citation and the corrected cause. A
user's latest rating replaces their earlier rating for that report. Read team totals with
`GET /investigations/{id}/feedback`; submit or update your own rating with
`PUT /investigations/{id}/feedback`, for example:

```json
{
  "rating":"incorrect",
  "comment":"The cited deployment was unrelated to the alert.",
  "correction_target":"Finding: deployment caused the errors",
  "corrected_cause":"The database connection pool was exhausted."
}
```

The small, versioned known-incident set is in
`backend/app/evaluations/known_incidents.json`. After migrations and sample
evidence are available, run it from `backend` with:

```bash
python -m app.scripts.evaluate_known_incidents
```

Analysts and admins can also run evaluations from **Evaluation history** in the
web interface and watch per-case progress. The command and button use the same
current case set and save results to PostgreSQL. Analysts can review corrections
in the **Review analyst corrections** queue and approve them into a new immutable
dataset version. Each subsequent run records that version, so results stay tied
to the exact reviewed cases used. Expand a run's dataset snapshot in the UI or
retrieve it with authenticated `GET /evaluations/case-sets/{version}`. Signed-in
users can compare recent runs in **Evaluation history**. The set is a small
regression signal; its expected-term and citation checks are not a substitute
for analyst review.

## Public access without sign-in

Set `ALLOW_PUBLIC_ACCESS=true` in the backend environment to let visitors run
investigations and add evidence without signing in. The React interface does not
display a sign-in form or a Saved reports panel. Public uploads and reports are
shared, so do not use this mode for private incident data.

The chat composer accepts `.log` and `.txt` files as log evidence, plus `.json`
and `.jsonl` files containing evidence records. Attachments are added to the
shared evidence library before the investigation runs. A request can contain at
most 250 records and 1 MB of combined evidence data.

Public requests can incur OpenAI API charges. The backend limits each client IP
to five investigations per minute and 30 per day, and two evidence uploads per
hour and 10 per day by default. Configure `PUBLIC_INVESTIGATIONS_PER_MINUTE`,
`PUBLIC_INVESTIGATIONS_PER_DAY`, `PUBLIC_EVIDENCE_UPLOADS_PER_HOUR`, and
`PUBLIC_EVIDENCE_UPLOADS_PER_DAY` to change those values. Set
`TRUST_PROXY_HEADERS=true` only when a trusted reverse proxy overwrites
`X-Real-IP` and the backend cannot be reached directly. The in-memory limiter
resets on restart and is per backend process, so use an edge rate limit such as
AWS WAF as well when deploying multiple workers or instances.

## Run automated tests

The unit tests use stubbed retrieval and model results, so they do not call the
OpenAI API:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
```
