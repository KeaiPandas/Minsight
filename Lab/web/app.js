const tabs = document.querySelectorAll(".tab");
const tabPanels = document.querySelectorAll(".tab-panel");

const scenarioSelect = document.getElementById("scenarioSelect");
const runButton = document.getElementById("runButton");
const statusPill = document.getElementById("statusPill");
const runMeta = document.getElementById("runMeta");
const summaryBoard = document.getElementById("summaryBoard");
const runList = document.getElementById("runList");
const runArchiveScenarioSelect = document.getElementById("runArchiveScenarioSelect");
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
const minutesBoard = document.getElementById("minutesBoard");
const rawOutputBoard = document.getElementById("rawOutputBoard");
const tasksBoard = document.getElementById("tasksBoard");
const alertsBoard = document.getElementById("alertsBoard");

let pollTimer = null;
let demoPollTimer = null;
let activeRunId = null;
let activeMeetingId = null;
let demoCases = [];
let allRuns = [];

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function setStatus(element, kind, text) {
  element.className = `status-pill ${kind}`;
  element.textContent = text;
}

function formatScore(score) {
  return `${((score || 0) * 100).toFixed(1)}%`;
}

function formatDelta(score) {
  const value = score || 0;
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}pp`;
}

function variantLabel(variant) {
  if (variant === "v2") {
    return "Minsight Agent";
  }
  if (variant === "v1") {
    return "V1 Archive";
  }
  return variant.toUpperCase();
}

function formatJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderJsonDetails(title, value, open = false) {
  return `
    <details class="json-details" ${open ? "open" : ""}>
      <summary>${escapeHtml(title)}</summary>
      <pre class="json-viewer">${escapeHtml(formatJson(value))}</pre>
    </details>
  `;
}

function activateTab(name) {
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  tabPanels.forEach((panel) => panel.classList.toggle("active", panel.id === `${name}Tab`));
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

function updateProgress(run) {
  const total = run?.total_tasks || 0;
  const completed = run?.completed_tasks || 0;
  const pct = total > 0 ? Math.min(100, (completed / total) * 100) : 0;
  progressBar.style.width = `${pct}%`;
  progressText.textContent = `${run?.phase || "queued"} | ${completed}/${total} | ${run?.current_case_id || "-"} | ${run?.current_variant || "-"}`;
}

function updateDemoProgress(meeting) {
  const status = meeting?.status || "queued";
  demoProgressBar.style.width = status === "completed" ? "100%" : status === "running" ? "66%" : "0%";
  demoProgressText.textContent = `${meeting?.phase || "queued"} | ${meeting?.source_case_id || meeting?.scenario || "ad_hoc"}`;
}

function renderSummary(summary, historyDelta) {
  const variants = Object.entries(summary || {}).filter(([variant]) => variant !== "v1");
  if (!variants.length) {
    summaryBoard.className = "summary-board empty";
    summaryBoard.textContent = "暂无基准结果。";
    return;
  }
  summaryBoard.className = "summary-board";
  summaryBoard.innerHTML = `
    ${renderV2HistoryHeatmap(historyDelta)}
    <div class="variant-grid">
      ${variants.map(([variant, scores]) => `
        <div class="variant-card">
          <h4>${variantLabel(variant)}</h4>
          ${[
            ["参会人", scores.participants],
            ["要点", scores.key_points],
            ["待办", scores.action_items],
            ["决策", scores.decisions],
            ["总体", scores.overall],
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

function renderRuns(runs, filterScenario = "") {
  const visibleRuns = filterScenario
    ? runs.filter((run) => run.scenario === filterScenario)
    : runs;
  if (!visibleRuns.length) {
    runList.className = "run-list empty";
    runList.textContent = filterScenario
      ? `暂无 ${filterScenario} 的历史运行。`
      : "暂无历史运行。";
    return;
  }
  runList.className = "run-list";
  runList.innerHTML = visibleRuns.map((run) => `
    <div class="history-row ${activeRunId === run.run_id ? "selected" : ""}" data-run-id="${run.run_id}">
      <button class="history-item" data-open-run-id="${run.run_id}">
        <div class="run-id">${run.run_id.slice(0, 8)}</div>
        <div class="meta">场景：${escapeHtml(run.scenario || "全部")} | v2：${escapeHtml(run.v2_impl)} | ${new Date(run.created_at).toLocaleString()}</div>
      </button>
      <button class="history-delete" data-delete-run-id="${run.run_id}" aria-label="删除运行 ${run.run_id.slice(0, 8)}">删除</button>
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
    caseTable.textContent = "运行基准后，这里显示逐条评审结果和原始输出。";
    return;
  }
  caseTable.className = "case-table";
  caseTable.innerHTML = cases.map((item) => `
    <article class="case-item">
      <div class="case-top">
        <div>
          <div class="case-variant">数据集</div>
          <div class="case-title">${escapeHtml(item.case_id)} | ${escapeHtml(item.scenario)}</div>
        </div>
      </div>
      ${renderV2HistoryHeatmap(item.v2_history_delta)}
      <div class="variant-grid detail-grid">
        ${Object.keys(item.variants || {}).filter((variant) => variant !== "v1").sort().map((variant) => renderVariantDetail(item, variant)).join("")}
      </div>
    </article>
  `).join("");
}

