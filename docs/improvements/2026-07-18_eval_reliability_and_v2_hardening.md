# 交接规格：评测可信度 + V2 工作流硬化 + 评测轴扩展

> 交接对象：改代码/标注的 agent。三条工作流（W1/W2/W3）+ 明确优先级。**照做即可，不必重新诊断。**
> 一句话排序：**先让 benchmark 可信（W1），再改工作流（W2），再扩评测轴（W3）**——工作流改得好不好要靠 benchmark 判断，benchmark 不可信就是在对噪声调参。

## 0. 证据（为什么要做）

- `nick_01`：决策**过抽**（gold=1，模型抽 5，把指令/否定当决策）。
- `real_01`（real_world_kickoff，2 万字长会）：决策**漏抽**（gold=6，模型只抽 2，judge=0.4）；要点**粒度不匹配**（gold 7 条细，模型 4 条粗，judge=0.75）。
- **gold 自相矛盾**：`real_01` 把"降优先级/暂不做/不上云"这类排除性表述**算决策**；`nick_01` 却把排除/否定**不算决策**。同一类表述两套标准 → 语义维度分数不可信。
- 工作流现状：`normalize →（key_points ∥ actions_decisions）→ validate → END`，每个 agent **对整篇转写单次调用**，无分段/无 map-reduce/无完整性自检；`meeting_info.attendees`（名册）与 `meeting_info.date`（会议日期）**每个场景都有但工作流没用**。
- 评测现状：客观维度（参会人/owner/due/格式）也全交 LLM judge，噪声大；无"证据忠实度""跨会议""负样本"任何一条测试轴。

## 优先级总览

| 工作流 | 内容 | 优先级 | 依赖 |
|---|---|---|---|
| **W1** | 标注规范（rubric）+ 回审修 gold（修决策口径矛盾） | **P0（最先）** | 无 |
| **W1.5** | 客观维度改规则匹配、judge 只评语义 | **P0（与 W1 并行）** | 见既有 spec `2026-07-18_nickname_and_eval_fix.md` |
| **W2** | V2 工作流硬化（map-reduce / 完整性自检 / 注入名册+日期 / 决策两步 / 证据校验） | **P1** | W1、W1.5（否则无法判断是否变好） |
| **W3a** | 证据忠实度 + 负样本 precision 测试轴 | **P1**（便宜、高价值） | W1 |
| **W3b** | 跨会议去重/冲突测试轴 | **P2**（重、依赖该功能落地） | 跨会议功能 |

---

## W1 · 标注规范 + 回审修 gold（P0，最先做）

**目标**：给出一份统一的 annotation rubric，并按它回审现有 gold，消除决策/要点的口径矛盾。没有这步，后面所有语义维度分数都不可信。

**为什么最先**：W2 的工作流改动、W3 的新测试，都要靠 benchmark 判断成效；gold 口径飘，benchmark 就是噪声。

**改哪些文件**
- 新增 `docs/annotation_rubric.md`（标注规范）。
- 回审并修订 `Core/data/scenarios/*.json` 的 `gold`（重点 `nickname_reference.json` 与 `real_world_kickoff.json` 的 `decisions`）。

**怎么改 —— rubric 至少定死四件事（每条都要带正反例）**
1. **决策边界**（矛盾的根源，必须选一个口径全库统一）。推荐口径：
   > 决策 = 会议对某**议题**作出的、会**改变后续行动**的实质性结论。**包含**：选定方案、确定优先级/排序、暂缓/搁置、明确排除某做法（"不做 X"）。**不包含**：个人即时指令且未上升为议题共识、单纯状态澄清（"财务已处理"）、尚在讨论未拍板的提议。
   - 依据：`real_01` 这种需求会，核心产出就是"优先级 + 排除"，若不算决策则会议几乎无产出、严重失真 → 采纳"排除/优先级/暂缓算决策"。
   - 回审动作：`real_01` 的 6 条决策按此**保留**；`nick_01` 逐条复核——议题级、影响后续行动、有共识的**算**；老板一句话的即时指令/澄清（"发票不写待办"）**不算**。把判定标准写进 rubric，让两者不再打架。
2. **要点粒度**：每议题一条主要点；关键业务约束（成本/边界/时效）单列；给一个"每会大致条数量级"参考，避免"4 粗 vs 7 细"漂移。
3. **待办边界**：有明确交付物且可指派 owner 才算；纯职责表述（"商务我负责"）不算待办。
4. **evidence 要求**：必须是转写的**真实片段**（可定位子串），最短且足够支撑该条结论。

**验收**
- rubric 每条规则都有 include/exclude 正反例。
- 任取两个含"排除/降优先级"表述的 case，决策标注口径一致（`nick_01` 与 `real_01` 不再矛盾）。
- 回审后重跑 benchmark，决策/要点分数的跨 run 波动明显收窄。

---

## W1.5 · 客观维度改规则匹配（P0，与 W1 并行）

见既有交接 `docs/improvements/2026-07-18_nickname_and_eval_fix.md` 的 P0-1：参会人/owner/due/格式用规则对 gold 精确匹配（别名归一后比），LLM judge 只评 `key_points` 与 `decisions` 两个语义维度。此处不重复，随 W1 一起落地。

