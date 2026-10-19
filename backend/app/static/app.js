const reportContainer = document.querySelector("#report");
const form = document.querySelector("#investigation-form");
const formMessage = document.querySelector("#form-message");
const submitButton = document.querySelector("#submit-button");
const historyList = document.querySelector("#history-list");
let accessToken = "";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

async function requestJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status})`);
  }
  return data;
}

function renderReport(report, identifiers = {}) {
  reportContainer.replaceChildren();
  reportContainer.className = "report-body";

  const meta = element("div", "report-meta");
  if (identifiers.investigation_id) {
    meta.append(element("span", "badge", `Report #${identifiers.investigation_id}`));
  }
  const confidence = Number(report.confidence_score || 0);
  meta.append(element("span", `badge ${confidence >= 0.7 ? "good" : "warn"}`, `${Math.round(confidence * 100)}% confidence`));
  meta.append(element("span", `badge ${report.validation?.is_valid ? "good" : "warn"}`, report.validation?.is_valid ? "Evidence supported" : "Needs review"));
  reportContainer.append(meta);

  reportContainer.append(element("div", "result-summary", report.investigation_result || "No investigation result was returned."));

  const validationSection = element("section", "report-section");
  validationSection.append(element("h3", "", "Validation"));
  validationSection.append(element("p", "", report.validation?.reason || "No validation details."));
  reportContainer.append(validationSection);

  const timelineSection = element("section", "report-section");
  timelineSection.append(element("h3", "", "Evidence timeline"));
  const timeline = report.timeline || [];
  if (timeline.length === 0) {
    timelineSection.append(element("p", "muted", "No timestamped evidence was retrieved."));
  } else {
    const timelineList = element("ol", "timeline-list");
    timeline.forEach((event) => {
      const item = element("li", "timeline-item");
      const marker = element("span", "timeline-marker");
      const body = element("div", "timeline-content");
      const metaLine = element("div", "timeline-meta");
      metaLine.append(element("time", "", new Date(event.timestamp).toLocaleString()));
      const source = [event.service, event.source_type].filter(Boolean).join(" · ");
      if (source) metaLine.append(element("span", "", source));
      body.append(metaLine, element("p", "", event.summary));
      const evidenceButton = element("button", "timeline-evidence", `Open E${event.evidence_id}`);
      evidenceButton.type = "button";
      evidenceButton.dataset.evidenceId = event.evidence_id;
      body.append(evidenceButton);
      item.append(marker, body);
      timelineList.append(item);
    });
    timelineSection.append(timelineList);
  }
  reportContainer.append(timelineSection);

  const citationsSection = element("section", "report-section");
  citationsSection.append(element("h3", "", "Citations"));
  const citations = report.citations || [];
  if (citations.length === 0) {
    citationsSection.append(element("p", "muted", "No evidence citations were returned."));
  }
  citations.forEach((citation) => {
    const card = element("article", "citation-card");
    const head = element("div", "citation-head");
    head.append(element("span", "", `[${citation.citation_id || `Evidence ${citation.evidence_id}`}]`));
    const sourceBits = [citation.source_type, citation.service, citation.source_id || citation.source_path].filter(Boolean);
    head.append(element("span", "citation-source", sourceBits.join(" · ") || "Source details unavailable"));
    card.append(head);
    if (citation.timestamp) card.append(element("p", "muted", `Timestamp: ${citation.timestamp}`));
    card.append(element("p", "", citation.excerpt || "Open the matching evidence item below."));
    citationsSection.append(card);
  });
  if (report.citation_warnings?.length) {
    const warnings = element("ul", "warning-list");
    report.citation_warnings.forEach((warning) => warnings.append(element("li", "", warning)));
    citationsSection.append(warnings);
  }
  reportContainer.append(citationsSection);

  if (report.filters && Object.values(report.filters).some(Boolean)) {
    const applied = Object.entries(report.filters).filter(([, value]) => value).map(([key, value]) => `${key}: ${value}`);
    const filtersSection = element("section", "report-section");
    filtersSection.append(element("h3", "", "Evidence filters"));
    filtersSection.append(element("p", "muted", applied.join(" · ")));
    reportContainer.append(filtersSection);
  }

  const evidence = report.evidence || [];
  if (evidence.length) {
    const details = element("details", "evidence-details");
    details.id = "all-evidence";
    details.append(element("summary", "", `All retrieved evidence (${evidence.length})`));
    evidence.forEach((item) => {
      const block = element("div", "evidence-item");
      block.id = `evidence-${item.evidence_id}`;
      const heading = element("strong", "", `Evidence ${item.evidence_id} · ${item.metadata?.source_type || "source"}`);
      block.append(heading, document.createElement("br"));
      block.append(element("span", "", item.content));
      details.append(block);
    });
    reportContainer.append(details);
  }

  reportContainer.querySelectorAll(".timeline-evidence").forEach((button) => {
    button.addEventListener("click", () => {
      const details = reportContainer.querySelector("#all-evidence");
      const target = reportContainer.querySelector(`#evidence-${button.dataset.evidenceId}`);
      if (details && target) {
        details.open = true;
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });
}

async function loadHistory() {
  historyList.replaceChildren(element("p", "muted", "Loading saved reports…"));
  try {
    const params = new URLSearchParams({ limit: "20" });
    const query = document.querySelector("#history-query").value.trim();
    const service = document.querySelector("#history-service").value.trim();
    const minConfidence = document.querySelector("#history-min-confidence").value;
    const status = document.querySelector("#history-status").value;
    const createdAfter = document.querySelector("#history-after").value;
    const createdBefore = document.querySelector("#history-before").value;
    if (query) params.set("q", query);
    if (service) params.set("service", service);
    if (minConfidence) params.set("min_confidence", minConfidence);
    if (status) params.set("status", status);
    if (createdAfter) params.set("created_after", new Date(createdAfter).toISOString());
    if (createdBefore) params.set("created_before", new Date(createdBefore).toISOString());
    const reports = await requestJson(`/investigations?${params.toString()}`);
    historyList.replaceChildren();
    if (!reports.length) {
      historyList.append(element("p", "muted", "No saved investigations yet."));
      return;
    }
    reports.forEach((item) => {
      const row = element("article", "history-row");
      const openButton = element("button", "history-open");
      openButton.type = "button";
      openButton.append(element("strong", "", item.incident || `Investigation #${item.investigation_id}`));
      openButton.append(element("span", "", `${item.question} · ${item.created_at ? new Date(item.created_at).toLocaleString() : "date unavailable"}`));
      openButton.addEventListener("click", () => openSavedReport(item.investigation_id));
      const actions = element("div", "history-actions");
      const statusSelect = element("select", "history-status-select");
      statusSelect.setAttribute("aria-label", `Status for investigation ${item.investigation_id}`);
      [["open", "Open"], ["investigating", "Investigating"], ["resolved", "Resolved"]].forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        statusSelect.append(option);
      });
      statusSelect.value = item.status || "open";
      statusSelect.addEventListener("change", () => updateReportStatus(item.investigation_id, statusSelect));
      const exportButton = element("button", "quiet-button", "Export Markdown");
      exportButton.type = "button";
      exportButton.addEventListener("click", () => downloadReport(item.investigation_id, exportButton));
      actions.append(
        element("span", "history-confidence", `${Math.round(Number(item.confidence_score || 0) * 100)}%`),
        statusSelect,
        exportButton,
      );
      const audit = element("details", "history-audit");
      const auditSummary = element("summary", "", "Status history");
      const auditEvents = element("div", "history-audit-events");
      audit.append(auditSummary, auditEvents);
      audit.addEventListener("toggle", () => {
        if (audit.open && audit.dataset.loaded !== "true") {
          loadStatusHistory(item.investigation_id, auditEvents, audit);
        }
      });
      row.append(openButton, actions, audit);
      historyList.append(row);
    });
  } catch (error) {
    historyList.replaceChildren(element("p", "muted", `Could not load saved reports: ${error.message}`));
  }
}

