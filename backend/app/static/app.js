const reportContainer = document.querySelector("#report");
const form = document.querySelector("#investigation-form");
const formMessage = document.querySelector("#form-message");
const submitButton = document.querySelector("#submit-button");
const historyList = document.querySelector("#history-list");
let accessToken = "";
let currentUserRole = "";

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

  if (identifiers.investigation_id) {
    const feedback = element("section", "report-section feedback-section");
    feedback.append(element("h3", "", "Was this report useful?"));
    const feedbackStatus = element("p", "muted", "Loading feedback…");
    const actions = element("div", "feedback-actions");
    const comment = document.createElement("textarea");
    comment.maxLength = 2000;
    comment.placeholder = "What should be improved? (optional)";
    comment.setAttribute("aria-label", "Feedback comment");
    const correctionTarget = document.createElement("input");
    correctionTarget.maxLength = 500;
    correctionTarget.placeholder = "Incorrect finding or citation (optional)";
    correctionTarget.setAttribute("aria-label", "Incorrect finding or citation");
    const correctedCause = document.createElement("textarea");
    correctedCause.maxLength = 2000;
    correctedCause.placeholder = "What is the corrected cause? (pair with the finding above)";
    correctedCause.setAttribute("aria-label", "Corrected cause");
    const buttons = [
      ["helpful", "Helpful"],
      ["incorrect", "Incorrect"],
    ];
    buttons.forEach(([rating, label]) => {
      const button = element("button", "secondary-button", label);
      button.type = "button";
      button.disabled = currentUserRole === "viewer";
      button.addEventListener("click", async () => {
        feedbackStatus.textContent = "Saving feedback…";
        try {
          await requestJson(`/investigations/${identifiers.investigation_id}/feedback`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              rating,
              comment: comment.value,
              correction_target: rating === "incorrect" ? correctionTarget.value : null,
              corrected_cause: rating === "incorrect" ? correctedCause.value : null,
            }),
          });
          feedbackStatus.textContent = `Your rating: ${rating}.`;
          await loadFeedbackSummary(identifiers.investigation_id, feedbackStatus);
        } catch (error) {
          feedbackStatus.textContent = `Could not save feedback: ${error.message}`;
        }
      });
      actions.append(button);
    });
    feedback.append(actions, comment, correctionTarget, correctedCause, feedbackStatus);
    reportContainer.append(feedback);
    loadFeedbackSummary(identifiers.investigation_id, feedbackStatus, comment, correctionTarget, correctedCause);
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

async function loadFeedbackSummary(id, target, commentInput = null, correctionTarget = null, correctedCause = null) {
  try {
    const summary = await requestJson(`/investigations/${id}/feedback`);
    const own = summary.my_feedback ? ` Your rating: ${summary.my_feedback.rating}.` : "";
    if (commentInput && summary.my_feedback) {
      commentInput.value = summary.my_feedback.comment || "";
      if (correctionTarget) correctionTarget.value = summary.my_feedback.correction_target || "";
      if (correctedCause) correctedCause.value = summary.my_feedback.corrected_cause || "";
    }
    target.textContent = `Team feedback: ${summary.helpful} helpful, ${summary.incorrect} incorrect.${own}`;
  } catch (error) {
    target.textContent = `Feedback unavailable: ${error.message}`;
  }
}

