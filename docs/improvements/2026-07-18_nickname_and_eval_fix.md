# 改进建议：nickname_reference 参会人骤降 + 评测口径不稳

> 交接对象：负责改代码的 agent。本文给出根因、按优先级排好的改进项、要改的具体文件、改法与验收标准。**照做即可，无需重新诊断。**

## 0. 现象

- 对比 run：本次 `323e0f3e` vs 上次 `122e6dde`，case `nick_01`（scenario=`nickname_reference`）。
- 参会人 70% → 10%（-60pp），待办 -5pp，总体 70% → 55%（-15pp）。

## 1. 冒烟证据（先看这个，别追"幻觉式回归"）

两次 run 的**参会人输出几乎完全相同**（都是昵称，只有 role 措辞不同）：

- `122e6dde`：`老板 / 二哥 / 花花 / 小林` → judge 打 **0.7**
- `323e0f3e`：`老板 / 二哥 / 花花 / 小林` → judge 打 **0.1**

名字完全一样，分数却 0.7↔0.1 → **这 -60pp 主要是 LLM judge 不稳定，不是模型退步。**（judge 温度已是 0，但整体式打分对措辞极敏感，宁严勿松时严了。）

## 2. 根因（4 条）

- **A. 名册未接入（最致命）**：`nick_01` 的 case 里**有真名名册** `alias_map = {"老板":"韩越","二哥":"周强","花花":"花敏","小林":"林舟"}`，但 `NormalizeAgent.run()` 只把 `transcript` 喂给模型，还要求模型"自己从转写里产出 alias_map"。转写里**根本没有真名**，且 `Core/prompts/v2/normalize.txt` 明确写"确定不了真名就用称呼本身"、few-shot 输出也是昵称→昵称。→ 模型只能输出昵称，永远对不上 gold 的真名。owner 也因此全是昵称。
- **B. LLM judge 不稳定**：客观维度（参会人姓名、owner、due、格式合法）也交给整体式 judge 打分，跨 run 噪声大（见 §1）。
- **C. 相对日期未归一**：gold 里"向林舟提供客户白名单"due=`2026-07-18`（今天），V2 输出 `null`。原因：actions agent **没拿到会议参考日期**，无法把"今天/下周三"换算成绝对日期。
- **D. 决策过抽（冗杂）**：gold 只有 1 条决策，V2 抽了 5 条，把老板的**指令/否定/澄清**（"要正式 demo 不要录屏""不发问卷""折扣未定""发票不写待办"）都当成了决策。

---

## 3. 改进项（按实施顺序）

### P0-1 · 客观维度改"规则精确匹配"，judge 只评语义（修 B）

**目标**：让参会人/owner/due/格式这些客观维度分数**可复现、可解释**，不再被 judge 噪声左右。

**改动文件**
- 新增 `Lab/metrics.py`（规则打分）。
- `Lab/runtime.py`：评分处改为"规则分 + judge 分"组合。
- `Lab/judge.py` / `Lab/prompts/judge.txt`：judge 只负责 `key_points` 与 `decisions` 两个语义维度。
- 前端 `Lab/web/app.js` 展示的维度键名（participants/key_points/action_items/decisions/overall）**保持不变**，只改分数来源。

**改法**
- 规则分（对 gold 精确比对）：
  - `participants`：姓名集合 F1（**用 case 的 `alias_map` 做别名归一后再比**，即预测里的昵称先映射成真名再与 gold 姓名集合比），role 正确率作为次要项。
  - `action_items`：任务用文本重叠贪心匹配；配对后算 owner 正确率（同样先经 alias 归一）、due 精确匹配（`null==null` 也算对，gold 为 null 但预测给值 = 幻觉扣分）。
  - `format_valid`：schema 是否通过。
- 语义分（保留 judge，temp 0、固定 prompt）：`key_points`（覆盖/失真）、`decisions`（最终结论 + supersedes 是否正确）。
- `overall`：客观维度用规则分、语义维度用 judge 分，加权汇总。

**验收**
- 同一份预测重复评测多次，客观维度分数**完全不变**。
- 参会人分数可解释为"真名集合匹配率"，而非黑盒。

### P0-2 · 把"名册"接入 normalize / actions（修 A）

