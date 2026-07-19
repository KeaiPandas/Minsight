# V2 借鉴点对照表与 Demo 补强建议

> 目的：把外部仓库的可借鉴点、当前 `Minsight` 代码现状、以及下一步更像样的 Demo 补强方向整理到一处，方便在其他会话中继续实施。
>
> 更新时间：2026-07-18

---

## 1. 当前结论摘要

`Minsight` 现在已经不是空壳，已经具备：

- `V1` 单次调用基线，可用于对照
- `V2` LangGraph 多阶段抽取工作流
- `participants / key_points / action_items / decisions` 四类结构化输出
- `pydantic` 契约校验与一次 repair 回环
- `Lab` 独立 benchmark、SQLite 落库、LLM judge、Web 控制台
- 六类 mock 场景测试集

但它当前仍主要是一个 **“抽取器 + 测评台”**，还不是 PRD 里定义的 **“会议结构化中台”**。PRD 中最关键、但代码侧尚未形成完整展示的能力包括：

- 结构化资产持久化与跨会议检索
- 待办派生到下游任务系统
- 冲突检测 / 重复待办检测
- 证据回链的可视化展示
- 人工复核与纠错入口
- 更贴近真实产品的业务演示链路

因此，另一个会话的实施重点不应是继续重写 V2 抽取器，而应优先补齐 **“演示闭环”**。

---

## 2. GitHub 借鉴点对照表

| 仓库 | 链接 | 更像 Minsight 的哪一块 | 可直接借鉴的功能 | 建议在 Minsight 中如何落地 |
|---|---|---|---|---|
| `silverstein/minutes` | https://github.com/silverstein/minutes | 跨会议沉淀 / 智能层 | 模板化抽取、跨会议查询、conversation memory | 做 `meeting / standup / review / 1-on-1` 模板；补一个“历史会议检索 + 重复任务提示”的轻量版 |
| `Foundry81/n8n-zoom-transcript-analysis` | https://github.com/Foundry81/n8n-zoom-transcript-analysis | Workflow 编排 / 企业分析扩展 | transcript 分段、按能力拆节点、风险/机会额外抽取 | 延续 V2 的分链思路，后续加 `risks` / `open_questions` 作为 P1 展示字段 |
| `github/awesome-copilot` meeting-minutes skill | https://github.com/github/awesome-copilot/blob/main/skills/meeting-minutes/SKILL.md | 输出 schema / 纪要规范 | 严格 minutes schema、owner + due + acceptance criteria、parking lot、references | 升级 demo 输出层，不只展示 JSON；增加“人可读纪要视图”和“未决事项” |
| `NotYuSheng/MeetMemo` | https://github.com/NotYuSheng/MeetMemo | 输入质量 / 证据回链 | speaker diarization、音频-转写同步、自定义 prompt、本地化 | 在 demo 中增加 transcript segment UI，点击待办/决策可定位原文片段 |
| `paberr/ownscribe` | https://github.com/paberr/ownscribe | 模板化 / 本地优先 / 追问 | meeting 模板、跨 meeting QA、本地隐私优先 | 在文档和 demo 中强调“模型可替换 / OpenAI 兼容 / 私有化友好”；后续加“Ask meetings” 占位功能 |
| `Zenatek/linear-issues-from-meet` | https://github.com/topics/meeting-automation?o=desc&s=stars | 下游执行闭环 | action item -> issue、assignee resolution、审批确认流 | 做一个 mock 下游任务派生页，至少支持生成 task payload 或写入本地 SQLite 表 |
| `logisticPM/MeetingWizard` | https://github.com/logisticPM/MeetingWizard | 单产品完整体验 | 转写、纪要、历史管理、导出、存储 | 可借鉴“历史会议列表 + 详情页”的交互结构，用现有 Lab Web 快速复刻 |
| `inboxpraveen/LLM-Minutes-of-Meeting` | https://github.com/inboxpraveen/LLM-Minutes-of-Meeting | 端到端轻量 demo | 音视频 -> transcript -> minutes 的最小闭环 | 若面试更重 demo 感，可以额外加“上传 transcript 文本 -> 出纪要”的单页入口 |

### 最值得借鉴的 6 个产品点

