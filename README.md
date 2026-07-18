# Minsight · 会议纪要 Agent 中台

把杂乱的会议转写，变成**结构化、可执行、可追溯**的会议资产：参会人、讨论要点、待办（含负责人与截止时间）、决策结论，并为每条结论回链原文证据。

Minsight 由两个相互独立的项目组成：

- **`Core/`** —— 抽取引擎。单次调用的 **V1 基线** 与基于 LangGraph 多 Agent 的 **V2 工作流**。
- **`Lab/`** —— 独立测评与演示项目。运行正式 Minsight Agent、结果落库（SQLite）、用强模型做 LLM judge 打分，并提供可视化前端（工作台 + 回归评测两个视图）。

> 背景：本项目源于「会议转写 → 结构化会议纪要」的工程实践——诊断同事的 V1、产出改进后的 V2 与可运行原型，并配套评测闭环。

---

## 亮点

- **V1 → V2 的架构演进**：把 V1 的「一个 prompt + 单次调用 + `json.loads`」拆成可编排、可校验、可观测的多阶段流水线。
- **Workflow 主干 + 多专家 Agent**：V2 用 LangGraph `StateGraph` 编排，`normalize →（key_points ∥ actions_decisions）→ validate → END`，并行分叉 + 汇聚 + 校验自修复。
- **三档模型路由**：`light / standard / strong` 三档，按 Agent 路由，全部由 `.env` 配置，**不写死任何厂商/模型**（OpenAI 兼容协议，可对接主流模型服务）。
- **结构化输出契约**：V2 用 pydantic 把 schema 与业务规则声明成显式契约（待办缺截止时间如实置空、负责人必填），校验失败带错误消息走自修复。
- **可配置提示词**：所有 prompt 外置到 `Core/prompts/`，按 v1/v2 项目隔离，改文件即可调优，无需动代码。
- **评测闭环**：结果落库 + 强模型 LLM judge 逐维度打分，支持逐条用例复盘与跨运行对比。
- **可视化前端**：工作台（业务演示：可读纪要、证据、派生待办、跨会议提醒）+ 基准评测（版本得分、历史运行、逐条评审）。

---

## 目录结构

```
Minsight/
├── Core/                 # 抽取引擎（不含评测/演示编排）
│   ├── v1/               #   单次调用基线
│   ├── v2/               #   LangGraph 工作流（agents/ + graph.py）
│   ├── shared/           #   模型路由 / prompt 渲染 / schema / 场景加载
│   ├── prompts/          #   提示词（按 v1、v2 项目隔离）
│   ├── data/scenarios/   #   样例会议与 gold 数据（Lab 复用）
│   └── run.py
├── Lab/                  # 独立测评 + 演示
│   ├── server.py         #   HTTP API + 静态前端
│   ├── runtime.py        #   基准运行生命周期
│   ├── store.py          #   SQLite 存储
│   ├── judge.py          #   LLM judge 打分
│   ├── web/              #   前端（工作台 / 基准评测）
│   └── tests/            #   针对三个公共接缝的自动化测试
├── .env.example          # 模型配置模板
└── README.md
```

---

## 快速开始

### 1. 配置模型

复制 `.env.example` 为 `.env`，至少配置一个可用的模型档位（OpenAI 兼容接口，填各自的 `base_url / api_key / model`）：

```bash
cp .env.example .env
# 编辑 .env，填写 LLM_LIGHT_* / LLM_STANDARD_* / LLM_STRONG_*
```

三档与 Agent 路由：

| 档位 | 用途 | 默认承担的 Agent |
|---|---|---|
| `light` | 轻量、最便宜快 | 说话人/角色归一、校验自修复 |
| `standard` | 中档均衡 | 要点抽取 |
| `strong` | 强推理 | 待办 + 决策、V1 基线、Lab judge |

每个 Agent 通过 `.env` 的 `AGENT_<NAME>=<profile>` 指定用哪个档位，即「哪个模型用在哪个 Agent 上」。

### 2. 跑抽取引擎（Core）

```bash
cd Core
pip install -r requirements.txt
python run.py --version v2 --scenario decision_reversal   # 跑 V2
python run.py --version v1 --scenario decision_reversal   # 跑 V1 基线
```

### 3. 启动测评 + 前端（Lab）

```bash
cd Lab
pip install -r requirements.txt
python server.py
# 打开 http://127.0.0.1:8787
```

默认进入「工作台」视图，第二个是「基准评测」视图。也可只跑基准 CLI：

```bash
python run.py --scenario decision_reversal
```

---

## 前端界面

- **工作台（Workbench）**：粘贴转写或选择样例会议 → 直接跑 V2 并与 V1 并排对比 → 展示可读纪要、每条待办/决策的原文证据、派生待办与跨会议重复提示。
- **基准评测（Benchmark）**：对共享场景集跑 V1/V2 → 预测落库 → 用 LLM judge 逐维度打分 → 版本得分汇总、历史运行归档、逐条用例评审。

前端为纯静态页面（`Lab/web/`），通过 `Lab/server.py` 的 `/api/*` 与后端交互。

---

## 评测

`Lab` 把「抽取 → 落库 → 从库评测」解耦：

- 预测与 gold 都进 SQLite（`Lab/minsight_lab.sqlite`），评测是一次库内比对，可复现、可跨运行对比。
- **LLM judge**（强模型、固定 prompt、低温）对参会人 / 要点 / 待办 / 决策各维度打分，并给出优点与问题。
- 每次运行的汇总落到 `Lab/results/<run_id>.json`。

---

## 测试

```bash
cd Lab
python -m unittest discover -s tests -v
```

覆盖三个公共接缝：HTTP API、基准运行时、SQLite 存储（含工作台会议资产的持久化）。

---

## 设计要点（约定）

- **Core 专注抽取接缝，Lab 专注评测接缝**，两者解耦，仅通过公开的抽取入口与共享场景/模型工具连接。
- V2 不再保留离线模拟或纯代码回退，`Core/v2/graph.py` 是唯一编排入口。
- 代码规范：**注释/文档用中文，代码标识符与程序打印/返回值用英文**；会议转写与 gold 属业务数据，保持中文。

## 当前基准评测口径

- `Core/v1/` 保留为归档 baseline，不删除，但不再进入 Lab 的新 benchmark 数据流。
- `Core/v2/` 是正式 Minsight Agent 的实现主体，后续迭代都围绕这条 LangGraph workflow 进行。
- Lab benchmark 每次只运行正式 Agent，并把当前 run 的 V2 分数与“上一次同 scenario/case 的 V2 分数”对比。
- 前端会在逐 case 详情中展示热力图：绿色代表本次提升，红色代表本次下降，灰色代表持平。
- 旧库里已经跑过的 V1 记录可以留作历史档案；新运行不再产生 V1 预测或 V1 得分。
