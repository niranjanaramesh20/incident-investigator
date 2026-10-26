import { useCallback, useEffect, useRef, useState } from "react";

const SOURCES = ["alert", "deployment", "git_commit", "log", "runbook"];

function inferSourceType(record) {
  if (SOURCES.includes(record.source_type)) return record.source_type;
  if (record.hash) return "git_commit";
  if (record.file_path && record.content) return "runbook";
  if (record.version && record.status) return "deployment";
  if (record.severity || record.metric) return "alert";
  return "log";
}

async function readEvidenceFile(file) {
  if (file.size > 1_000_000) throw new Error(`${file.name} is larger than the 1 MB upload limit.`);
  const extension = file.name.toLowerCase().split(".").pop();
  const content = await file.text();

  if (extension === "log" || extension === "txt") {
    if (!content.trim()) throw new Error(`${file.name} is empty.`);
    const chunks = content.match(/[\s\S]{1,15000}/g) || [];
    const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 180);
    return chunks.map((message, index) => ({
      source_type: "log",
      source_id: `${safeName}:${index + 1}`,
      timestamp: new Date(file.lastModified).toISOString(),
      message,
    }));
  }

  if (extension !== "json" && extension !== "jsonl") {
    throw new Error(`${file.name}: use JSON, JSONL, LOG, or TXT files.`);
  }
  const parsed = extension === "jsonl"
    ? content.split(/\r?\n/).filter((line) => line.trim()).map((line) => JSON.parse(line))
    : JSON.parse(content);
  const list = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.records) ? parsed.records : [parsed];
  if (!list.length || list.some((record) => !record || Array.isArray(record) || typeof record !== "object")) {
    throw new Error(`${file.name} must contain evidence records as a JSON array, an object with a records array, or JSONL rows.`);
  }
  return list.map((record) => ({ ...record, source_type: record.source_type || parsed?.source_type || inferSourceType(record) }));
}

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