1. **模板化抽取**
   不同会议类型使用不同 schema / prompt，而不是一套通用纪要。
2. **分链抽取**
   participants、key points、action items、decisions 分开做，最后融合。
3. **证据可回看**
   每个结构化结果都能回到 transcript 原文片段。
4. **跨会议智能**
   至少支持重复待办、责任冲突、决策反复中的一种轻量检测。
5. **任务闭环**
   抽取结果不是停在 JSON，而是能生成 task payload / mock 下游任务。
6. **人工复核**
   低置信度或缺要素条目，进入 review，而不是直接当最终结果。

---

## 3. 当前 Minsight 已实现能力盘点

以下判断基于 2026-07-18 本地代码。

### 3.1 已经有的能力

| 能力 | 现状 | 代码依据 |
|---|---|---|
| V1 对照基线 | 已有，单次 prompt + `json.loads` | `Core/v1/extractor.py` |
| V2 多阶段工作流 | 已有，统一走 LangGraph | `Core/v2/graph.py` |
| 说话人/别名归一 | 已有 normalize agent | `Core/v2/agents/normalize_agent.py` |
| 要点抽取 | 已有独立 agent | `Core/v2/agents/key_points_agent.py` |
| 待办 + 决策联合抽取 | 已有独立 agent | `Core/v2/agents/actions_decisions_agent.py` |
| 决策反复表达 | prompt 已要求 `supersedes` | `Core/prompts/v2/actions_decisions.txt` |
| due 不臆造 | 已通过 pydantic 规则归一为 `None` | `Core/shared/models.py` |
| owner 必填校验 | 已有字段校验 | `Core/shared/models.py` |
| repair 回环 | 已有一次 parse/repair 重试 | `Core/shared/models.py`, `Core/v2/agents/repair_agent.py` |
| 统一结构化输出 | 已有 | `Core/shared/schema.py`, `Core/shared/models.py` |
| 六类 mock 场景测试集 | 已有 | `Core/data/scenarios/*.json` |
| 独立 benchmark 项目 | 已有 | `Lab/README.md`, `Lab/run.py` |
| 预测结果 / judgement 落库 | 已有 SQLite | `Lab/store.py`, `Lab/minsight_lab.sqlite` |
| LLM judge + 聚合 summary | 已有 | `Lab/judge.py`, `Lab/results/*.json` |
| Web 控制台 | 已有，可跑 benchmark | `Lab/server.py`, `Lab/web/` |

### 3.2 部分有、但还不够“产品化”的能力

| 能力 | 当前状态 | 问题 |
|---|---|---|
| 证据回链 | `action_items` / `decisions` schema 已有 `evidence` 字段 | 还没有 UI 展示，也没有 transcript segment 跳转 |
| 参会人角色 | 已可抽出 `name + role` | 没有和会议元信息、组织通讯录、下游 assignee 映射联动 |
| 多模型路由 | 已有 `light / standard / strong` 配置设计 | 目前更偏工程能力展示，用户可感知价值还不强 |
| 评测体系 | 已有 benchmark + judge | 更像研发内测工具，不像面试时可感知的业务 demo |
| 输出结构 | JSON 很完整 | 还缺一个“给业务/面试官看”的人类可读纪要视图 |

### 3.3 现在明显还没有的能力

| 能力 | 状态 | 对应 PRD 位置 |
|---|---|---|
| 会议实体资产库（Meeting / Person / Action / Decision） | 未落地为业务存储层 | `PRD/Minsight_PRD.md` R4 |
| 跨会议检索与聚合 | 未看到业务查询入口 | R4 / 沉淀层 |
| 待办派生到任务系统 | 未落地 | R5 / R8 |
| 自动提醒 | 未落地 | R6 |
| 跨会议去重 / 冲突检测 | 未落地 | R7 |
| 数据看板（业务看板） | 未落地；当前只有 benchmark console | R9 |
| 场景化抽取模板 | 文档有规划，代码未成体系 | R10 |
| 人工纠错页 / 审核流 | 未落地 | `human_correction` 埋点仍是规划态 |
| 多生产者接入 | 目前主要是 mock transcript 输入 | R1 |
| Demo 级 transcript 上传入口 | 未落地 | Task 04 可感知体验不足 |

