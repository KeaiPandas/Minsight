const tabs = document.querySelectorAll(".tab");
const tabPanels = document.querySelectorAll(".tab-panel");

const scenarioSelect = document.getElementById("scenarioSelect");
const plainToggle = document.getElementById("plainToggle");
const runButton = document.getElementById("runButton");
const statusPill = document.getElementById("statusPill");
const runMeta = document.getElementById("runMeta");
const summaryBoard = document.getElementById("summaryBoard");
const runList = document.getElementById("runList");
const caseTable = document.getElementById("caseTable");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");

const demoCaseSelect = document.getElementById("demoCaseSelect");
const loadMockButton = document.getElementById("loadMockButton");
const demoTitleInput = document.getElementById("demoTitleInput");
const demoTranscriptInput = document.getElementById("demoTranscriptInput");
const demoRunButton = document.getElementById("demoRunButton");
const demoStatusPill = document.getElementById("demoStatusPill");
const demoMeta = document.getElementById("demoMeta");
const demoProgressBar = document.getElementById("demoProgressBar");
const demoProgressText = document.getElementById("demoProgressText");
const meetingList = document.getElementById("meetingList");
const comparisonBoard = document.getElementById("comparisonBoard");
const minutesBoard = document.getElementById("minutesBoard");
const tasksBoard = document.getElementById("tasksBoard");
const alertsBoard = document.getElementById("alertsBoard");

let pollTimer = null;
let demoPollTimer = null;
let activeRunId = null;
let activeMeetingId = null;
let demoCases = [];

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function setStatus(element, kind, text) {
  element.className = `status-pill ${kind}`;
  element.textContent = text;
}

function formatScore(score) {
  return (score * 100).toFixed(1) + "%";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function activateTab(name) {
  tabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === `${name}Tab`);
  });
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

function updateProgress(run) {
  const total = run?.total_tasks || 0;
  const completed = run?.completed_tasks || 0;
  const pct = total > 0 ? Math.min(100, (completed / total) * 100) : 0;
  progressBar.style.width = `${pct}%`;
  const phase = run?.phase || "queued";
  const caseId = run?.current_case_id || "-";
  const variant = run?.current_variant || "-";
  progressText.textContent = `${phase} | ${completed}/${total} | ${caseId} | ${variant}`;
}

function updateDemoProgress(meeting) {
  const phase = meeting?.phase || "queued";
  demoProgressBar.style.width = meeting?.status === "completed" ? "100%" : meeting?.status === "running" ? "66%" : "0%";
  demoProgressText.textContent = `${phase} | ${meeting?.source_case_id || meeting?.scenario || "ad_hoc"}`;
}

function renderSummary(summary) {
  const variants = Object.entries(summary || {});
  if (!variants.length) {
    summaryBoard.className = "summary-board empty";
    summaryBoard.textContent = "No benchmark results yet.";
    return;
  }
  summaryBoard.className = "summary-board";
  summaryBoard.innerHTML = `
    <div class="variant-grid">
      ${variants.map(([variant, scores]) => `
        <div class="variant-card">
          <h4>${variant.toUpperCase()}</h4>
          ${[
            ["Participants", scores.participants],
            ["Key Points", scores.key_points],
            ["Actions", scores.action_items],
            ["Decisions", scores.decisions],
            ["Overall", scores.overall],
          ].map(([label, value]) => `
            <div class="metric-row">
              <span>${label}</span>
              <strong>${formatScore(value)}</strong>
            </div>
          `).join("")}
        </div>
      `).join("")}
    </div>
  `;
}