async function loadHistory() {
  historyList.replaceChildren(element("p", "muted", "Loading saved reports…"));
  try {
    const params = new URLSearchParams({ limit: "20" });
    const query = document.querySelector("#history-query").value.trim();
    const service = document.querySelector("#history-service").value.trim();
    const assignee = document.querySelector("#history-assignee").value.trim();
    const minConfidence = document.querySelector("#history-min-confidence").value;
    const status = document.querySelector("#history-status").value;
    const createdAfter = document.querySelector("#history-after").value;
    const createdBefore = document.querySelector("#history-before").value;
    if (query) params.set("q", query);
    if (service) params.set("service", service);
    if (assignee) params.set("assignee", assignee);
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
      statusSelect.disabled = currentUserRole === "viewer";
      statusSelect.addEventListener("change", () => updateReportStatus(item.investigation_id, statusSelect));
      const exportButton = element("button", "quiet-button", "Export Markdown");
      exportButton.type = "button";
      exportButton.addEventListener("click", () => downloadReport(item.investigation_id, exportButton));
      actions.append(
        element("span", "history-confidence", `${Math.round(Number(item.confidence_score || 0) * 100)}%`),
        statusSelect,
        exportButton,
      );
      let assignForm = null;
      if (currentUserRole !== "viewer") {
        assignForm = element("form", "assignee-form");
        const assigneeInput = element("input", "", "");
        assigneeInput.value = item.assignee || "";
        assigneeInput.maxLength = 254;
        assigneeInput.type = "email";
        assigneeInput.placeholder = "Teammate account email (blank to unassign)";
        assigneeInput.setAttribute("aria-label", `Assignee for investigation ${item.investigation_id}`);
        const assignButton = element("button", "quiet-button", "Save assignee");
        assignButton.type = "submit";
        assignForm.append(assigneeInput, assignButton);
        assignForm.addEventListener("submit", (event) => {
          event.preventDefault();
          updateAssignee(item.investigation_id, assigneeInput, assignButton);
        });
      }
      const audit = element("details", "history-audit");
      const auditSummary = element("summary", "", "Status history");
      const auditEvents = element("div", "history-audit-events");
      audit.append(auditSummary, auditEvents);
      audit.addEventListener("toggle", () => {
        if (audit.open && audit.dataset.loaded !== "true") {
          loadStatusHistory(item.investigation_id, auditEvents, audit);
        }
      });
      const collaboration = element("details", "history-collaboration");
      const collaborationSummary = element("summary", "", "Comments and activity");
      const collaborationBody = element("div", "collaboration-body");
      collaboration.append(collaborationSummary, collaborationBody);
      collaboration.addEventListener("toggle", () => {
        if (collaboration.open && collaboration.dataset.loaded !== "true") {
          loadCollaboration(item.investigation_id, collaborationBody, collaboration);
        }
      });
      row.append(openButton, actions);
      if (assignForm) row.append(assignForm);
      row.append(audit, collaboration);
      historyList.append(row);
    });
  } catch (error) {
    historyList.replaceChildren(element("p", "muted", `Could not load saved reports: ${error.message}`));
  }
}