---

## 4. 现阶段最值得补的 Demo 方向

目标不是继续把 `Core` 做得更学术，而是让面试官 3 分钟内看懂：

1. V1 为什么不行
2. V2 为什么更可靠
3. 结果怎么进入执行闭环
4. 这不是玩具摘要器，而是中台雏形

### 推荐的 Demo 方案：做一个“结构化纪要工作台”

建议复用 `Lab/web/` 现有前端和 `SQLite`，快速补成一个业务 demo，而不是从头新开栈。

#### 页面 1：Transcript 输入页

- 输入方式：
  - 直接粘贴 transcript
  - 或选择内置 scenario
- 操作：
  - 运行 `V1`
  - 运行 `V2`
  - 对比输出

#### 页面 2：纪要结果页

- 展示四块卡片：
  - Participants
  - Key Points
  - Action Items
  - Decisions
- 每条 action / decision 展示：
  - owner
  - due
  - evidence 片段
  - 低置信 / 信息缺失标识

#### 页面 3：执行闭环页

- 把 `action_items` 生成本地 `task payload`
- 展示 mock 下游字段：
  - title
  - assignee
  - due_date
  - source_meeting
  - source_evidence
- 可选：
  - 一键“推送到飞书多维表格（mock）”
  - 实际先写 SQLite / JSON 文件也可以

#### 页面 4：跨会议视图

- 同一个 owner 的所有 action_items
- 重复 task 文本提示
- 决策反复列表

这一页可以先做规则版，不需要等语义检索。

---

## 5. 推荐补强优先级

### P0：强烈建议马上补

这些做完，整体会从“作业代码”升级到“可讲的产品 demo”。

1. **人类可读纪要视图**
   - 在 JSON 之外增加标准化 minutes 展示
   - 参考 GitHub skill：Metadata / Decisions / Action Items / Risks / Parking Lot

2. **证据回链展示**
   - 每条 action / decision 都能看到原文片段
   - 最简单版本：展示 transcript 引文文本，不必先做时间戳跳转

3. **任务派生 mock**
   - 将 action items 持久化到本地 `tasks` 表
   - 展示“会议 -> 任务”的闭环

4. **V1 vs V2 对比页**
   - 直接展示：
     - V1 漏了什么
     - V2 修复了什么
   - 面试效果非常强

### P1：推荐作为第二阶段补强

1. **跨会议重复待办检测**
   - 先用规范化文本 + owner + 时间范围做规则检测
2. **决策反复清单**
   - 用 `supersedes` 字段形成“历史决策 -> 当前决策”链
3. **模板化抽取**
   - 至少做两种模板：
     - `decision_meeting`
     - `standup`
4. **人工复核入口**
   - 对 `due is null`、`owner missing`、`evidence empty` 标红

### P2：更长期、可写进文档但不必这轮实现

1. 多生产者接入
2. 飞书真实 API 对接
3. 自动提醒
4. 私有化部署故事线
5. 语义级冲突检测

---

## 6. 建议另一个会话优先实施的具体任务

为了降低并行协作成本，建议按下面顺序做。

### 任务 A：补一份业务 demo 文档

建议更新：

- `PRD/Minsight_PRD.md`
- 或新建 `docs/demo-story.md`

要补的内容：

- demo 入口
- 用户操作路径
- 页面结构
- 演示脚本
- 每页想证明什么价值

### 任务 B：补一个业务视角前端

优先复用：

- `Lab/server.py`
- `Lab/web/index.html`
- `Lab/web/app.js`

建议新增：

- transcript 输入模式
- 结构化纪要结果卡片
- action task mock 列表
- benchmark 视图与业务视图切换

### 任务 C：补一个轻量资产层

最小可行实现：

- 继续使用 SQLite
- 新增：
  - `meetings`
  - `meeting_actions`
  - `meeting_decisions`
  - `derived_tasks`

目的不是追求完美建模，而是把“沉淀层”和“派生层”演示出来。

### 任务 D：补规则版跨会议检测

先实现两个最小规则：

1. 同 owner + 相似 task -> 标记 `possible_duplicate`
2. 同主题 decision + `supersedes` -> 标记 `decision_reversal`