function renderRuns(runs) {
  if (!runs.length) {
    runList.className = "run-list empty";
    runList.textContent = "No previous runs.";
    return;
  }
  runList.className = "run-list";
  runList.innerHTML = runs.map((run) => `
    <div class="history-row ${activeRunId === run.run_id ? "selected" : ""}" data-run-id="${run.run_id}">
      <button class="history-item" data-open-run-id="${run.run_id}">
        <div class="run-id">${run.run_id.slice(0, 8)}</div>
        <div class="meta">
          scenario: ${escapeHtml(run.scenario || "all")} | v2: ${escapeHtml(run.v2_impl)} | ${new Date(run.created_at).toLocaleString()}
        </div>
      </button>
      <button class="history-delete" data-delete-run-id="${run.run_id}" aria-label="Delete run ${run.run_id.slice(0, 8)}">
        Delete
      </button>
    </div>
  `).join("");

  runList.querySelectorAll("[data-open-run-id]").forEach((button) => {
    button.addEventListener("click", () => loadRun(button.dataset.openRunId));
  });

  runList.querySelectorAll("[data-delete-run-id]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      await deleteRun(button.dataset.deleteRunId);
    });
  });
}

function renderCases(data) {
  const cases = data.case_results || [];
  if (!cases.length) {
    caseTable.className = "case-table empty";
    caseTable.textContent = "Run a benchmark to see per-case judge results here.";
    return;
  }
  caseTable.className = "case-table";
  caseTable.innerHTML = cases.map((item) => `
    <article class="case-item">
      <div class="case-top">
        <div>
          <div class="case-variant">dataset</div>
          <div class="case-title">${escapeHtml(item.case_id)} | ${escapeHtml(item.scenario)}</div>
        </div>
      </div>
      <div class="variant-grid detail-grid">
        ${["v1", "v2"].map((variant) => renderVariantDetail(item, variant)).join("")}
      </div>
    </article>
  `).join("");
}

function renderVariantDetail(item, variant) {
  const entry = item.variants?.[variant];
  if (!entry?.judgement) {
    return `
      <section class="variant-card detail-card">
        <h4>${variant.toUpperCase()}</h4>
        <div class="judge-text">No result for this variant.</div>
      </section>
    `;
  }
  const result = entry.judgement;
  return `
    <section class="variant-card detail-card">
      <div class="case-top">
        <div class="case-variant">${variant.toUpperCase()}</div>
        <div>${entry.created_at ? new Date(entry.created_at).toLocaleString() : ""}</div>
      </div>
      ${[
        ["Participants", result.participants],
        ["Key Points", result.key_points],
        ["Actions", result.action_items],
        ["Decisions", result.decisions],
        ["Overall", result.overall],
      ].map(([label, value]) => `
        <div class="metric-row">
          <span>${label}</span>
          <strong>${formatScore(value)}</strong>
        </div>
      `).join("")}
      <div class="judge-text">
        <strong>Summary:</strong> ${escapeHtml(result.summary)}<br/>
        <strong>Strengths:</strong> ${escapeHtml((result.strengths || []).join(", ") || "-")}<br/>
        <strong>Issues:</strong> ${escapeHtml((result.issues || []).join(", ") || "-")}
      </div>
    </section>
  `;
}

function renderMeetingArchive(meetings) {
  if (!meetings.length) {
    meetingList.className = "run-list empty";
    meetingList.textContent = "No workspace runs yet.";
    return;
  }
  meetingList.className = "run-list";
  meetingList.innerHTML = meetings.map((meeting) => `
    <button class="history-item ${activeMeetingId === meeting.meeting_id ? "selected-card" : ""}" data-meeting-id="${meeting.meeting_id}">
      <div class="run-id">${escapeHtml(meeting.title)}</div>
      <div class="meta">
        ${escapeHtml(meeting.scenario || "ad_hoc")} | ${meeting.status} | ${new Date(meeting.created_at).toLocaleString()}
      </div>
    </button>
  `).join("");
  meetingList.querySelectorAll("[data-meeting-id]").forEach((button) => {
    button.addEventListener("click", () => loadMeeting(button.dataset.meetingId));
  });
}