async function loadEvaluationHistory(refreshCorrections = false) {
  const container = document.querySelector("#evaluation-history");
  container.replaceChildren(element("p", "muted", "Loading evaluation runs…"));
  if (currentUserRole === "viewer") document.querySelector("#correction-review").hidden = true;
  else if (refreshCorrections) await loadCorrectionQueue();
  try {
    const runs = await requestJson("/evaluations/runs?limit=20");
    container.replaceChildren();
    if (!runs.length) {
      container.append(element("p", "muted", "No evaluation runs recorded yet. Run `python -m app.scripts.evaluate_known_incidents` from backend."));
      return;
    }
    runs.forEach((run, index) => {
      const card = element("article", "evaluation-run");
      const older = runs[index + 1];
      const title = element("div", "evaluation-run-title");
      title.append(element("strong", "", `Run #${run.id} · dataset v${run.dataset_version}`));
      const runState = run.status === "running" || run.status === "queued"
        ? `${run.status} · ${run.completed_cases}/${run.case_count}${run.current_case ? ` · ${run.current_case}` : ""}`
        : run.status === "failed" ? `Failed · ${run.error || "see run details"}` : `${run.created_at ? new Date(run.created_at).toLocaleString() : "date unavailable"} · ${run.initiated_by}`;
      title.append(element("span", `muted ${run.status === "failed" ? "case-failed" : ""}`, runState));
      card.append(title);
      if (run.status !== "completed") {
        if (run.status === "running" || run.status === "queued") {
          const progressBar = element("div", "evaluation-progress-bar");
          const progressFill = element("span", "");
          progressFill.style.width = `${run.case_count ? Math.round(run.completed_cases / run.case_count * 100) : 0}%`;
          progressBar.append(progressFill);
          card.append(progressBar);
        }
        container.append(card);
        return;
      }
      const metrics = element("div", "evaluation-metrics");
      [
        ["Pass rate", run.pass_rate],
        ["Citation rate", run.citation_rate],
        ["Validation rate", run.validation_rate],
        ["Mean confidence", run.mean_confidence],
      ].forEach(([label, value]) => {
        const metric = element("div", "evaluation-metric");
        const line = element("div", "evaluation-metric-line");
        const previous = older ? Number(older[label === "Pass rate" ? "pass_rate" : label === "Citation rate" ? "citation_rate" : label === "Validation rate" ? "validation_rate" : "mean_confidence"]) : null;
        const delta = previous === null ? "" : ` · ${Number(value) - previous >= 0 ? "+" : ""}${Math.round((Number(value) - previous) * 100)} pp`;
        line.append(element("span", "", label), element("strong", "", `${Math.round(Number(value) * 100)}%${delta}`));
        metric.append(line);
        const bar = element("div", "evaluation-bar");
        const fill = element("span", "");
        fill.style.width = `${Math.max(0, Math.min(100, Number(value) * 100))}%`;
        bar.append(fill);
        metric.append(bar);
        metrics.append(metric);
      });
      card.append(metrics, element("p", "muted evaluation-case-count", `${run.passed_count}/${run.case_count} cases passed`));
      const snapshot = element("details", "evaluation-cases");
      snapshot.append(element("summary", "", `Dataset v${run.dataset_version} snapshot`));
      const snapshotBody = element("div", "evaluation-snapshot");
      snapshot.append(snapshotBody);
      snapshot.addEventListener("toggle", async () => {
        if (!snapshot.open || snapshot.dataset.loaded === "true") return;
        snapshotBody.append(element("p", "muted", "Loading versioned cases…"));
        try {
          const data = await requestJson(`/evaluations/case-sets/${run.dataset_version}`);
          snapshotBody.replaceChildren(element("p", "muted", `${data.change_summary} · created by ${data.created_by}`));
          data.cases.forEach((testCase) => {
            const item = element("article", "snapshot-case");
            item.append(element("strong", "", testCase.id));
            if (testCase.correction_target) item.append(element("p", "", `Disputed finding: ${testCase.correction_target}`));
            item.append(element("p", "", `Incident: ${testCase.incident}`));
            item.append(element("p", "", `Question: ${testCase.question}`));
            item.append(element("p", "muted", `Expected terms: ${(testCase.expected_terms || []).join(", ")}`));
            snapshotBody.append(item);
          });
          snapshot.dataset.loaded = "true";
        } catch (error) {
          snapshotBody.replaceChildren(element("p", "muted", `Could not load dataset snapshot: ${error.message}`));
        }
      });
      card.append(snapshot);
      const details = element("details", "evaluation-cases");
      details.append(element("summary", "", "Case results"));
      const list = element("ul", "evaluation-case-list");
      (run.results || []).forEach((result) => {
        const item = element("li", result.passed ? "case-passed" : "case-failed");
        const terms = result.expected_terms_found?.length ? result.expected_terms_found.join(", ") : "no expected terms found";
        item.textContent = `${result.passed ? "Passed" : "Failed"} · ${result.id} · ${result.citation_count} citations · ${terms}`;
        list.append(item);
      });
      details.append(list);
      card.append(details);
      container.append(card);
    });
  } catch (error) {
    container.replaceChildren(element("p", "muted", `Could not load evaluation history: ${error.message}`));
  }
}