### 任务 E：补证据展示

最小可行实现：

- 把 `evidence` 当纯文本展示
- 若未来 transcript 支持 segment id，再升级为点击跳转

---

## 7. 一句话判断：哪些功能已经有了，哪些最值得补

### 已经有了

- V1/V2 抽取器
- LangGraph 编排
- schema 校验
- repair 回环
- mock 场景测试集
- benchmark + judge + SQLite + Web 控制台

### 最值得补

- 业务视角纪要页
- 证据回链展示
- 任务派生 mock
- 跨会议重复 / 冲突检测轻量版
- 面向面试讲解的 V1 vs V2 对比演示

---

## 8. 推荐给下个会话的实施目标

如果只能选一个目标，建议定成：

> **把当前 Minsight 从“抽取器 + benchmark”补成“可演示的会议结构化工作台”**。

最小验收标准：

- 可输入 transcript 或选择 mock case
- 可运行 V2 并展示结构化结果
- 可看到 evidence
- 可生成 mock tasks
- 可查看至少一种跨会议提示（重复待办或决策反复）
- 可与 V1 做可视化对比

达到这个标准后，这个作业的故事会完整很多。

---

## 2026-07-18 补充：当前 Demo 与 Benchmark 口径

### 已落地的演示闭环

当前 `Minsight` 已经从“V1/V2 抽取器 + Lab benchmark”补强为一个可演示的会议结构化工作台：

- `Workbench` 支持粘贴 transcript 或选择 mock case。
- 工作台业务演示只运行 V2，不再每次跑 V1。
- V2 输出会渲染为人类可读纪要，而不是只展示 JSON。
- 每条 `action_item` 和 `decision` 可以展示 evidence 原文片段。
- `action_items` 会派生为本地 mock tasks，形成“会议纪要 -> 待办”的执行闭环。
- SQLite 额外沉淀 `meetings / meeting_actions / meeting_decisions / derived_tasks`。
- 已有规则版跨会议提示：重复待办、决策反复。
- `Benchmark` 改为正式 Agent 回归评测，用于量化每次迭代相对上一次同任务的提升或下降。

### 当前 6 个 benchmark 基准

测试数据位于 `Core/data/scenarios/*.json`，每个 case 都包含 `transcript / complexity_tags / alias_map / gold`。
`gold` 是人工标准答案，包含：

- `participants`
- `key_points`
- `action_items`
- `decisions`

当前 6 个场景及测试目的：

| 场景 | 主要测试点 |
|---|---|
| `decision_reversal` | 新决策覆盖旧决策，是否正确识别 `supersedes`。 |
| `long_meeting` | 长上下文、多议题、排除项和后置更正。 |
| `missing_fields` | 负责人/截止时间隐含或缺失时，是否避免幻觉补全。 |
| `mixed_language` | 中英混合、英文产品术语和 scope 裁剪。 |
| `multi_topic` | 多主题混杂、parking lot、共享 owner、非决策过滤。 |
| `nickname_reference` | 昵称映射、代词指代、客户侧人员与内部 owner 区分。 |

### 百分比评分如何产生

当前不使用语义相似度，也不调用 embedding 模型 API。
Lab 使用 `LLM judge`：

1. 同一条 case 运行正式 Minsight Agent。
2. 每条预测结果连同 `case_id / scenario / transcript / gold / output / routing` 落入 SQLite。
3. Lab 从库中读取预测结果，把 `transcript + gold + prediction` 填入固定 judge prompt。
4. judge 返回 `participants / key_points / action_items / decisions / overall` 五个 `0.0 ~ 1.0` 小数。
5. 前端把小数乘以 100 显示为百分比。
6. 多 case 时，同一版本同一维度做简单平均。
7. 若存在上一次同 scenario/case 的 V2 结果，则计算 current-minus-previous 分差并在前端热力图展示。

因此，页面上的 `67.5%` 这类结果表示：

> 强模型评委认为该版本输出在对应维度上，与人工 `gold` 标准答案的匹配程度约为 0.675。

这个指标适合用于 demo、回归观察和 prompt/agent 迭代方向判断；它不是完全确定性的规则指标，judge 模型可能存在小幅波动。
