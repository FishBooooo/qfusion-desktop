# API Contracts

`openapi.json` 由后端应用通过 `scripts/export_openapi.py` 生成。不要手工编辑生成结果。

更新流程：

```bash
uv run python scripts/export_openapi.py
pnpm generate:client
```

M0 只有健康检查契约。金融数据和模型契约将在对应里程碑通过 Pydantic、JSON Schema、迁移和测试一起引入。