async function loadCorrectionQueue() {
  const container = document.querySelector("#correction-queue");
  if (currentUserRole === "viewer") {
    document.querySelector("#correction-review").hidden = true;
    return;
  }
  document.querySelector("#correction-review").hidden = false;
  container.replaceChildren(element("p", "muted", "Loading corrections…"));
  try {
    const corrections = await requestJson("/evaluations/corrections");
    container.replaceChildren();
    if (!corrections.length) {
      container.append(element("p", "muted", "No analyst corrections to review yet."));
      return;
    }
    corrections.forEach((correction) => {
      const card = element("article", "correction-card");
      card.append(element("strong", "", `Investigation #${correction.investigation_id}`));
      card.append(element("p", "muted", correction.incident));
      card.append(element("p", "", `Evaluation question: ${correction.question}`));
      card.append(element("p", "", `Disputed: ${correction.correction_target}`));
      card.append(element("p", "", `Proposed cause: ${correction.corrected_cause}`));
      if (correction.comment) card.append(element("p", "muted", `Analyst note: ${correction.comment}`));
      const button = element("button", "quiet-button", correction.approved ? "Included in current set" : "Approve as evaluation case");
      button.type = "button";
      button.disabled = correction.approved;
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Adding…";
        try {
          const result = await requestJson(`/evaluations/corrections/${correction.feedback_id}/approve`, { method: "POST" });
          document.querySelector("#evaluation-progress").textContent = `Added to evaluation dataset v${result.dataset_version} (${result.case_count} cases).`;
          await loadEvaluationHistory(true);
        } catch (error) {
          button.disabled = false;
          button.textContent = `Could not add: ${error.message}`;
        }
      });
      card.append(button);
      container.append(card);
    });
  } catch (error) {
    container.replaceChildren(element("p", "muted", `Could not load corrections: ${error.message}`));
  }
}

async function startEvaluation() {
  const button = document.querySelector("#run-evaluation");
  const progress = document.querySelector("#evaluation-progress");
  button.disabled = true;
  button.textContent = "Starting…";
  try {
    const started = await requestJson("/evaluations/runs", { method: "POST" });
    progress.textContent = `Evaluation run #${started.run_id} queued for dataset v${started.dataset_version}.`;
    await loadEvaluationHistory(true);
    for (let attempt = 0; attempt < 900; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const run = await requestJson(`/evaluations/runs/${started.run_id}`);
      if (run.status === "completed") {
        progress.textContent = `Run #${run.id} completed: ${run.passed_count}/${run.case_count} cases passed.`;
        await loadEvaluationHistory();
        return;
      }
      if (run.status === "failed") throw new Error(run.error || "Evaluation failed.");
      progress.textContent = `${run.status === "queued" ? "Waiting to start" : `Running ${run.current_case || "case"}`} · ${run.completed_cases}/${run.case_count} cases complete.`;
      await loadEvaluationHistory();
    }
    progress.textContent = `Run #${started.run_id} is still running. Use Refresh to check its progress.`;
  } catch (error) {
    progress.textContent = `Evaluation could not complete: ${error.message}`;
    await loadEvaluationHistory();
  } finally {
    button.disabled = false;
    button.textContent = "Run evaluation";
  }
}