function renderV2HistoryHeatmap(delta) {
  if (!delta) {
    return `
      <section class="heatmap-card empty-heatmap">
        <div class="heatmap-title">暂无上一次同任务结果</div>
        <div class="heatmap-note">再次运行同一个数据集后，这里会显示本次 Minsight Agent 相对上一次的分数变化。</div>
      </section>
    `;
  }
  const metrics = [
    ["participants", "参会人"],
    ["key_points", "要点"],
    ["action_items", "待办"],
    ["decisions", "决策"],
    ["overall", "总体"],
  ];
  return `
    <section class="heatmap-card">
      <div class="heatmap-head">
        <div>
          <div class="case-variant">V2 历史对比热力图</div>
          <div class="heatmap-title">本次 Minsight Agent - 上一次同任务</div>
        </div>
        <div class="heatmap-note">对比 run ${escapeHtml((delta.previous_run_id || "").slice(0, 8))}</div>
      </div>
      <div class="heatmap-grid">
        ${metrics.map(([key, label]) => {
          const value = delta.delta?.[key] || 0;
          const tone = value > 0.001 ? "up" : value < -0.001 ? "down" : "flat";
          return `
            <div class="heat-cell ${tone}">
              <span>${label}</span>
              <strong>${formatDelta(value)}</strong>
              <small>${formatScore(delta.previous?.[key])} → ${formatScore(delta.current?.[key])}</small>
            </div>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function renderVariantDetail(item, variant) {
  const entry = item.variants?.[variant];
  if (!entry) {
    return `
      <section class="variant-card detail-card">
        <h4>${variantLabel(variant)}</h4>
        <div class="judge-text">该版本暂无结果。</div>
      </section>
    `;
  }
  const result = entry.judgement;
  return `
    <section class="variant-card detail-card">
      <div class="case-top">
        <div class="case-variant">${variantLabel(variant)}</div>
        <div>${entry.created_at ? new Date(entry.created_at).toLocaleString() : ""}</div>
      </div>
      ${result ? [
        ["参会人", result.participants],
        ["要点", result.key_points],
        ["待办", result.action_items],
        ["决策", result.decisions],
        ["总体", result.overall],
      ].map(([label, value]) => `
        <div class="metric-row">
          <span>${label}</span>
          <strong>${formatScore(value)}</strong>
        </div>
      `).join("") : `<div class="judge-text">评审尚未完成。</div>`}
      ${result ? `
        <div class="judge-text">
          <strong>摘要：</strong> ${escapeHtml(result.summary)}<br/>
          <strong>优点：</strong> ${escapeHtml((result.strengths || []).join(", ") || "-")}<br/>
          <strong>问题：</strong> ${escapeHtml((result.issues || []).join(", ") || "-")}
        </div>
      ` : ""}
      ${renderJsonDetails("查看该版本结构化输出", entry.prediction?.output)}
      ${renderJsonDetails("查看模型路由记录", entry.prediction?.routing || [])}
    </section>
  `;
}

function renderMeetingArchive(meetings) {
  if (!meetings.length) {
    meetingList.className = "run-list empty";
    meetingList.textContent = "暂无工作台记录。";
    return;
  }
  meetingList.className = "run-list";
  meetingList.innerHTML = meetings.map((meeting) => `
    <button class="history-item ${activeMeetingId === meeting.meeting_id ? "selected-card" : ""}" data-meeting-id="${meeting.meeting_id}">
      <div class="run-id">${escapeHtml(meeting.title)}</div>
      <div class="meta">${escapeHtml(meeting.scenario || "ad_hoc")} | ${meeting.status} | ${new Date(meeting.created_at).toLocaleString()}</div>
    </button>
  `).join("");
  meetingList.querySelectorAll("[data-meeting-id]").forEach((button) => {
    button.addEventListener("click", () => loadMeeting(button.dataset.meetingId));
  });
}

function renderMinutes(minutes) {
  if (!minutes) {
    minutesBoard.className = "case-table empty";
    minutesBoard.textContent = "结构化会议纪要会显示在这里。";
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
      <div class="judge-text"><strong>摘要：</strong> ${escapeHtml(minutes.summary_line)}</div>
      <div class="minutes-grid">
        ${renderMinutesSection("参会人", (minutes.participants || []).map((item) => `
          <div class="evidence-item"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.role || "未标注角色")}</span></div>
        `).join(""), "未抽取到参会人。")}
        ${renderMinutesSection("要点", (minutes.key_points || []).map((item) => `
          <div class="evidence-item"><strong>${escapeHtml(item.topic)}</strong><span>${escapeHtml(item.summary || "")}</span></div>
        `).join(""), "未抽取到要点。")}
        ${renderMinutesSection("待办", (minutes.action_items || []).map((item) => `
          <div class="evidence-item">
            <strong>${escapeHtml(item.task)}</strong>
            <span>负责人：${escapeHtml(item.owner || "未指派")} | 截止：${escapeHtml(item.due || "未设置")}</span>
            <blockquote>${escapeHtml(item.evidence || "无证据")}</blockquote>
          </div>
        `).join(""), "未抽取到待办。")}
        ${renderMinutesSection("决策", (minutes.decisions || []).map((item) => `
          <div class="evidence-item">
            <strong>${escapeHtml(item.decision)}</strong>
            <span>取代：${escapeHtml(item.supersedes || "无")}</span>
            <blockquote>${escapeHtml(item.evidence || "无证据")}</blockquote>
          </div>
        `).join(""), "未抽取到决策。")}
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

function renderRawOutput(output) {
  if (!output) {
    rawOutputBoard.className = "case-table empty";
    rawOutputBoard.textContent = "运行会议后，这里显示 V2 的完整输出。";
    return;
  }
  rawOutputBoard.className = "case-table";
  rawOutputBoard.innerHTML = `
    <article class="case-item">
      <section class="variant-card detail-card">
        <h4>V2 原始输出</h4>
        ${renderJsonDetails("展开 V2 JSON", output, true)}
      </section>
    </article>
  `;
}

function renderTasks(tasks) {
  if (!tasks?.length) {
    tasksBoard.className = "case-table empty";
    tasksBoard.textContent = "派生的待办任务会显示在这里。";
    return;
  }
  tasksBoard.className = "case-table";
  tasksBoard.innerHTML = tasks.map((task) => `
    <article class="case-item">
      <div class="case-top">
        <div>
          <div class="case-variant">派生任务</div>
          <div class="case-title">${escapeHtml(task.title)}</div>
        </div>
        <div>${escapeHtml(task.status)}</div>
      </div>
      <div class="judge-text">
        <strong>负责人：</strong> ${escapeHtml(task.assignee || "未指派")}<br/>
        <strong>截止：</strong> ${escapeHtml(task.due_date || "未设置")}<br/>
        <strong>证据：</strong> ${escapeHtml(task.source_evidence || "-")}
      </div>
    </article>
  `).join("");
}

function renderAlerts(alerts) {
  if (!alerts?.length) {
    alertsBoard.className = "case-table empty";
    alertsBoard.textContent = "跨会议提示会显示在这里。";
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
        ${alert.task ? `<strong>任务：</strong> ${escapeHtml(alert.task)}<br/>` : ""}
        ${alert.related_meeting_id ? `<strong>关联会议：</strong> ${escapeHtml(alert.related_meeting_id)}<br/>` : ""}
        ${alert.supersedes ? `<strong>取代：</strong> ${escapeHtml(alert.supersedes)}` : ""}
      </div>
    </article>
  `).join("");
}

async function loadScenarios() {
  const data = await fetchJson("/api/scenarios");
  scenarioSelect.innerHTML = `
    <option value="">全部场景</option>
    ${data.scenarios.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("")}
  `;
  runArchiveScenarioSelect.innerHTML = `
    <option value="">全部任务</option>
    ${data.scenarios.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("")}
  `;
}

async function loadDemoCases() {
  try {
    const data = await fetchJson("/api/demo/cases");
    demoCases = data.cases || [];
    if (!demoCases.length) {
      demoCaseSelect.innerHTML = `<option value="">未找到样例，请重启 Lab 服务</option>`;
      loadMockButton.disabled = true;
      return;
    }
    loadMockButton.disabled = false;
    demoCaseSelect.innerHTML = `
      <option value="">选择一个样例</option>
      ${demoCases.map((item) => `<option value="${escapeHtml(item.case_id)}">${escapeHtml(item.case_id)} | ${escapeHtml(item.scenario)}</option>`).join("")}
    `;
  } catch (error) {
    demoCases = [];
    loadMockButton.disabled = true;
    demoCaseSelect.innerHTML = `<option value="">样例加载失败</option>`;
    throw error;
  }
}

async function loadRuns() {
  const data = await fetchJson("/api/runs");
  allRuns = data.runs || [];
  renderRuns(allRuns, runArchiveScenarioSelect.value || "");
}

async function loadMeetings() {
  const data = await fetchJson("/api/demo/meetings");
  renderMeetingArchive(data.meetings || []);
}

async function loadRun(runId) {
  const data = await fetchJson(`/api/run?id=${encodeURIComponent(runId)}`);
  activeRunId = data.run.run_id;
  renderSummary(data.summary, data.summary_history_delta);
  renderCases(data);
    runMeta.textContent = `查看运行 ${data.run.run_id} | 场景=${data.run.scenario || "全部"} | agent=${data.run.v2_impl}`;
  updateProgress(data.run);
  if (data.run.status === "completed") {
    setStatus(statusPill, "done", "完成");
  } else if (data.run.status === "failed") {
    setStatus(statusPill, "error", "失败");
    runMeta.textContent = data.run.error_message || runMeta.textContent;
  } else {
    setStatus(statusPill, "running", "运行中");
  }
  await loadRuns();
  return data;
}

async function loadMeeting(meetingId) {
  const data = await fetchJson(`/api/demo/meeting?id=${encodeURIComponent(meetingId)}`);
  activeMeetingId = data.meeting.meeting_id;
  renderMinutes(data.minutes);
  renderRawOutput(data.output || data.variants?.v2);
  renderTasks(data.derived_tasks);
  renderAlerts(data.alerts);
  demoMeta.textContent = `查看 ${data.meeting.title} | ${data.meeting.scenario || "ad_hoc"} | ${data.meeting.meeting_id}`;
  updateDemoProgress(data.meeting);
  if (data.meeting.status === "completed") {
    setStatus(demoStatusPill, "done", "完成");
  } else if (data.meeting.status === "failed") {
    setStatus(demoStatusPill, "error", "失败");
    demoMeta.textContent = data.meeting.error_message || demoMeta.textContent;
  } else {
    setStatus(demoStatusPill, "running", "运行中");
  }
  await loadMeetings();
  return data;
}

async function deleteRun(runId) {
  await fetchJson(`/api/run?id=${encodeURIComponent(runId)}`, { method: "DELETE" });
  if (activeRunId === runId) {
    activeRunId = null;
    renderSummary({}, null);
    renderCases({});
    setStatus(statusPill, "idle", "空闲");
    runMeta.textContent = "运行已删除。";
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
    setStatus(statusPill, "error", "出错");
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
    setStatus(demoStatusPill, "error", "出错");
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
    setStatus(statusPill, "running", "运行中");
    runMeta.textContent = "正在用真实 LLM 运行 Minsight Agent 回归评测，可能需要一会儿。";
    progressBar.style.width = "0%";
    progressText.textContent = "排队中 | 0/0 | - | -";
    const result = await fetchJson("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenarioSelect.value || null }),
    });
    runMeta.textContent = `已启动 | run_id=${result.run_id}`;
    await pollRun(result.run_id);
  } catch (error) {
    setStatus(statusPill, "error", "出错");
    runMeta.textContent = error.message;
    runButton.disabled = false;
  }
});

runArchiveScenarioSelect.addEventListener("change", () => {
  renderRuns(allRuns, runArchiveScenarioSelect.value || "");
});

demoRunButton.addEventListener("click", async () => {
  try {
    demoRunButton.disabled = true;
    stopDemoPolling();
    setStatus(demoStatusPill, "running", "运行中");
    demoMeta.textContent = "正在对该转写运行 V2 工作流。";
    demoProgressBar.style.width = "0%";
    demoProgressText.textContent = "排队中 | 准备输入";
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
    demoMeta.textContent = `已启动 | meeting_id=${result.meeting_id}`;
    await pollMeeting(result.meeting_id);
  } catch (error) {
    setStatus(demoStatusPill, "error", "出错");
    demoMeta.textContent = error.message;
    demoRunButton.disabled = false;
  }
});

async function boot() {
  activateTab("workbench");
  setStatus(statusPill, "idle", "空闲");
  setStatus(demoStatusPill, "idle", "空闲");
  updateProgress(null);
  updateDemoProgress(null);
  await loadScenarios();
  await loadDemoCases();
  await loadRuns();
  await loadMeetings();
  renderSummary({}, null);
  renderCases({});
  renderMinutes(null);
  renderRawOutput(null);
  renderTasks(null);
  renderAlerts(null);
}

boot().catch((error) => {
  setStatus(statusPill, "error", "出错");
  setStatus(demoStatusPill, "error", "出错");
  runMeta.textContent = error.message;
  demoMeta.textContent = error.message;
});