---

## W2 · V2 工作流硬化（P1）

**目标**：把"单次全文抽取"升级为可分段、可 map-reduce、可自检的流水线，治长会漏抽与粒度漂移，并补上名册/日期输入契约。

**目标图**
```
segment（分段去噪）
  → normalize（注入名册 attendees）
    →（key_points: map→reduce  ∥  actions_decisions: map→reduce）
      → merge / 时序·优先级消解
        → verify（完整性 + 证据忠实度自检，缺则回补）
          → validate（契约/规则）→ END
```

**改哪些文件**：`Core/v2/graph.py`、`Core/v2/agents/*.py`（新增 `segment_agent.py`、`verify_agent.py`）、`Core/prompts/v2/*.txt`（新增 `segment.txt`、`verify.txt`，改 `key_points.txt`、`actions_decisions.txt`、`normalize.txt`）、`Core/shared/models.py`（如加 confidence 字段）。数据侧**无需改**（`meeting_info` 已含 attendees/date）。

**逐项（按内部优先级）**
- **W2-a｜要点/决策 map-reduce（最先，治 real_01 漏抽）**：加 `segment` 节点把长转写按议题/窗口切块（短会可跳过，退化为单次）；`key_points`、`actions_decisions` 对每块 map，再 reduce 合并去重 + 时序/优先级消解。
- **W2-b｜完整性自检节点 `verify`**：合并后加一次轻量 LLM 自检——"每个被明确拍板/降级/排除/选定的议题，是否都在 decisions 里？"，发现缺口定向回补。控成本：只对长会或低置信触发。
- **W2-c｜注入名册 + 会议日期（零数据改动）**：`normalize_agent`/`actions_decisions_agent` 把 `case["meeting_info"]["attendees"]`（`display_name→name` 名册）和 `case["meeting_info"]["date"]` 作为 ground-truth 传进 prompt（新增 `{{ROSTER}}`、`{{MEETING_DATE}}` 占位符）。→ 一并根治"昵称→真名"与"今天→绝对日期"两个老根因。改 `normalize.txt`：用名册归一，别再"凭空造真名/回退昵称"。
- **W2-d｜决策两步：广召回 → 判定过滤**：先尽量全召回候选决策（含排除/降级/选定），再按 **W1 rubric** 过滤"是否算最终决策"。召回与精度分开调，同治 `nick_01` 过抽与 `real_01` 漏抽。**依赖 W1 的 rubric。**
- **W2-e｜证据忠实度校验 + 置信度路由**：`validation_agent` 里校验每条 evidence 能在转写定位（真实子串），不通过则重抽；每条结论带 `confidence`，低置信升 `strong` 档重抽或标人工复核。

**成本控制**：map-reduce/自检增加调用——用分段并行 + 只对长会启用自检 + 低置信才升档。

**验收**
- `real_01`：决策召回明显上升（接近 gold 的议题级决策数），要点粒度贴近 rubric。
- `nick_01`：决策不再过抽（贴合 rubric）；参会人/owner 为真名。
- 相对日期："今天"类归一为绝对日期。
- 全场景总体不回退；`Lab/tests` 全绿。

---

## W3 · 评测轴扩展（贴合 PRD/路线图）

现有 benchmark 只测"单会抽取质量"，没测 PRD 的核心价值。按价值/成本补三条轴。

**W3a｜证据忠实度（P1，便宜高价值）**
- 改 `Lab/`（新增/扩展 `Lab/metrics.py`）：对每条 action/decision 的 `evidence` 做**真实子串/模糊匹配**校验，`evidence_faithfulness = 命中数/总数`，作为独立维度或并入可信度。judge 不再负责这条（客观可复现）。
- 验收：臆造 evidence 的条目能被稳定判低分。

**W3b｜负样本 / 空会 precision（P1）**
- 新增场景 `Core/data/scenarios/low_signal.json`：几乎无实质产出的闲聊会，gold 的待办/决策接近空。
- 评测：加 precision 口径（臆造条目扣分），补上现在只测召回、不测精度的缺口。
- 验收：模型在空会上不再幻觉待办/决策。

**W3c｜跨会议去重/冲突（P2，重、依赖功能）**
- 设计（先出方案，不急落地）：多会议 fixture（同一待办跨会重复、本次决策推翻上次会决策）；Lab 侧按序跑一串会议，校验去重/冲突输出。
- 依赖：跨会议检测功能需先从 demo-only 变成可评测能力。这是路线图 V3 的重点，故标 P2。

---

## 红线（别踩）
- **不要为提分放宽 gold**；W1 是统一口径、补应有上下文，不是改答案。
- judge 保留但**降权**：只评 `key_points`/`decisions` 语义维度，客观维度以规则为准。
- 保持 pydantic 契约：owner 必填、due 缺失置 `null`、只输出 JSON。
- 改 prompt 注意 `{{...}}` 占位符 + `str.replace` 渲染，别破坏"只输出 JSON"。
- W2 的分段/自检要有**短会短路**与**成本开关**，别让每场会都翻倍烧 token。
