# V2 Structured Extraction

V2 现在统一为 LangGraph 工作流实现，核心 agent 位于 `agents/` 目录：

- `normalize_agent.py`
- `key_points_agent.py`
- `actions_decisions_agent.py`
- `repair_agent.py`
- `validation_agent.py`

运行方式：

```bash
python v2/run.py --scenario decision_reversal
```

运行前需要先在 `Core/.env`、仓库根目录 `.env` 或 `Lab/.env` 中配置可用的真实 LLM profile。