async function loadStatusHistory(id, container, details) {
  container.replaceChildren(element("p", "muted", "Loading status history…"));
  try {
    const events = await requestJson(`/investigations/${id}/status-history`);
    container.replaceChildren();
    if (!events.length) {
      container.append(element("p", "muted", "No status changes recorded yet."));
    } else {
      const list = element("ul", "history-audit-list");
      events.forEach((event) => {
        const changedAt = event.changed_at ? new Date(event.changed_at).toLocaleString() : "time unavailable";
        const entry = element("li", "", `${event.previous_status} → ${event.new_status} · ${changedAt}`);
        list.append(entry);
      });
      container.append(list);
    }
    details.dataset.loaded = "true";
  } catch (error) {
    container.replaceChildren(element("p", "muted", `Could not load status history: ${error.message}`));
  }
}

async function updateReportStatus(id, select) {
  select.disabled = true;
  try {
    await requestJson(`/investigations/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: select.value }),
    });
    await loadHistory();
  } catch (error) {
    formMessage.textContent = `Could not update status: ${error.message}`;
    select.disabled = false;
  }
}

async function downloadReport(id, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Preparing…";
  try {
    const headers = new Headers();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    const response = await fetch(`/investigations/${id}/export`, { headers });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || `Request failed (${response.status})`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `investigation-${id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    formMessage.textContent = `Could not export report: ${error.message}`;
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function openSavedReport(id) {
  reportContainer.replaceChildren(element("p", "muted", "Loading saved report…"));
  try {
    const saved = await requestJson(`/investigations/${id}`);
    renderReport(saved.report || saved, saved);
    document.querySelector("#report-title").textContent = `Investigation #${saved.investigation_id}`;
    document.querySelector(".result-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    reportContainer.replaceChildren(element("p", "", `Could not open report: ${error.message}`));
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "";
  submitButton.disabled = true;
  submitButton.querySelector("span:first-child").textContent = "Investigating…";

  const formData = new FormData(form);
  const payload = {
    incident: formData.get("incident").trim(),
    question: formData.get("question").trim(),
  };
  ["service", "source_type"].forEach((key) => {
    const value = formData.get(key)?.trim();
    if (value) payload[key] = value;
  });
  ["start_time", "end_time"].forEach((key) => {
    const value = formData.get(key);
    if (value) payload[key] = new Date(value).toISOString();
  });

  try {
    const report = await requestJson("/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderReport(report, report);
    document.querySelector("#report-title").textContent = "Investigation complete";
    await loadHistory();
  } catch (error) {
    formMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span:first-child").textContent = "Run investigation";
  }
});

document.querySelector("#refresh-history").addEventListener("click", loadHistory);
document.querySelector("#history-filters").addEventListener("submit", (event) => {
  event.preventDefault();
  loadHistory();
});

document.querySelector("#ingestion-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#ingestion-message");
  const button = document.querySelector("#ingestion-button");
  message.textContent = "";
  button.disabled = true;
  button.querySelector(".ingestion-button-label").textContent = "Indexing…";
  try {
    const records = JSON.parse(document.querySelector("#ingestion-records").value);
    if (!Array.isArray(records)) throw new Error("Enter a JSON array of records.");
    const result = await requestJson("/evidence", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_type: document.querySelector("#ingestion-source-type").value,
        records,
      }),
    });
    message.textContent = `Indexed ${result.record_count} records (${result.inserted} new, ${result.updated} updated).`;
    message.className = "form-message success-message";
    loadHealth();
  } catch (error) {
    message.textContent = error.message;
    message.className = "form-message";
  } finally {
    button.disabled = false;
    button.querySelector(".ingestion-button-label").textContent = "Index records";
  }
});

document.querySelector("#connect-button").addEventListener("click", async () => {
  const tokenInput = document.querySelector("#access-token");
  const authStatus = document.querySelector("#auth-status");
  const candidate = tokenInput.value.trim();
  if (!candidate) {
    authStatus.textContent = "Enter your token";
    return;
  }
  try {
    await requestJson("/auth/check", {
      headers: { Authorization: `Bearer ${candidate}` },
    });
    accessToken = candidate;
    tokenInput.value = "";
    authStatus.textContent = "Connected";
    authStatus.className = "auth-status connected";
    await loadHistory();
  } catch (error) {
    accessToken = "";
    authStatus.textContent = error.message;
    authStatus.className = "auth-status error";
  }
});

async function loadHealth() {
  const health = document.querySelector("#health");
  try {
    const result = await requestJson("/health");
    health.className = `health ${result.ready ? "ready" : "degraded"}`;
    const statuses = Object.entries(result.checks || {}).map(([name, status]) => `${name}: ${status}`);
    health.lastElementChild.textContent = result.ready ? "Services ready" : statuses.join(" · ");
  } catch (error) {
    health.className = "health degraded";
    health.lastElementChild.textContent = `Health check failed: ${error.message}`;
  }
}

loadHealth();
loadHistory();
