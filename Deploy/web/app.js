const state = {
  cases: [],
  meetingId: null,      // 当前详情会议
  meetingData: null,    // 当前详情数据缓存
  runningId: null,      // 正在运行的会议（列表页轮询用）
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

const SYNC_LABEL = { pending: "待同步", dry_run: "预览·未写入", synced: "已同步", failed: "同步失败" };
const syncLabel = (s) => SYNC_LABEL[s] || s || "待同步";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function setStatus(text, kind = "idle") {
  const pill = $("statusPill");
  pill.textContent = text;
  pill.className = `pill ${kind}`;
}

function statusKind(status) {
  if (status === "completed") return "done";
  if (status === "failed") return "error";
  if (status === "running" || status === "queued") return "running";
  return "";
}

function statusText(status) {
  return { completed: "完成", failed: "失败", running: "运行中", queued: "排队中" }[status] || status || "—";
}

/* ---------------- 样例与运行 ---------------- */

async function loadCases() {
  const payload = await requestJson("/api/demo/cases");
  state.cases = payload.cases || [];
  $("caseSelect").innerHTML = [
    '<option value="">选择一个样例</option>',
    ...state.cases.map((item) => `<option value="${escapeHtml(item.case_id)}">${escapeHtml(item.title)}</option>`),
  ].join("");
}

function loadSelectedCase() {
  const selected = state.cases.find((item) => item.case_id === $("caseSelect").value);
  if (!selected) return;
  $("titleInput").value = selected.title || "";
  $("transcriptInput").value = selected.transcript || "";
}

async function runMeeting() {
  const transcript = $("transcriptInput").value.trim();
  if (!transcript) {
    setStatus("需要转写", "error");
    $("meta").textContent = "请先输入会议转写，或载入一个样例。";
    return;
  }
  setStatus("排队中", "running");
  const payload = await requestJson("/api/demo/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: $("titleInput").value.trim(),
      transcript,
      case_id: $("caseSelect").value || null,
    }),
  });
  state.runningId = payload.meeting_id;
  $("meta").textContent = `会议已创建：${payload.meeting_id}`;
  pollRunning();
}

async function pollRunning() {
  clearTimeout(state.pollTimer);
  if (!state.runningId) return;
  const payload = await requestJson(`/api/demo/meeting?id=${encodeURIComponent(state.runningId)}`);
  const status = payload.meeting?.status;
  if (status === "completed") {
    setStatus("完成", "done");
    $("meta").textContent = "运行完成，正在打开会议详情…";
    await loadMeetings();
    const id = state.runningId;
    state.runningId = null;
    state.meetingData = null;
    location.hash = `#/meeting/${id}`;   // 跳转到详情
    return;
  }
  if (status === "failed") {
    setStatus("失败", "error");
    $("meta").textContent = payload.meeting?.error_message || "运行失败";
    state.runningId = null;
    return;
  }
  setStatus("运行中", "running");
  state.pollTimer = setTimeout(pollRunning, 1000);
}

/* ---------------- 会议列表 ---------------- */

async function loadMeetings() {
  const payload = await requestJson("/api/demo/meetings");
  const meetings = payload.meetings || [];
  $("meetingCount").textContent = meetings.length ? `${meetings.length} 场` : "";
  $("meetingsBoard").className = meetings.length ? "meeting-list" : "meeting-list empty";
  $("meetingsBoard").innerHTML = meetings.length
    ? meetings.map((meeting) => `
      <a class="meeting-row" href="#/meeting/${encodeURIComponent(meeting.meeting_id)}">
        <div class="meeting-row-main">
          <strong>${escapeHtml(meeting.title || "未命名会议")}</strong>
          <span class="meeting-row-meta">${escapeHtml(meeting.created_at || "")}</span>
        </div>
        <div class="meeting-row-side">
          <span class="pill ${statusKind(meeting.status)}">${escapeHtml(statusText(meeting.status))}</span>
          <span class="chev">›</span>
        </div>
      </a>
    `).join("")
    : "暂无会议记录，先运行一次会议。";
}

/* ---------------- 详情渲染 ---------------- */

function renderDetailHeader(payload) {
  const meeting = payload.meeting || {};
  const minutes = payload.minutes || {};
  $("detailTitle").textContent = meeting.title || minutes.title || "会议详情";
  const bits = [];
  if (meeting.scenario) bits.push(escapeHtml(meeting.scenario));
  if (meeting.created_at) bits.push(escapeHtml(meeting.created_at));
  $("detailMeta").innerHTML = bits.join(" · ");
  const pill = $("detailStatus");
  pill.textContent = statusText(meeting.status);
  pill.className = `pill ${statusKind(meeting.status)}`;
}

