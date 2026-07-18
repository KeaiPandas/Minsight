# V1 单次调用基线

V1 保持题目中的 naive 实现思路：

1. 拼接一个会议纪要 prompt
2. 单次调用 LLM
3. 直接 `json.loads(response)`
4. 不做 schema 校验、repair、证据补全或字段归一化

```bash
python v1/run.py --scenario decision_reversal
```

运行前需要在 `Core/.env` 配置真实 LLM profile。项目已移除离线模拟链路。

## 已知缺陷

- 输出只要带 Markdown code fence 或解释性文字，`json.loads` 就会失败。
- 四类信息混在一次 prompt 中，长转写更容易漏抽。
- 没有说话人归一化，参会人、负责人可能使用昵称或角色名。
- 没有 evidence 字段，无法追溯待办和决策来自哪句原文。
- 没有 repair 回环，格式失败会直接暴露为抽取错误。

这些缺陷是 V2 LangGraph 多 agent 工作流需要解决的问题。