async function updateAssignee(id, input, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    await requestJson(`/investigations/${id}/assignee`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assigned_to: input.value.trim() || null }),
    });
    await loadHistory();
    loadNotifications();
  } catch (error) {
    formMessage.textContent = `Could not save assignee: ${error.message}`;
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function loadCollaboration(id, container, details) {
  container.replaceChildren(element("p", "muted", "Loading comments and activity…"));
  try {
    const [comments, activities] = await Promise.all([
      requestJson(`/investigations/${id}/comments`),
      requestJson(`/investigations/${id}/activity`),
    ]);
    container.replaceChildren();
    const commentList = element("div", "comment-list");
    if (!comments.length) commentList.append(element("p", "muted", "No comments yet."));
    comments.forEach((comment) => {
      const card = element("article", "comment-card");
      const time = comment.created_at ? new Date(comment.created_at).toLocaleString() : "time unavailable";
      card.append(element("strong", "", `${comment.author} · ${time}`), element("p", "", comment.body));
      commentList.append(card);
    });
    container.append(element("h3", "", "Comments"), commentList);

    if (currentUserRole !== "viewer") {
      const formNode = element("form", "comment-form");
      const body = element("textarea", "", "");
      body.placeholder = "Add a handoff note or comment";
      body.maxLength = 5000;
      body.required = true;
      const submit = element("button", "quiet-button", "Add comment");
      submit.type = "submit";
      formNode.append(body, submit);
      formNode.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      try {
        await requestJson(`/investigations/${id}/comments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: body.value.trim() }),
        });
        details.dataset.loaded = "false";
        loadCollaboration(id, container, details);
        loadNotifications();
      } catch (error) {
        formMessage.textContent = `Could not add comment: ${error.message}`;
        submit.disabled = false;
      }
      });
      container.append(formNode);
    }

    container.append(element("h3", "", "Activity"));
    const activityList = element("ul", "activity-list");
    if (!activities.length) activityList.append(element("li", "muted", "No collaboration activity yet."));
    activities.forEach((activity) => {
      const when = activity.created_at ? new Date(activity.created_at).toLocaleString() : "time unavailable";
      const actor = activity.actor ? `${activity.actor} · ` : "";
      activityList.append(element("li", "", `${actor}${activity.details} · ${when}`));
    });
    container.append(activityList);
    details.dataset.loaded = "true";
  } catch (error) {
    container.replaceChildren(element("p", "muted", `Could not load collaboration details: ${error.message}`));
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
      const actor = event.changed_by ? `${event.changed_by} · ` : "";
      const entry = element("li", "", `${actor}${event.previous_status} → ${event.new_status} · ${changedAt}`);
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
    loadNotifications();
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

async function loadNotifications() {
  const list = document.querySelector("#notification-list");
  list.replaceChildren(element("p", "muted", "Loading notifications…"));
  try {
    const result = await requestJson("/notifications?limit=30");
    const count = Number(result.unread_count || 0);
    document.querySelector("#notification-count").textContent = `${count} unread`;
    list.replaceChildren();
    if (!result.items.length) {
      list.append(element("p", "muted", "No notifications yet."));
      return;
    }
    result.items.forEach((item) => {
      const row = element("article", `notification-item${item.is_read ? " read" : " unread"}`);
      const message = element("button", "notification-message", item.message);
      message.type = "button";
      message.addEventListener("click", () => openSavedReport(item.investigation_id));
      const time = item.created_at ? new Date(item.created_at).toLocaleString() : "time unavailable";
      row.append(message, element("span", "muted", time));
      if (!item.is_read) {
        const readButton = element("button", "quiet-button", "Mark read");
        readButton.type = "button";
        readButton.addEventListener("click", async () => {
          readButton.disabled = true;
          try {
            await requestJson(`/notifications/${item.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ is_read: true }),
            });
            await loadNotifications();
          } catch (error) {
            formMessage.textContent = `Could not mark notification as read: ${error.message}`;
            readButton.disabled = false;
          }
        });
        row.append(readButton);
      }
      list.append(row);
    });
  } catch (error) {
    list.replaceChildren(element("p", "muted", `Could not load notifications: ${error.message}`));
  }
}

async function loadTeamAccounts() {
  const list = document.querySelector("#team-list");
  list.replaceChildren(element("p", "muted", "Loading accounts…"));
  try {
    const users = await requestJson("/users");
    list.replaceChildren();
    users.forEach((user) => {
      const row = element("div", "team-account");
      row.append(element("span", "", user.email));
      const role = element("select", "", "");
      [["admin", "Admin"], ["analyst", "Analyst"], ["viewer", "Viewer"]].forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        role.append(option);
      });
      role.value = user.role;
      role.addEventListener("change", () => updateTeamAccount(user.id, { role: role.value }));
      const activeLabel = element("label", "team-active");
      const active = document.createElement("input");
      active.type = "checkbox";
      active.checked = user.is_active;
      active.setAttribute("aria-label", `Active account ${user.email}`);
      active.addEventListener("change", () => updateTeamAccount(user.id, { is_active: active.checked }));
      activeLabel.append(active, element("span", "", user.is_active ? "Active" : "Disabled"));
      row.append(role, activeLabel);
      list.append(row);
    });
  } catch (error) {
    list.replaceChildren(element("p", "muted", `Could not load accounts: ${error.message}`));
  }
}