function renderMeeting(payload) {
  renderMinutes(payload.minutes || {});
  renderTasks(payload.derived_tasks || []);
  renderDecisions(payload.decisions || []);
  renderAlerts(payload.alerts || []);
}

function renderMinutes(minutes) {
  const participants = (minutes.participants || [])
    .map((item) => `<li><strong>${escapeHtml(item.name)}</strong>${item.role ? ` · ${escapeHtml(item.role)}` : ""}</li>`).join("");
  const keyPoints = (minutes.key_points || [])
    .map((item) => `<li><strong>${escapeHtml(item.topic || "要点")}</strong> ${escapeHtml(item.summary || "")}</li>`).join("");
  $("minutesBoard").className = "";
  $("minutesBoard").innerHTML = `
    <h3>${escapeHtml(minutes.title || "会议纪要")}</h3>
    <p class="muted">${escapeHtml(minutes.summary_line || "")}</p>
    <h4>参会人</h4><ul class="clean-list">${participants || "<li>暂无</li>"}</ul>
    <h4>讨论要点</h4><ul class="clean-list">${keyPoints || "<li>暂无</li>"}</ul>
  `;
}

function renderTasks(tasks) {
  if (!tasks.length) {
    $("tasksBoard").className = "empty";
    $("tasksBoard").innerHTML = "暂无派生待办。";
    return;
  }
  $("tasksBoard").className = "";
  $("tasksBoard").innerHTML = `
    <div class="sync-toolbar">
      <button id="syncTasksButton" class="secondary">同步待办到飞书</button>
      <span class="muted">默认预览模式（dry-run），不写入飞书。</span>
    </div>
    ${tasks.map((task) => {
      const s = task.sync_status || "pending";
      return `
      <div class="item">
        <div class="item-top">
          <strong>${escapeHtml(task.title)}</strong>
          <span class="badge sync ${escapeHtml(s)}">${escapeHtml(syncLabel(s))}</span>
        </div>
        <p class="muted">负责人：${escapeHtml(task.assignee || "未指派")} · 截止：${escapeHtml(task.due_date || "未设置")}</p>
        ${task.external_url ? `<p><a class="feishu-link" href="${escapeHtml(task.external_url)}" target="_blank" rel="noreferrer">打开飞书任务 ↗</a></p>` : ""}
        ${task.sync_error ? `<p class="muted">同步错误：${escapeHtml(task.sync_error)}</p>` : ""}
        <blockquote>${escapeHtml(task.source_evidence || "")}</blockquote>
      </div>`;
    }).join("")}
  `;
  const btn = $("syncTasksButton");
  if (btn) btn.addEventListener("click", () => syncTasks(btn));
}

function renderDecisions(decisions) {
  if (!decisions.length) {
    $("decisionsBoard").className = "empty";
    $("decisionsBoard").innerHTML = "暂无决策。";
    return;
  }
  $("decisionsBoard").className = "";
  $("decisionsBoard").innerHTML = `
    <div class="sync-toolbar">
      <button id="syncDecisionsButton" class="secondary">同步决策到飞书多维表格</button>
      <span class="muted">默认预览模式（dry-run），不写入飞书 Base。</span>
    </div>
    ${decisions.map((decision) => {
      const s = decision.base_sync_status || "pending";
      return `
      <div class="item">
        <div class="item-top">
          <strong>${escapeHtml(decision.decision)}</strong>
          <span class="badge sync ${escapeHtml(s)}">${escapeHtml(syncLabel(s))}</span>
        </div>
        ${decision.supersedes ? `<p class="muted">替代：${escapeHtml(decision.supersedes)}</p>` : ""}
        ${decision.base_url ? `<p><a class="feishu-link" href="${escapeHtml(decision.base_url)}" target="_blank" rel="noreferrer">打开飞书多维表格 ↗</a></p>` : ""}
        <blockquote>${escapeHtml(decision.evidence || "")}</blockquote>
      </div>`;
    }).join("")}
  `;
  const btn = $("syncDecisionsButton");
  if (btn) btn.addEventListener("click", () => syncDecisions(btn));
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    $("alertsBoard").className = "empty";
    $("alertsBoard").innerHTML = "暂无跨会议提示。";
    return;
  }
  $("alertsBoard").className = "";
  $("alertsBoard").innerHTML = alerts.map((alert) => `
    <div class="item">
      <div class="item-top"><strong>${escapeHtml(alert.title)}</strong>${alert.type ? `<span class="badge">${escapeHtml(alert.type)}</span>` : ""}</div>
      <p class="muted">${escapeHtml(alert.message || "")}</p>
    </div>
  `).join("");
}

