import { useCallback, useEffect, useMemo, useState } from "react";

const PAGE_SIZE = 20;
const SOURCES = ["alert", "deployment", "git_commit", "log", "runbook"];
const STATUSES = ["open", "investigating", "resolved"];

function dateLabel(value) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function useApi(token) {
  return useCallback(async (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(url, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }, [token]);
}

function SectionHeading({ eyebrow, title, action, id }) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h2 id={id}>{title}</h2></div>{action}</div>;
}

function ReportView({ report, record, api, role, onChanged }) {
  const [feedback, setFeedback] = useState(null);
  const [comment, setComment] = useState("");
  const [target, setTarget] = useState("");
  const [cause, setCause] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const id = record?.investigation_id;
  const body = report?.report || report || {};

  useEffect(() => {
    let active = true;
    if (id && api) api(`/investigations/${id}/feedback`).then((result) => {
      if (!active) return;
      setFeedback(result);
      setComment(result.my_feedback?.comment || "");
      setTarget(result.my_feedback?.correction_target || "");
      setCause(result.my_feedback?.corrected_cause || "");
    }).catch((error) => setNote(`Feedback could not load: ${error.message}`));
    return () => { active = false; };
  }, [id, api]);

  async function rate(rating) {
    setBusy(true); setNote("Saving feedback…");
    try {
      await api(`/investigations/${id}/feedback`, { method: "PUT", body: JSON.stringify({
        rating, comment, correction_target: rating === "incorrect" ? target : null,
        corrected_cause: rating === "incorrect" ? cause : null,
      }) });
      const result = await api(`/investigations/${id}/feedback`);
      setFeedback(result); setNote("Feedback saved.");
    } catch (error) { setNote(error.message); }
    finally { setBusy(false); }
  }

  return <div className="report-content">
    <div className="badges">
      {id && <span className="badge">Report #{id}</span>}
      <span className={`badge ${(body.confidence_score || 0) >= .7 ? "positive" : "caution"}`}>{Math.round((body.confidence_score || record?.confidence_score || 0) * 100)}% confidence</span>
      <span className={`badge ${body.validation?.is_valid ? "positive" : "caution"}`}>{body.validation?.is_valid ? "Evidence supported" : "Needs review"}</span>
    </div>
    <section className="report-block"><h3>Findings</h3><p className="finding">{body.investigation_result || record?.investigation_result || "No investigation result was returned."}</p></section>
    <section className="report-block"><h3>Validation</h3><p>{body.validation?.reason || "No validation details."}</p></section>
    {body.timeline?.length > 0 && <section className="report-block"><h3>Evidence timeline</h3><ol className="timeline">{body.timeline.map((item, index) => <li key={`${item.evidence_id}-${index}`}><time>{dateLabel(item.timestamp)}</time><span className="timeline-source">{[item.service, item.source_type].filter(Boolean).join(" · ")}</span><p>{item.summary}</p><a href={`#evidence-${item.evidence_id}`}>Open evidence {item.evidence_id}</a></li>)}</ol></section>}
    <section className="report-block"><h3>Citations</h3>{body.citations?.length ? body.citations.map((citation, index) => <article className="citation" key={`${citation.evidence_id}-${index}`}><div><strong>{citation.citation_id || `Evidence ${citation.evidence_id}`}</strong><span>{[citation.source_type, citation.service, citation.source_id || citation.source_path].filter(Boolean).join(" · ")}</span></div>{citation.timestamp && <small>{dateLabel(citation.timestamp)}</small>}<p>{citation.excerpt || "See retrieved evidence."}</p></article>) : <p className="muted">No evidence citations were returned.</p>}{body.citation_warnings?.length > 0 && <ul className="warnings">{body.citation_warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}</section>
    {body.evidence?.length > 0 && <details className="evidence-list"><summary>All retrieved evidence ({body.evidence.length})</summary>{body.evidence.map((item) => <article className="evidence-item" id={`evidence-${item.evidence_id}`} key={item.evidence_id}><strong>Evidence {item.evidence_id} · {item.metadata?.source_type || "source"}</strong><p>{item.content}</p></article>)}</details>}
    {id && <section className="report-block feedback"><h3>Team feedback</h3><p className="muted">{feedback ? `${feedback.helpful} helpful · ${feedback.incorrect} incorrect` : "Loading feedback…"}</p>{role !== "viewer" ? <><label>Comment (optional)<textarea value={comment} maxLength={2000} onChange={(event) => setComment(event.target.value)} /></label><label>Incorrect finding or citation<input value={target} maxLength={500} onChange={(event) => setTarget(event.target.value)} /></label><label>Corrected cause<input value={cause} maxLength={2000} onChange={(event) => setCause(event.target.value)} /></label><div className="button-row"><button className="button secondary" disabled={busy} onClick={() => rate("helpful")}>Helpful</button><button className="button secondary" disabled={busy || (!!target.trim() !== !!cause.trim())} onClick={() => rate("incorrect")}>Incorrect</button></div></> : <p className="muted">Viewer accounts cannot submit feedback.</p>}{note && <p className="form-note" role="status">{note}</p>}</section>}
    {record && <Collaboration record={record} api={api} role={role} onChanged={onChanged} />}
  </div>;
}

function Collaboration({ record, api, role, onChanged }) {
  const [comments, setComments] = useState([]);
  const [activities, setActivities] = useState([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const id = record.investigation_id;
  useEffect(() => {
    Promise.all([api(`/investigations/${id}/comments`), api(`/investigations/${id}/activity`)]).then(([notes, events]) => {
      setComments(notes); setActivities(events);
    }).catch((reason) => setError(reason.message));
  }, [id, api]);
  async function addComment(event) {
    event.preventDefault();
    try {
      await api(`/investigations/${id}/comments`, { method: "POST", body: JSON.stringify({ body }) });
      setBody("");
      const [notes, events] = await Promise.all([api(`/investigations/${id}/comments`), api(`/investigations/${id}/activity`)]);
      setComments(notes); setActivities(events); onChanged?.();
    } catch (reason) { setError(reason.message); }
  }
  return <section className="report-block collaboration"><h3>Handoff and activity</h3>{comments.length ? comments.map((item) => <article className="comment" key={item.id}><strong>{item.author} · {dateLabel(item.created_at)}</strong><p>{item.body}</p></article>) : <p className="muted">No handoff notes yet.</p>}{role !== "viewer" && <form onSubmit={addComment} className="comment-form"><label htmlFor="handoff-comment">Add a handoff note</label><textarea id="handoff-comment" value={body} maxLength={5000} required onChange={(event) => setBody(event.target.value)} /><button className="button secondary">Add note</button></form>}<details><summary>Activity history ({activities.length})</summary><ul className="activity-list">{activities.map((item, index) => <li key={index}>{item.actor ? `${item.actor} · ` : ""}{item.details} <span>{dateLabel(item.created_at)}</span></li>)}</ul></details>{error && <p className="form-note error">{error}</p>}</section>;
}

export default function App() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState(null);
  const api = useApi(token);
  const [health, setHealth] = useState(null);
  const [auth, setAuth] = useState({ email: "", password: "" });
  const [authError, setAuthError] = useState("");
  const [incident, setIncident] = useState("");
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState({ service: "", source_type: "", start_time: "", end_time: "" });
  const [report, setReport] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [search, setSearch] = useState({ q: "", service: "", status: "", assignee: "", min_confidence: "", created_after: "", created_before: "" });
  const [appliedSearch, setAppliedSearch] = useState({});
  const [ingestType, setIngestType] = useState("log");
  const [records, setRecords] = useState('[{"source_id":"trace-104","service":"payment-service","timestamp":"2026-07-25T10:40:00","level":"ERROR","message":"Database connection timeout"}]');
  const [ingestMessage, setIngestMessage] = useState("");
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const [evaluations, setEvaluations] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [team, setTeam] = useState([]);

  const analyst = user?.role === "admin" || user?.role === "analyst";
  const userLabel = useMemo(() => user ? `${user.email} · ${user.role}` : "Not signed in", [user]);

  const loadHealth = useCallback(async () => {
    try { const result = await fetch("/health").then((response) => response.json()); setHealth(result); }
    catch { setHealth(null); }
  }, []);

  const loadHistory = useCallback(async (nextOffset = 0, filtersApplied = appliedSearch) => {
    if (!token) { setHistory([]); return; }
    const params = new URLSearchParams({ limit: String(PAGE_SIZE + 1), offset: String(nextOffset) });
    Object.entries(filtersApplied).forEach(([key, value]) => {
      if (!value) return;
      params.set(key, key.startsWith("created_") ? new Date(value).toISOString() : value);
    });
    try {
      const results = await api(`/investigations?${params}`);
      setHistory(results.slice(0, PAGE_SIZE)); setHasNext(results.length > PAGE_SIZE); setOffset(nextOffset);
    } catch (error) { setMessage(`Saved reports could not load: ${error.message}`); }
  }, [token, api, appliedSearch]);

  const refreshNotifications = useCallback(async () => {
    if (!token) return;
    try { const result = await api("/notifications?limit=30"); setNotifications(result.items); setUnread(result.unread_count); }
    catch { /* Notification access is secondary to the main workspace. */ }
  }, [token, api]);

  const refreshEvaluations = useCallback(async () => {
    if (!token) return;
    try { setEvaluations(await api("/evaluations/runs?limit=10")); }
    catch { setEvaluations([]); }
  }, [token, api]);

  const refreshCorrections = useCallback(async () => {
    if (!token || user?.role === "viewer") return;
    try { setCorrections(await api("/evaluations/corrections")); }
    catch { setCorrections([]); }
  }, [token, user, api]);

  useEffect(() => { loadHealth(); const timer = window.setInterval(loadHealth, 60000); return () => window.clearInterval(timer); }, [loadHealth]);
  useEffect(() => { if (token) { loadHistory(0); refreshNotifications(); refreshEvaluations(); refreshCorrections(); if (user?.role === "admin") api("/users").then(setTeam).catch(() => setTeam([])); } else { setHistory([]); setTeam([]); setNotifications([]); setCorrections([]); } }, [token, user, api, loadHistory, refreshNotifications, refreshEvaluations, refreshCorrections]);

  async function signIn(event) {
    event.preventDefault(); setAuthError("");
    try {
      const result = await api("/auth/login", { method: "POST", body: JSON.stringify(auth) });
      setToken(result.access_token); setUser(result.user); setAuth((value) => ({ ...value, password: "" })); setMessage("");
    } catch (error) { setAuthError(error.message); }
  }
  function signOut() { setToken(""); setUser(null); setSelected(null); setReport(null); setHistory([]); setOffset(0); setHasNext(false); setTeam([]); setNotifications([]); setEvaluations([]); setMessage("Signed out."); }

  async function submitInvestigation(event) {
    event.preventDefault(); setBusy(true); setMessage("");
    const payload = { incident, question };
    Object.entries(filters).forEach(([key, value]) => { if (value) payload[key] = key.endsWith("_time") ? new Date(value).toISOString() : value; });
    try {
      const result = await api("/investigate", { method: "POST", body: JSON.stringify(payload) });
      setReport(result); setSelected({ investigation_id: result.investigation_id, incident, question, investigation_result: result.investigation_result, confidence_score: result.confidence_score, status: "open", created_at: result.created_at });
      await loadHistory(0); await refreshNotifications();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  async function openReport(item) {
    setBusy(true); setMessage("");
    try { const result = await api(`/investigations/${item.investigation_id}`); setSelected(item); setReport(result); document.querySelector("#report")?.scrollIntoView({ behavior: "smooth", block: "start" }); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  async function updateStatus(item, status) {
    try { await api(`/investigations/${item.investigation_id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }); await loadHistory(offset); await refreshNotifications(); }
    catch (error) { setMessage(error.message); }
  }

  async function assign(item, assignedTo) {
    try { await api(`/investigations/${item.investigation_id}/assignee`, { method: "PATCH", body: JSON.stringify({ assigned_to: assignedTo || null }) }); await loadHistory(offset); await refreshNotifications(); }
    catch (error) { setMessage(error.message); }
  }

  async function exportReport(id) {
    try {
      const response = await fetch(`/investigations/${id}/export`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) { const error = await response.json(); throw new Error(error.detail || "Export failed."); }
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `investigation-${id}.md`; anchor.click(); URL.revokeObjectURL(url);
    } catch (error) { setMessage(error.message); }
  }

  async function ingest(event) {
    event.preventDefault(); setBusy(true); setIngestMessage("");
    try {
      const result = await api("/evidence", { method: "POST", body: JSON.stringify({ source_type: ingestType, records: JSON.parse(records) }) });
      setIngestMessage(`Indexed ${result.record_count} records · ${result.inserted} new · ${result.updated} updated.`); loadHealth();
    } catch (error) { setIngestMessage(error instanceof SyntaxError ? "Enter valid JSON records." : error.message); }
    finally { setBusy(false); }
  }

  async function runEvaluation() {
    setBusy(true); setMessage("Starting evaluation…");
    try {
      const run = await api("/evaluations/runs", { method: "POST" });
      setMessage(`Evaluation run #${run.run_id} is queued for dataset v${run.dataset_version}.`);
      await refreshEvaluations();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  async function approveCorrection(feedbackId) {
    try { const result = await api(`/evaluations/corrections/${feedbackId}/approve`, { method: "POST" }); setMessage(`Added to evaluation dataset v${result.dataset_version}.`); await Promise.all([refreshCorrections(), refreshEvaluations()]); }
    catch (error) { setMessage(error.message); }
  }

  async function updateTeamAccount(id, changes) {
    try { await api(`/users/${id}`, { method: "PATCH", body: JSON.stringify(changes) }); setTeam(await api("/users")); setMessage("Account updated."); }
    catch (error) { setMessage(error.message); }
  }

  async function createAccount(event) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try { await api("/users", { method: "POST", body: JSON.stringify({ email: form.get("email"), password: form.get("password"), role: form.get("role") }) }); event.currentTarget.reset(); setTeam(await api("/users")); setMessage("Account created."); }
    catch (error) { setMessage(error.message); }
  }

  return <>
    <header className="topbar">
      <a className="brand" href="#top"><span className="brand-mark">II</span><span>Incident Investigator</span></a>
      <form className="auth-controls" onSubmit={signIn}>{!user ? <><input type="email" aria-label="Account email" placeholder="Email" autoComplete="username" required value={auth.email} onChange={(event) => setAuth({ ...auth, email: event.target.value })} /><input type="password" aria-label="Account password" placeholder="Password" autoComplete="current-password" required value={auth.password} onChange={(event) => setAuth({ ...auth, password: event.target.value })} /><button className="button secondary">Sign in</button></> : <><span className="user-label">{userLabel}</span><button type="button" className="button secondary" onClick={signOut}>Sign out</button></>}{authError && <span className="auth-error" role="alert">{authError}</span>}</form>
      <div className={`health ${health?.ready ? "ready" : "degraded"}`}><span className="health-dot" />{health?.ready ? "Services ready" : "Services degraded"}</div>
    </header>
    <nav className="workspace-nav" aria-label="Workspace sections"><a href="#investigate">Investigate</a><a href="#evidence">Evidence</a><a href="#history">Saved reports</a></nav>

    <main id="top" className="workspace">
      <section className="intro"><span className="eyebrow">Operations workspace</span><h1>Find the signal.<br /><span>Understand the incident.</span></h1><p>Ask a question across logs, alerts, deployments, commits, and runbooks. Review every conclusion against its supporting evidence.</p></section>
      {!user && <div className="access-banner" role="status">Sign in to view saved reports. Analyst or administrator access is required to investigate incidents and add evidence.</div>}
      {message && <div className="notice" role="status">{message}<button aria-label="Dismiss message" onClick={() => setMessage("")}>×</button></div>}

      <div className="main-grid">
        <section className="panel" id="investigate"><SectionHeading eyebrow="New investigation" title="Describe what happened" /><form onSubmit={submitInvestigation}>
          <label>Incident summary<textarea required maxLength={10000} rows={5} disabled={!analyst} value={incident} onChange={(event) => setIncident(event.target.value)} placeholder="Payment failures began shortly after the production deployment…" /></label>
          <label>What do you want to find out?<input required maxLength={2000} disabled={!analyst} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What caused the increase in failed payments?" /></label>
          <details className="filters"><summary>Filter the evidence <span>Optional</span></summary><div className="filter-grid">
            <label>Service<input disabled={!analyst} value={filters.service} onChange={(event) => setFilters({ ...filters, service: event.target.value })} placeholder="payment-service" /></label>
            <label>Source type<select disabled={!analyst} value={filters.source_type} onChange={(event) => setFilters({ ...filters, source_type: event.target.value })}><option value="">All sources</option>{SOURCES.map((source) => <option key={source} value={source}>{source.replace("_", " ")}</option>)}</select></label>
            <label>From<input type="datetime-local" disabled={!analyst} value={filters.start_time} onChange={(event) => setFilters({ ...filters, start_time: event.target.value })} /></label>
            <label>To<input type="datetime-local" disabled={!analyst} value={filters.end_time} onChange={(event) => setFilters({ ...filters, end_time: event.target.value })} /></label>
          </div></details>
          <button className="button primary" disabled={!analyst || busy}>{busy ? "Working…" : "Run investigation"}<span>↗</span></button>
          {!analyst && <p className="muted access-hint">{user ? "Viewer accounts have read-only access." : "Sign in with an analyst or administrator account to continue."}</p>}
        </form></section>

        <section className="panel report-panel" id="report"><SectionHeading eyebrow="Investigation report" title={selected ? `Investigation #${selected.investigation_id}` : "Your findings will appear here"} action={selected && <button className="button secondary" onClick={() => exportReport(selected.investigation_id)}>Export Markdown</button>} />
          {report ? <ReportView key={selected?.investigation_id || "latest"} report={report} record={selected} api={api} role={user?.role} onChanged={() => refreshNotifications()} /> : <div className="empty-state"><span className="empty-mark">⌕</span><p>Start an investigation or open a saved report to see findings, confidence, and evidence citations.</p></div>}
        </section>
      </div>

      <section className="panel section-panel" id="evidence"><SectionHeading eyebrow="Evidence sources" title="Add or refresh evidence" /><form onSubmit={ingest}>
        <div className="ingest-tools"><label>Source type<select value={ingestType} disabled={!analyst} onChange={(event) => setIngestType(event.target.value)}>{SOURCES.map((source) => <option key={source} value={source}>{source.replace("_", " ")}</option>)}</select></label><button className="button primary" disabled={!analyst || busy}>Index records <span>↗</span></button></div>
        <label>JSON records<textarea className="json-input" rows={7} spellCheck="false" required disabled={!analyst} value={records} onChange={(event) => setRecords(event.target.value)} /></label>
        <p className="muted">Use stable source IDs so refreshed records replace existing evidence.</p>{!analyst && <p className="access-hint">{user ? "Viewer accounts cannot add evidence." : "Sign in with an analyst or administrator account to add evidence."}</p>}{ingestMessage && <p className="form-note" role="status">{ingestMessage}</p>}
      </form></section>

      <section className="panel section-panel" id="history"><SectionHeading eyebrow="Investigation history" title="Saved reports" action={<button className="button secondary" onClick={() => loadHistory(offset)}>Refresh</button>} />
        {user && <><form className="history-filters" onSubmit={(event) => { event.preventDefault(); const next = Object.fromEntries(Object.entries(search).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()])); setAppliedSearch(next); loadHistory(0, next); }}>
          <input aria-label="Search reports" placeholder="Search incident or answer" value={search.q} onChange={(event) => setSearch({ ...search, q: event.target.value })} />
          <input aria-label="Service filter" placeholder="Service" value={search.service} onChange={(event) => setSearch({ ...search, service: event.target.value })} />
          <input aria-label="Assignee filter" placeholder="Assignee" value={search.assignee} onChange={(event) => setSearch({ ...search, assignee: event.target.value })} />
          <select aria-label="Status filter" value={search.status} onChange={(event) => setSearch({ ...search, status: event.target.value })}><option value="">All statuses</option>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select>
          <select aria-label="Minimum confidence" value={search.min_confidence} onChange={(event) => setSearch({ ...search, min_confidence: event.target.value })}><option value="">Any confidence</option><option value="0.4">40%+</option><option value="0.6">60%+</option><option value="0.8">80%+</option></select>
          <input type="datetime-local" aria-label="Created after" value={search.created_after} onChange={(event) => setSearch({ ...search, created_after: event.target.value })} />
          <input type="datetime-local" aria-label="Created before" value={search.created_before} onChange={(event) => setSearch({ ...search, created_before: event.target.value })} />
          <button className="button secondary">Apply filters</button>
        </form>
        <div className="history-list">{history.length ? history.map((item) => <HistoryRow key={item.investigation_id} item={item} role={user.role} onOpen={openReport} onStatus={updateStatus} onAssign={assign} onExport={exportReport} />) : <p className="muted">No saved reports match this view.</p>}</div>
        {(offset > 0 || hasNext) && <div className="pagination"><button className="button secondary" disabled={!offset} onClick={() => loadHistory(Math.max(0, offset - PAGE_SIZE))}>Previous</button><span>Reports {offset + 1}–{offset + history.length}{hasNext ? "+" : ""}</span><button className="button secondary" disabled={!hasNext} onClick={() => loadHistory(offset + PAGE_SIZE)}>Next</button></div>}
        </>}
        <details className="notification-box"><summary>Notifications <span>{unread} unread</span></summary><div className="notification-list">{notifications.length ? notifications.map((item) => <article className="notification" key={item.id}><button onClick={() => openReport({ investigation_id: item.investigation_id })}>{item.message}</button><span>{dateLabel(item.created_at)}</span>{!item.is_read && <button className="text-button" onClick={async () => { await api(`/notifications/${item.id}`, { method: "PATCH", body: JSON.stringify({ is_read: true }) }); refreshNotifications(); }}>Mark read</button>}</article>) : <p className="muted">No notifications yet.</p>}</div></details>
      </section>

      {user && user.role !== "viewer" && <section className="panel section-panel"><SectionHeading eyebrow="Quality checks" title="Evaluation history" action={<button className="button secondary" disabled={busy} onClick={runEvaluation}>Run evaluation</button>} /><button className="text-button" onClick={() => { refreshEvaluations(); refreshCorrections(); }}>Refresh runs and corrections</button><div className="evaluation-list">{evaluations.length ? evaluations.map((run) => <article className="evaluation-row" key={run.id}><strong>Run #{run.id} · dataset v{run.dataset_version}</strong><span className={`run-state ${run.status}`}>{run.status} · {run.completed_cases}/{run.case_count}</span>{run.status === "completed" && <p>{run.passed_count}/{run.case_count} passed · pass rate {Math.round(run.pass_rate * 100)}% · citations {Math.round(run.citation_rate * 100)}%</p>}{run.error && <p className="error">{run.error}</p>}</article>) : <p className="muted">No evaluation runs recorded yet.</p>}</div><details className="correction-review"><summary>Review analyst corrections ({corrections.length})</summary><div className="evaluation-list">{corrections.length ? corrections.map((correction) => <article className="evaluation-row" key={correction.feedback_id}><strong>Investigation #{correction.investigation_id}</strong><p>{correction.incident}</p><p>Disputed: {correction.correction_target}</p><p>Proposed cause: {correction.corrected_cause}</p><button className="button secondary" disabled={correction.approved} onClick={() => approveCorrection(correction.feedback_id)}>{correction.approved ? "Included in current set" : "Approve as evaluation case"}</button></article>) : <p className="muted">No analyst corrections to review.</p>}</div></details></section>}

      {user?.role === "admin" && <section className="panel section-panel"><SectionHeading eyebrow="Administration" title="Team accounts" /><form className="team-form" onSubmit={createAccount}><input name="email" required type="email" placeholder="Teammate email" /><input name="password" required type="password" minLength={12} placeholder="Temporary password (12+ characters)" /><select name="role"><option value="analyst">Analyst</option><option value="viewer">Viewer</option><option value="admin">Admin</option></select><button className="button secondary">Create account</button></form><div className="team-list">{team.map((member) => <div className="team-account" key={member.id}><span>{member.email}</span><select aria-label={`Role for ${member.email}`} value={member.role} disabled={member.email === user.email} onChange={(event) => updateTeamAccount(member.id, { role: event.target.value })}><option value="admin">Admin</option><option value="analyst">Analyst</option><option value="viewer">Viewer</option></select><label><input type="checkbox" checked={member.is_active} disabled={member.email === user.email} onChange={(event) => updateTeamAccount(member.id, { is_active: event.target.checked })} /> Active</label></div>)}</div></section>}
      <footer>AI-assisted analysis · Verify conclusions against the cited source material.</footer>
    </main>
  </>;
}

function HistoryRow({ item, role, onOpen, onStatus, onAssign, onExport }) {
  const [assignee, setAssignee] = useState(item.assignee || "");
  return <article className="history-row"><button className="history-open" onClick={() => onOpen(item)}><strong>{item.incident || `Investigation #${item.investigation_id}`}</strong><span>{item.question} · {dateLabel(item.created_at)}</span></button><div className="history-actions"><span className="confidence">{Math.round((item.confidence_score || 0) * 100)}%</span><select aria-label={`Status for report ${item.investigation_id}`} disabled={role === "viewer"} value={item.status || "open"} onChange={(event) => onStatus(item, event.target.value)}>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select><button className="text-button" onClick={() => onExport(item.investigation_id)}>Export</button></div>{role !== "viewer" && <form className="assignee-form" onSubmit={(event) => { event.preventDefault(); onAssign(item, assignee.trim()); }}><input type="email" aria-label="Assignee email" placeholder="Teammate email (blank to unassign)" value={assignee} onChange={(event) => setAssignee(event.target.value)} /><button className="button secondary">Save assignee</button></form>}</article>;
}