function renderComparison(comparison) {
  if (!comparison) {
    comparisonBoard.className = "summary-board empty";
    comparisonBoard.textContent = "Run a meeting to see why V2 is safer than V1.";
    return;
  }
  comparisonBoard.className = "summary-board";
  comparisonBoard.innerHTML = `
    <div class="variant-grid">
      <section class="variant-card">
        <h4>V1 Baseline</h4>
        <div class="metric-row"><span>Format Valid</span><strong>${comparison.v1_format_valid ? "Yes" : "No"}</strong></div>
        ${Object.entries(comparison.v1_counts || {}).map(([key, value]) => `
          <div class="metric-row"><span>${key.replaceAll("_", " ")}</span><strong>${value}</strong></div>
        `).join("")}
      </section>
      <section class="variant-card">
        <h4>V2 Workflow</h4>
        <div class="metric-row"><span>Format Valid</span><strong>${comparison.v2_format_valid ? "Yes" : "No"}</strong></div>
        ${Object.entries(comparison.v2_counts || {}).map(([key, value]) => `
          <div class="metric-row"><span>${key.replaceAll("_", " ")}</span><strong>${value}</strong></div>
        `).join("")}
      </section>
    </div>
    <div class="judge-text">
      <strong>Why V2 wins:</strong><br/>
      ${(comparison.highlights || []).map((line) => `• ${escapeHtml(line)}`).join("<br/>")}
    </div>
  `;
}

function renderMinutes(minutes) {
  if (!minutes) {
    minutesBoard.className = "case-table empty";
    minutesBoard.textContent = "Your human-readable minutes will appear here.";
    return;
  }
  minutesBoard.className = "case-table";
  minutesBoard.innerHTML = `
    <article class="case-item">
      <div class="case-top">
        <div>
          <div class="case-variant">${escapeHtml(minutes.scenario)}</div>
          <div class="case-title">${escapeHtml(minutes.title)}</div>
        </div>
      </div>
      <div class="judge-text"><strong>Summary:</strong> ${escapeHtml(minutes.summary_line)}</div>
      <div class="minutes-grid">
        ${renderMinutesSection("Participants", (minutes.participants || []).map((item) => `
          <div class="evidence-item"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.role || "role not set")}</span></div>
        `).join(""), "No participants extracted.")}
        ${renderMinutesSection("Key Points", (minutes.key_points || []).map((item) => `
          <div class="evidence-item"><strong>${escapeHtml(item.topic)}</strong><span>${escapeHtml(item.summary || "")}</span></div>
        `).join(""), "No key points extracted.")}
        ${renderMinutesSection("Action Items", (minutes.action_items || []).map((item) => `
          <div class="evidence-item">
            <strong>${escapeHtml(item.task)}</strong>
            <span>Owner: ${escapeHtml(item.owner || "unassigned")} | Due: ${escapeHtml(item.due || "not set")}</span>
            <blockquote>${escapeHtml(item.evidence || "No evidence attached")}</blockquote>
          </div>
        `).join(""), "No action items extracted.")}
        ${renderMinutesSection("Decisions", (minutes.decisions || []).map((item) => `
          <div class="evidence-item">
            <strong>${escapeHtml(item.decision)}</strong>
            <span>Supersedes: ${escapeHtml(item.supersedes || "none")}</span>
            <blockquote>${escapeHtml(item.evidence || "No evidence attached")}</blockquote>
          </div>
        `).join(""), "No decisions extracted.")}
      </div>
    </article>
  `;
}

function renderMinutesSection(title, body, emptyText) {
  return `
    <section class="variant-card minutes-card">
      <h4>${title}</h4>
      ${body || `<div class="judge-text">${emptyText}</div>`}
    </section>
  `;
}

function renderTasks(tasks) {
  if (!tasks?.length) {
    tasksBoard.className = "case-table empty";
    tasksBoard.textContent = "Derived mock tasks will appear here.";
    return;
  }
  tasksBoard.className = "case-table";
  tasksBoard.innerHTML = tasks.map((task) => `
    <article class="case-item">
      <div class="case-top">
        <div>
          <div class="case-variant">mock task</div>
          <div class="case-title">${escapeHtml(task.title)}</div>
        </div>
        <div>${escapeHtml(task.status)}</div>
      </div>
      <div class="judge-text">
        <strong>Assignee:</strong> ${escapeHtml(task.assignee || "unassigned")}<br/>
        <strong>Due:</strong> ${escapeHtml(task.due_date || "not set")}<br/>
        <strong>Evidence:</strong> ${escapeHtml(task.source_evidence || "-")}
      </div>
    </article>
  `).join("");
}

