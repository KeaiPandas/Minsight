# prompts/

提示词按项目目录隔离存放：

```text
prompts/
├── v1/
│   └── v1_all.txt
└── v2/
    ├── normalize.txt
    ├── key_points.txt
    ├── actions_decisions.txt
    └── repair.txt
```

- `v1/extractor.py` 调用 `render("v1", ...)`。
- `v2/agents/*.py` 调用 `render("v2", ...)`。
- 修改某一套 prompt 时，只会影响对应项目，不会串到另一套链路。