function ReportView({ report, record, onExport }) {
  const body = report?.report || report || {};
  const citations = body.citations || [];
  const evidence = body.evidence || [];
  const unresolved = citations.filter((item) => !item.validated_as_supporting);
  const confidence = body.confidence_score ?? record?.confidence_score ?? 0;

  return <div className="report-content">
    <div className="report-summary">
      <span className={`badge ${body.validation?.is_valid ? "positive" : "caution"}`}>
        {body.validation?.is_valid ? "Validator marked supported" : "Needs evidence review"}
      </span>
      <span className="badge">Confidence estimate · {Math.round(confidence * 100)}%</span>
      {record?.investigation_id && <button className="button secondary export-button" onClick={() => onExport(record.investigation_id)}>Export report</button>}
    </div>
    <p className="confidence-note">The score is a heuristic, not a probability. Check the cited sources before relying on the conclusion.</p>

    <section className="report-block"><h3>Findings</h3><div className="finding">{body.investigation_result || record?.investigation_result || "No investigation result was returned."}</div></section>

    <section className="report-block validation-block">
      <h3>Evidence check</h3>
      <p>{body.validation?.reason || "No validation details were returned."}</p>
      {body.citation_warnings?.length > 0 && <ul className="warnings">{body.citation_warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
      {unresolved.length > 0 && <p className="review-note">{unresolved.length} citation{unresolved.length === 1 ? " was" : "s were"} not confirmed as supporting evidence. Review them before presenting the conclusion.</p>}
    </section>

    {citations.length > 0 && <section className="report-block"><h3>Sources cited <span className="section-count">{citations.length}</span></h3>
      <div className="citation-list">{citations.map((citation, index) => <article className="citation" key={`${citation.evidence_id}-${index}`}>
        <div className="citation-heading"><strong>{citation.citation_id || `Evidence ${citation.evidence_id}`}</strong><span>{[citation.source_type?.replace("_", " "), citation.service, citation.source_id || citation.source_path].filter(Boolean).join(" · ")}</span></div>
        <div className="citation-tags"><span className={citation.cited_in_answer ? "tag tag-answer" : "tag"}>{citation.cited_in_answer ? "Cited in answer" : "Validator source"}</span><span className={citation.validated_as_supporting ? "tag tag-valid" : "tag tag-review"}>{citation.validated_as_supporting ? "Support confirmed" : "Not confirmed"}</span>{citation.timestamp && <time>{dateLabel(citation.timestamp)}</time>}</div>
        <p>{citation.excerpt || "See retrieved evidence."}</p>
      </article>)}</div>
    </section>}

    {body.timeline?.length > 0 && <section className="report-block"><h3>Evidence timeline</h3><ol className="timeline">{body.timeline.map((item, index) => <li key={`${item.evidence_id}-${index}`}><time>{dateLabel(item.timestamp)}</time><span className="timeline-source">{[item.service, item.source_type?.replace("_", " ")].filter(Boolean).join(" · ")}</span><p>{item.summary}</p><a href={`#evidence-${item.evidence_id}`}>View evidence {item.evidence_id}</a></li>)}</ol></section>}

    <details className="evidence-list"><summary>Retrieved evidence <span>{evidence.length} items</span></summary>
      {evidence.length ? evidence.map((item) => <article className="evidence-item" id={`evidence-${item.evidence_id}`} key={item.evidence_id}><strong>Evidence {item.evidence_id} · {item.metadata?.source_type?.replace("_", " ") || "source"}</strong><span className="evidence-meta">{[item.metadata?.service, item.metadata?.source_id || item.metadata?.source_path, item.metadata?.timestamp && dateLabel(item.metadata.timestamp)].filter(Boolean).join(" · ")}</span><p>{item.content}</p></article>) : <p className="muted">No evidence was retrieved for this investigation.</p>}
    </details>
  </div>;
}

export default function App() {
  const api = useApi("");
  const [health, setHealth] = useState(null);
  const [draft, setDraft] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const chatEndRef = useRef(null);

  const loadHealth = useCallback(async () => {
    try { setHealth(await fetch("/health").then((response) => response.json())); }
    catch { setHealth(null); }
  }, []);

  useEffect(() => {
    loadHealth();
    const timer = window.setInterval(loadHealth, 60000);
    return () => window.clearInterval(timer);
  }, [loadHealth]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatMessages, busy]);

  function chooseFiles(event) {
    const chosen = Array.from(event.target.files || []);
    setAttachments((current) => [...current, ...chosen].slice(0, 10));
    event.target.value = "";
  }

  async function submitChat(event) {
    event.preventDefault();
    const prompt = draft.trim();
    const files = attachments;
    if (busy || (!prompt && !files.length)) return;

    setChatMessages((current) => [...current, {
      role: "user",
      content: prompt,
      files: files.map((file) => ({ name: file.name, size: file.size })),
    }]);
    setDraft("");
    setAttachments([]);
    setBusy(true);
    try {
      if (files.length) {
        const records = [];
        for (const file of files) records.push(...await readEvidenceFile(file));
        if (records.length > 250) throw new Error("Attach files containing no more than 250 records total.");
        if (records.some((record) => Object.values(record).some((value) => typeof value === "string" && value.length > 20_000))) {
          throw new Error("A text field in an attachment exceeds the 20,000 character limit.");
        }
        if (JSON.stringify(records).length > 950_000) throw new Error("The combined attachments exceed the 1 MB upload limit.");
        await api("/evidence", { method: "POST", body: JSON.stringify({ source_type: "mixed", records }) });
        loadHealth();
      }

      const incident = prompt || "Investigate the attached evidence files.";
      const question = prompt || "Analyze the attached evidence and summarize the key findings, likely causes, and supporting details.";
      const result = await api("/investigate", { method: "POST", body: JSON.stringify({ incident, question }) });
      const record = { investigation_id: result.investigation_id, incident, question, investigation_result: result.investigation_result, confidence_score: result.confidence_score };
      setChatMessages((current) => [...current, { role: "assistant", report: result, record }]);
    } catch (error) {
      setChatMessages((current) => [...current, { role: "assistant", error: error.message }]);
    } finally {
      setBusy(false);
    }
  }

  async function exportReport(id) {
    try {
      const response = await fetch(`/investigations/${id}/export`);
      if (!response.ok) { const error = await response.json(); throw new Error(error.detail || "Export failed."); }
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `investigation-${id}.md`; anchor.click(); URL.revokeObjectURL(url);
    } catch (error) { setNotice(error.message); }
  }

  return <>
    <header className="chat-topbar">
      <a className="brand" href="#top"><span className="brand-mark">II</span><span>Incident Investigator</span></a>
      <div className={"health " + (health?.ready ? "ready" : "degraded")}><span className="health-dot" />{health?.ready ? "Ready" : "Check setup"}</div>
    </header>
    <main id="top" className="chat-app">
      <section className="chat-thread" aria-live="polite">
        {!chatMessages.length && <div className="chat-welcome"><span className="eyebrow">Incident response</span><h1>What happened?</h1><p>Describe the incident, attach logs or evidence files, and I’ll investigate.</p></div>}
        {chatMessages.map((item, index) => <article className={"chat-message " + item.role} key={index}>
          {item.role === "user" ? <div className="user-bubble">
            {item.content && <p>{item.content}</p>}
            {item.files?.length > 0 && <div className="message-files">{item.files.map((file) => <span className="message-file" key={file.name}>▤ {file.name}</span>)}</div>}
          </div> : item.error ? <div className="assistant-error" role="alert">{item.error}</div> :
            <div className="assistant-response"><ReportView report={item.report} record={item.record} onExport={exportReport} /></div>}
        </article>)}
        {busy && <div className="chat-message assistant"><div className="typing-indicator" role="status">Reviewing the incident and evidence…</div></div>}
        <div ref={chatEndRef} />
      </section>
      {notice && <div className="chat-notice" role="status">{notice}<button aria-label="Dismiss message" onClick={() => setNotice("")}>×</button></div>}
      <form className="chat-composer" onSubmit={submitChat}>
        {attachments.length > 0 && <div className="attachment-list">{attachments.map((file, index) => <span className="attachment-chip" key={file.name + "-" + index}><span>▤ {file.name}</span><button type="button" aria-label={"Remove " + file.name} onClick={() => setAttachments((current) => current.filter((_, fileIndex) => fileIndex !== index))}>×</button></span>)}</div>}
        <textarea aria-label="Message" rows={2} maxLength={2000} disabled={busy} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Message Incident Investigator…" />
        <div className="composer-actions">
          <label className="attach-button" title="Attach log, text, JSON, or JSONL files">＋<span>Add files</span><input type="file" accept=".json,.jsonl,.log,.txt,application/json,application/x-ndjson,text/plain" multiple disabled={busy} onChange={chooseFiles} /></label>
          <span className="composer-hint">Logs, text, JSON, JSONL · up to 1 MB per file</span>
          <button className="send-button" aria-label="Send message" disabled={busy || (!draft.trim() && !attachments.length)}>{busy ? "…" : "↑"}</button>
        </div>
      </form>
      <p className="chat-disclaimer">AI-generated analysis can be wrong. Check the cited evidence before relying on a conclusion.</p>
    </main>
  </>;
}