function renderAlerts(alerts) {
  if (!alerts?.length) {
    alertsBoard.className = "case-table empty";
    alertsBoard.textContent = "Cross-meeting hints will appear here.";
    return;
  }
  alertsBoard.className = "case-table";
  alertsBoard.innerHTML = alerts.map((alert) => `
    <article class="case-item">
      <div class="case-top">
        <div>
          <div class="case-variant">${escapeHtml(alert.type)}</div>
          <div class="case-title">${escapeHtml(alert.title)}</div>
        </div>
      </div>
      <div class="judge-text">
        ${escapeHtml(alert.message || "")}<br/>
        ${alert.task ? `<strong>Task:</strong> ${escapeHtml(alert.task)}<br/>` : ""}
        ${alert.related_meeting_id ? `<strong>Related meeting:</strong> ${escapeHtml(alert.related_meeting_id)}<br/>` : ""}
        ${alert.supersedes ? `<strong>Supersedes:</strong> ${escapeHtml(alert.supersedes)}` : ""}
      </div>
    </article>
  `).join("");
}

async function loadScenarios() {
  const data = await fetchJson("/api/scenarios");
  scenarioSelect.innerHTML = `
    <option value="">all scenarios</option>
    ${data.scenarios.map((name) => `<option value="${name}">${name}</option>`).join("")}
  `;
}

async function loadDemoCases() {
  const data = await fetchJson("/api/demo/cases");
  demoCases = data.cases || [];
  demoCaseSelect.innerHTML = `
    <option value="">choose a mock case</option>
    ${demoCases.map((item) => `<option value="${item.case_id}">${item.case_id} | ${item.scenario}</option>`).join("")}
  `;
}

async function loadRuns() {
  const data = await fetchJson("/api/runs");
  renderRuns(data.runs || []);
}

async function loadMeetings() {
  const data = await fetchJson("/api/demo/meetings");
  renderMeetingArchive(data.meetings || []);
}

async function loadRun(runId) {
  const data = await fetchJson(`/api/run?id=${encodeURIComponent(runId)}`);
  activeRunId = data.run.run_id;
  renderSummary(data.summary);
  renderCases(data);
  runMeta.textContent = `Viewing run ${data.run.run_id} | scenario=${data.run.scenario || "all"} | v2=${data.run.v2_impl}`;
  updateProgress(data.run);
  if (data.run.status === "completed") {
    setStatus(statusPill, "done", "Complete");
  } else if (data.run.status === "failed") {
    setStatus(statusPill, "error", "Failed");
    runMeta.textContent = data.run.error_message || runMeta.textContent;
  } else {
    setStatus(statusPill, "running", "Running");
  }
  await loadRuns();
  return data;
}

async function loadMeeting(meetingId) {
  const data = await fetchJson(`/api/demo/meeting?id=${encodeURIComponent(meetingId)}`);
  activeMeetingId = data.meeting.meeting_id;
  renderComparison(data.comparison);
  renderMinutes(data.minutes);
  renderTasks(data.derived_tasks);
  renderAlerts(data.alerts);
  demoMeta.textContent = `Viewing ${data.meeting.title} | ${data.meeting.scenario || "ad_hoc"} | ${data.meeting.meeting_id}`;
  updateDemoProgress(data.meeting);
  if (data.meeting.status === "completed") {
    setStatus(demoStatusPill, "done", "Complete");
  } else if (data.meeting.status === "failed") {
    setStatus(demoStatusPill, "error", "Failed");
    demoMeta.textContent = data.meeting.error_message || demoMeta.textContent;
  } else {
    setStatus(demoStatusPill, "running", "Running");
  }
  await loadMeetings();
  return data;
}

