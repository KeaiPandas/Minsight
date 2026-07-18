# prompts/

`prompts/` 存放 V2 agent 使用的提示词模板。

```text
prompts/
├── v1/
│   └── v1_all.txt        # 历史保留；当前 V1 为题目式内联 prompt
└── v2/
    ├── normalize.txt
    ├── key_points.txt
    ├── actions_decisions.txt
    └── repair.txt
```

- `Core/v1/extractor.py` 现在刻意使用内联 prompt，保持“单次调用 + json.loads”的基线实现。
- `Core/v2/agents/*.py` 继续通过 `shared.prompts.render("v2", ...)` 加载模板。
- 修改 V2 某个 prompt 只影响对应 agent，不影响 V1 baseline。