/* ---------------- 同步 ---------------- */

async function syncTasks(button) {
  if (!state.meetingId) return;
  if (button) { button.disabled = true; button.textContent = "同步中…"; }
  try {
    const result = await requestJson("/api/demo/meeting/sync-feishu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ meeting_id: state.meetingId }),
    });
    const mode = result.mode === "lark_cli" ? "已写入飞书" : "预览完成（dry-run，未写入）";
    $("detailMeta").innerHTML = `待办同步：${escapeHtml(mode)}`;
    await refreshDetail();
  } catch (error) {
    if (button) { button.disabled = false; button.textContent = "同步待办到飞书"; }
    $("detailMeta").innerHTML = `待办同步失败：${escapeHtml(error.message)}`;
  }
}

async function syncDecisions(button) {
  if (!state.meetingId) return;
  if (button) { button.disabled = true; button.textContent = "同步中…"; }
  try {
    const result = await requestJson("/api/demo/meeting/sync-decisions-base", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ meeting_id: state.meetingId }),
    });
    const mode = result.mode === "lark_cli" ? "已写入飞书 Base" : "预览完成（dry-run，未写入）";
    $("detailMeta").innerHTML = `决策同步：${escapeHtml(mode)}`;
    await refreshDetail();
  } catch (error) {
    if (button) { button.disabled = false; button.textContent = "同步决策到飞书多维表格"; }
    $("detailMeta").innerHTML = `决策同步失败：${escapeHtml(error.message)}`;
  }
}

async function refreshDetail() {
  if (!state.meetingId) return;
  const payload = await requestJson(`/api/demo/meeting?id=${encodeURIComponent(state.meetingId)}`);
  state.meetingData = payload;
  renderDetailHeader(payload);
  renderMeeting(payload);
}

/* ---------------- 路由：列表 <-> 详情 ---------------- */

function activateDetailTab(tab) {
  const active = ["minutes", "tasks", "decisions", "alerts"].includes(tab) ? tab : "minutes";
  document.querySelectorAll(".dtab").forEach((el) => el.classList.toggle("active", el.dataset.tab === active));
  document.querySelectorAll(".dtab-panel").forEach((el) => { el.hidden = el.dataset.panel !== active; });
}

function showList() {
  $("detailView").hidden = true;
  $("listView").hidden = false;
  state.meetingId = null;
  loadMeetings().catch(() => {});
}

async function showDetail(meetingId, tab) {
  $("listView").hidden = true;
  $("detailView").hidden = false;
  window.scrollTo({ top: 0 });
  if (state.meetingId !== meetingId || !state.meetingData) {
    state.meetingId = meetingId;
    $("detailTitle").textContent = "加载中…";
    $("detailMeta").innerHTML = "";
    try {
      const payload = await requestJson(`/api/demo/meeting?id=${encodeURIComponent(meetingId)}`);
      state.meetingData = payload;
      renderDetailHeader(payload);
      renderMeeting(payload);
    } catch (error) {
      $("detailTitle").textContent = "会议未找到";
      $("detailMeta").innerHTML = escapeHtml(error.message);
    }
  }
  activateDetailTab(tab);
}

function router() {
  const raw = decodeURIComponent((location.hash || "").replace(/^#/, "")) || "/";
  const match = raw.match(/^\/meeting\/([^/]+)(?:\/([^/]+))?$/);
  if (match) {
    showDetail(match[1], match[2]);
  } else {
    showList();
  }
}

/* 详情内 Tab 点击 -> 改 hash（每个分区一个可跳转 URL） */
document.querySelectorAll(".dtab").forEach((el) => {
  el.addEventListener("click", () => {
    if (state.meetingId) location.hash = `#/meeting/${encodeURIComponent(state.meetingId)}/${el.dataset.tab}`;
  });
});

$("backButton").addEventListener("click", () => { location.hash = "#/"; });
$("loadCaseButton").addEventListener("click", loadSelectedCase);
$("runButton").addEventListener("click", () => runMeeting().catch((error) => {
  setStatus("失败", "error");
  $("meta").textContent = error.message;
}));

window.addEventListener("hashchange", router);

/* ---------------- 启动 ---------------- */

loadCases().catch((error) => {
  setStatus("初始化失败", "error");
  $("meta").textContent = error.message;
});
router();