async function deleteRun(runId) {
  await fetchJson(`/api/run?id=${encodeURIComponent(runId)}`, { method: "DELETE" });
  if (activeRunId === runId) {
    activeRunId = null;
    renderSummary({});
    renderCases({});
    setStatus(statusPill, "idle", "Idle");
    runMeta.textContent = "Run deleted.";
    updateProgress(null);
  }
  await loadRuns();
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function stopDemoPolling() {
  if (demoPollTimer) {
    clearTimeout(demoPollTimer);
    demoPollTimer = null;
  }
}

async function pollRun(runId) {
  try {
    const data = await loadRun(runId);
    if (data.run.status === "completed" || data.run.status === "failed") {
      runButton.disabled = false;
      stopPolling();
      return;
    }
    pollTimer = setTimeout(() => pollRun(runId), 3000);
  } catch (error) {
    setStatus(statusPill, "error", "Error");
    runMeta.textContent = error.message;
    runButton.disabled = false;
    stopPolling();
  }
}

async function pollMeeting(meetingId) {
  try {
    const data = await loadMeeting(meetingId);
    if (data.meeting.status === "completed" || data.meeting.status === "failed") {
      demoRunButton.disabled = false;
      stopDemoPolling();
      return;
    }
    demoPollTimer = setTimeout(() => pollMeeting(meetingId), 3000);
  } catch (error) {
    setStatus(demoStatusPill, "error", "Error");
    demoMeta.textContent = error.message;
    demoRunButton.disabled = false;
    stopDemoPolling();
  }
}

loadMockButton.addEventListener("click", () => {
  const selected = demoCases.find((item) => item.case_id === demoCaseSelect.value);
  if (!selected) {
    return;
  }
  demoTitleInput.value = selected.title;
  demoTranscriptInput.value = selected.transcript;
});

runButton.addEventListener("click", async () => {
  try {
    runButton.disabled = true;
    stopPolling();
    setStatus(statusPill, "running", "Running");
    runMeta.textContent = "Lab is running with real LLM calls. This can take a while.";
    progressBar.style.width = "0%";
    progressText.textContent = "queued | 0/0 | - | -";
    const result = await fetchJson("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: scenarioSelect.value || null,
      }),
    });
    runMeta.textContent = `Run started | run_id=${result.run_id}`;
    await pollRun(result.run_id);
  } catch (error) {
    setStatus(statusPill, "error", "Error");
    runMeta.textContent = error.message;
    runButton.disabled = false;
  }
});

demoRunButton.addEventListener("click", async () => {
  try {
    demoRunButton.disabled = true;
    stopDemoPolling();
    setStatus(demoStatusPill, "running", "Running");
    demoMeta.textContent = "Running V1 and V2 on the workspace transcript.";
    demoProgressBar.style.width = "0%";
    demoProgressText.textContent = "queued | preparing input";
    const transcript = demoTranscriptInput.value.trim();
    const caseId = transcript ? null : (demoCaseSelect.value || null);
    const selected = demoCases.find((item) => item.case_id === demoCaseSelect.value);
    const result = await fetchJson("/api/demo/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: demoTitleInput.value.trim() || null,
        transcript: transcript || null,
        case_id: caseId,
        scenario: selected?.scenario || null,
      }),
    });
    demoMeta.textContent = `Workspace run started | meeting_id=${result.meeting_id}`;
    await pollMeeting(result.meeting_id);
  } catch (error) {
    setStatus(demoStatusPill, "error", "Error");
    demoMeta.textContent = error.message;
    demoRunButton.disabled = false;
  }
});

async function boot() {
  activateTab("workbench");
  setStatus(statusPill, "idle", "Idle");
  setStatus(demoStatusPill, "idle", "Idle");
  updateProgress(null);
  updateDemoProgress(null);
  if (plainToggle) {
    plainToggle.checked = false;
    plainToggle.disabled = true;
    plainToggle.parentElement.title = "Plain mode has been removed. Lab uses the LangGraph V2 extractor only.";
  }
  await loadScenarios();
  await loadDemoCases();
  await loadRuns();
  await loadMeetings();
  renderComparison(null);
  renderMinutes(null);
  renderTasks(null);
  renderAlerts(null);
}

boot().catch((error) => {
  setStatus(statusPill, "error", "Error");
  setStatus(demoStatusPill, "error", "Error");
  runMeta.textContent = error.message;
  demoMeta.textContent = error.message;
});
