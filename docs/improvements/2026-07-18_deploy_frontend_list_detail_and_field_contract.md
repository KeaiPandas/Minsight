# 交接：Deploy 前端「列表→详情」改版 + 前后端字段契约

> 交接对象：负责 `Deploy/` 后端的 agent。前端已改完（**只动了 `Deploy/web/` 三个文件，未改任何后端接口**），本文说明前端现在依赖的**响应字段契约**，请后端按此对齐；标注 ✅=既有已用、⚠️=前端新读入需你确认命名。

## 1. 前端改了什么

`Deploy/web/` 从"单页长滚动"改为 **hash 路由的列表→详情**：

- **列表页 `#/`**：运行表单 + 会议记录列表（每场一行，点击跳详情）。
- **详情页 `#/meeting/<id>`**：返回 + 标题/状态 + 4 个分区 Tab（可读纪要 / 派生待办 / 决策与证据 / 跨会议提示），每个 Tab 有独立 URL `#/meeting/<id>/<tab>`（`minutes|tasks|decisions|alerts`）。
- 运行完成后自动跳到该会详情；待办/决策各自带同步按钮与四态徽章。

改动文件：`Deploy/web/index.html`、`Deploy/web/app.js`、`Deploy/web/styles.css`。**接口路径、请求体一律沿用现有约定，未新增/未改。**

## 2. 复用的接口（未改）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/demo/cases` | 样例列表 |
| GET | `/api/demo/meetings` | 会议列表 |
| GET | `/api/demo/meeting?id=<id>` | 会议详情 |
| POST | `/api/demo/run` | 运行一次会议 |
| POST | `/api/demo/meeting/sync-feishu` | 同步待办到飞书任务 |
| POST | `/api/demo/meeting/sync-decisions-base` | 同步决策到飞书多维表格（Base） |

## 3. 字段契约（前端读取的字段，请对齐命名）

### 3.1 `GET /api/demo/meetings` → `{ meetings: [...] }`
每个 meeting：`meeting_id`✅、`title`✅、`status`✅、`created_at`✅。

### 3.2 `GET /api/demo/meeting?id=` → 顶层对象
- `meeting`：`status`✅、`error_message`✅、`title`✅、`scenario`⚠️、`created_at`⚠️（详情头会显示 scenario 与创建时间；没有就不显示，不报错）。
- `minutes`：`title`✅、`summary_line`✅、`participants[]`✅（`{name, role}`）、`key_points[]`✅（`{topic, summary}`）。
- `derived_tasks[]`（派生待办）：
  - `title`✅、`assignee`✅、`due_date`✅、`source_evidence`✅、`sync_status`✅（`pending|dry_run|synced|failed`）。
  - `external_url`⚠️（已同步时给"打开飞书任务 ↗"链接，可空）。
  - `sync_error`⚠️（失败时展示原因，可空）。
- `decisions[]`（决策与证据）：
  - `decision`✅、`supersedes`✅、`evidence`✅、`base_sync_status`✅（`pending|dry_run|synced|failed`）。
  - `base_url`⚠️（已同步到 Base 时给"打开飞书多维表格 ↗"链接，可空）。
- `alerts[]`（跨会议提示）：`title`✅、`message`✅、`type`⚠️（有则作小标签展示，可空）。

### 3.3 同步接口返回
`POST /api/demo/meeting/sync-feishu` 与 `.../sync-decisions-base` 前端只读 **`mode`**⚠️（`dry_run` → 提示"预览完成（未写入）"；`lark_cli` → 提示"已写入飞书 / 已写入飞书 Base"）。同步后前端会重新 GET 详情刷新徽章，所以**只要同步把状态落库、详情能读到最新 `sync_status`/`base_sync_status` 即可**。

## 4. 需要后端确认/对齐的点（⚠️ 汇总）

1. **决策 Base 同步字段**：详情里每条 decision 是否返回 `base_sync_status` 与 `base_url`？（前端按这两个名字读；如后端用了别的名，二选一：改后端返回名，或告诉我改前端。）
2. **待办外链**：task 是否返回 `external_url`、`sync_error`？
3. **会议详情头**：`meeting.scenario` / `meeting.created_at` 是否随详情返回？（可选，缺了只是详情头少两行信息。）
4. **同步返回 `mode`**：两个 sync 接口是否都返回 `mode`（`dry_run`/`lark_cli`）？

以上字段缺失都不会让前端崩（有兜底：可空即不渲染对应部分），但**决策的 `base_sync_status` 是徽章状态的关键**，建议优先保证。

## 5. 前端未做（明确边界）
- 不改任何后端逻辑与接口。
- 不做真实飞书写入（由后端 sink + `MINSIGHT_FEISHU_SYNC_MODE` 决定，前端默认走后端的默认模式）。
- 详情内 Tab 仅前端路由，不额外请求后端（同一会议 Tab 切换不重复拉取）。
