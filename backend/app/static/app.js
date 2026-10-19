const reportContainer = document.querySelector("#report");
const form = document.querySelector("#investigation-form");
const formMessage = document.querySelector("#form-message");
const submitButton = document.querySelector("#submit-button");
const historyList = document.querySelector("#history-list");

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
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
    details.append(element("summary", "", `All retrieved evidence (${evidence.length})`));
    evidence.forEach((item) => {
      const block = element("div", "evidence-item");
      const heading = element("strong", "", `Evidence ${item.evidence_id} · ${item.metadata?.source_type || "source"}`);
      block.append(heading, document.createElement("br"));
      block.append(element("span", "", item.content));
      details.append(block);
    });
    reportContainer.append(details);
  }
}

async function loadHistory() {
  historyList.replaceChildren(element("p", "muted", "Loading saved reports…"));
  try {
    const reports = await requestJson("/investigations?limit=20");
    historyList.replaceChildren();
    if (!reports.length) {
      historyList.append(element("p", "muted", "No saved investigations yet."));
      return;
    }
    reports.forEach((item) => {
      const button = element("button", "history-row");
      button.type = "button";
      button.append(element("strong", "", item.incident || `Investigation #${item.investigation_id}`));
      button.append(element("span", "", `${item.question} · ${item.created_at ? new Date(item.created_at).toLocaleString() : "date unavailable"}`));
      button.append(element("span", "history-confidence", `${Math.round(Number(item.confidence_score || 0) * 100)}%`));
      button.addEventListener("click", () => openSavedReport(item.investigation_id));
      historyList.append(button);
    });
  } catch (error) {
    historyList.replaceChildren(element("p", "muted", `Could not load saved reports: ${error.message}`));
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