async function updateTeamAccount(id, changes) {
  const message = document.querySelector("#team-message");
  message.textContent = "Saving account changes…";
  try {
    await requestJson(`/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    message.textContent = "Account updated.";
    await loadTeamAccounts();
  } catch (error) {
    message.textContent = error.message;
    await loadTeamAccounts();
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
    await loadNotifications();
  } catch (error) {
    formMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span:first-child").textContent = "Run investigation";
  }
});

document.querySelector("#refresh-history").addEventListener("click", loadHistory);
document.querySelector("#refresh-evaluations").addEventListener("click", loadEvaluationHistory);
document.querySelector("#run-evaluation").addEventListener("click", startEvaluation);
document.querySelector("#history-filters").addEventListener("submit", (event) => {
  event.preventDefault();
  loadHistory();
});
document.querySelector("#notification-panel").addEventListener("toggle", (event) => {
  if (event.currentTarget.open) loadNotifications();
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
  const emailInput = document.querySelector("#account-email");
  const passwordInput = document.querySelector("#account-password");
  const authStatus = document.querySelector("#auth-status");
  const email = emailInput.value.trim();
  const password = passwordInput.value;
  if (!email || !password) {
    authStatus.textContent = "Enter email and password";
    return;
  }
  try {
    const login = await requestJson("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    accessToken = login.access_token;
    currentUserRole = login.user.role;
    document.querySelector("#team-panel").hidden = currentUserRole !== "admin";
    document.querySelector("#evaluation-panel").hidden = false;
    document.querySelector("#run-evaluation").hidden = currentUserRole === "viewer";
    document.querySelector("#signout-button").hidden = false;
    passwordInput.value = "";
    authStatus.textContent = `${login.user.email} · ${login.user.role}`;
    authStatus.className = "auth-status connected";
    await loadHistory();
    await loadEvaluationHistory(true);
    await loadNotifications();
    if (currentUserRole === "admin") await loadTeamAccounts();
  } catch (error) {
    accessToken = "";
    currentUserRole = "";
    document.querySelector("#team-panel").hidden = true;
    document.querySelector("#evaluation-panel").hidden = true;
    document.querySelector("#signout-button").hidden = true;
    document.querySelector("#team-list").replaceChildren();
    historyList.replaceChildren(element("p", "muted", "Sign in to view saved reports."));
    document.querySelector("#notification-list").replaceChildren();
    document.querySelector("#notification-count").textContent = "0 unread";
    reportContainer.replaceChildren(element("p", "muted", "Sign in to open saved reports."));
    authStatus.textContent = error.message;
    authStatus.className = "auth-status error";
  }
});

document.querySelector("#team-create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#team-message");
  try {
    await requestJson("/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.querySelector("#team-email").value.trim(),
        password: document.querySelector("#team-password").value,
        role: document.querySelector("#team-role").value,
      }),
    });
    document.querySelector("#team-password").value = "";
    message.textContent = "Account created.";
    await loadTeamAccounts();
    await loadHistory();
  } catch (error) {
    message.textContent = error.message;
  }
});

document.querySelector("#signout-button").addEventListener("click", () => {
  accessToken = "";
  currentUserRole = "";
  document.querySelector("#team-panel").hidden = true;
  document.querySelector("#evaluation-panel").hidden = true;
  document.querySelector("#signout-button").hidden = true;
  document.querySelector("#auth-status").textContent = "Signed out";
  document.querySelector("#auth-status").className = "auth-status";
  historyList.replaceChildren(element("p", "muted", "Sign in to view saved reports."));
  document.querySelector("#notification-list").replaceChildren();
  document.querySelector("#notification-count").textContent = "0 unread";
  document.querySelector("#team-list").replaceChildren();
  reportContainer.replaceChildren(element("p", "muted", "Sign in to open saved reports."));
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