**目标**：昵称→真实身份用 case 名册归一；生产语义上，这份名册来自**日程邀请/组织通讯录的参会名单**，演示里就用 `case["alias_map"]`。

**改动文件**
- `Core/v2/agents/normalize_agent.py`：`run()` 把 `case.get("alias_map")` 作为 roster 传入 prompt。
- `Core/prompts/v2/normalize.txt`：新增 `{{ROSTER}}` 占位符；指令改为"**用给定名册把说话人称呼映射到真实姓名**；名册里有的必须用真名"；**改掉 few-shot**（当前教昵称→昵称，要改成昵称→真名）；保留"名册里没有的人才可用称呼本身"。
- `Core/v2/agents/actions_decisions_agent.py`：owner 归一用**权威名册**（`case["alias_map"]` 优先，normalize 产出的作补充）。
- `Core/prompts/v2/actions_decisions.txt`：`{{ALIAS_MAP}}` 传入的应是权威名册。
- `Core/v2/graph.py`：把 roster 从 `state["case"]` 贯穿给两个 agent。
- `Lab`：确认 case 透传时 `alias_map` 未被丢弃；建议在 `predictions` 落库时也存一份 `alias_map`（便于评测端做别名归一，配合 P0-1）。

**注意**
- 这是"**补上本该有的上下文**"，不是放宽 gold、更不是作弊：真实产品一定有参会名单。
- 名册缺失时保留"可用称呼"回退，别硬编。

**验收**
- `nick_01` 参会人输出为 `韩越 / 周强 / 花敏 / 林舟`；action owner 归一为真名。

### P1-1 · 相对日期归一（修 C）

**目标**："今天/明天/下周三"能换算成绝对日期。

**改动文件**
- 场景数据 `Core/data/scenarios/*.json`：给每个 case 增加 `meeting_date` 字段（`nick_01` 应为 `2026-07-18`，因为 gold 把"今天"标成了该日期）。
- `Core/v2/agents/actions_decisions_agent.py`：把 `case.get("meeting_date")` 传入 prompt。
- `Core/prompts/v2/actions_decisions.txt`：新增 `{{MEETING_DATE}}` 占位符；规则改为"**以会议日期为基准把相对日期换算成 ISO 绝对日期**，无法换算才 `null`"；加正反 few-shot（今天→具体日期）。

**验收**
- `nick_01`："向林舟提供客户白名单" due=`2026-07-18`；"安排客户培训" due=`2026-08-05`。

### P1-2 · 收紧决策定义（修 D）

**目标**：只保留实质性最终结论，不再把指令/否定/澄清当决策。

**改动文件**
- `Core/prompts/v2/actions_decisions.txt`：决策部分显式排除——① 指令类（"要/不要做 X"）；② 否定与禁止（"不用录屏""不发问卷"）；③ 状态澄清（"财务已处理""发票不写待办"）；④ 未定事项（"折扣未定"）。只保留**改变状态 / 责任归属 / 明确选定方案**的正向最终结论；加正反 few-shot。

**验收**
- `nick_01` 决策 = **1 条**（商务对接归周强、培训归花敏、API demo 归林舟），不再出现"不要录屏/不发问卷/发票"这类条目。

---

## 4. 实施顺序

1. **P0-1**（让分数先可信，否则改抽取无法判断是否变好）
2. **P0-2**（修最致命的真实根因）
3. **P1-1、P1-2**

每改一步：先跑 `nick_01` 定点验证，再跑全场景回归对比。

## 5. 全局验收清单

- [ ] 客观维度分数可复现（同预测重复评测不漂移）。
- [ ] `nick_01`：参会人 & owner = 真名；"今天"类 due 归一为 `2026-07-18`；决策 = 1 条。
- [ ] 全场景总体分**不回退**（重点看 `decision_reversal`、`missing_fields`、`multi_topic` 未被 P1-2 误伤）。
- [ ] `Lab/tests` 全绿。

## 6. 红线（别踩）

- **不要为提分而放宽 gold**；名册接入是补上应有上下文，不是改答案。
- judge **保留但降权**：只评语义维度，客观维度以规则为准。
- 保持 pydantic 契约：owner 必填、due 缺失置 `null`、只输出 JSON。
- 改 prompt 注意 `{{...}}` 占位符 + `str.replace` 渲染，别破坏"只输出 JSON"。
