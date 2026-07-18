# 项目工作约定与交付物索引（Minsight）

## 背景
飞书 AI 工程师岗位作业：会议转写文本 → 结构化会议纪要，优化同事的 V1，产出 V2 与可运行原型。
产品定位：**Minsight**（会议纪要 Agent 中台，上游会议软件 → 结构化沉淀 → 下游多维表格等，自带数据看板）。

## 工作约定（重要，长期遵守）
- **聊业务 → 更新业务文档**：`PRD/Minsight_PRD.md`（定位、竞品、需求、场景、功能、看板等）。
- **聊技术 → 更新技术文档**：`PRD/V1诊断与V2方案_Task02_03_05.md`（V1 诊断、V2 架构、模型路由、prompt、评测、工程落地等）。
- 每次讨论有结论就分类沉淀进对应文档，不要让聊天白白浪费。
- 代码规范：**注释/文档用中文，代码标识符与程序打印/返回值用英文**；会议转写与 gold 属业务数据，保持中文。

## 交付物索引
- `PRD/Minsight_PRD.md` —— 业务文档（PRD）。
- `PRD/V1诊断与V2方案_Task02_03_05.md` —— 技术文档（Task 02/03/05）。
- `Core/` —— 抽取核心（Task 04）。V1、V2 两个独立项目 + shared/prompts/data。
  - Core 用于查看 V1 / V2 抽取结果：配 `.env` 后运行 `python run.py --version v2 --scenario decision_reversal`。
  - 三档模型 `light/standard/strong` + 按 Agent 路由，全部 `.env` 配置，不写死厂商/模型。
  - 提示词在 `prompts/*.txt`，可配置。V2 有纯代码版与 LangGraph 版。
- `Lab/` —— 独立测评项目：运行 V1 / V2、落库、用 LLM judge 打分，并提供可视化前端。

## 作业五个 Task 落点
Task01 场景 → PRD；Task02 诊断 / Task03 改进 / Task05 优化+评测 → 技术文档；Task04 原型 → `Core/`。
