# Versioned financial schemas

M1 从 Pydantic 领域类型生成并提交确定性的 JSON Schema。禁止手工维护与运行时类型分离的
第二份契约。

当前正式契约：

- `analysis_snapshot.schema.json`：三套独立模型共享的不可变
  `AnalysisSnapshot` 输入；
- `data_source_record.schema.json`：带来源、时间、修订、质量、版本与原始载荷哈希的
  Point-in-Time 事实包装。

重新生成：

```bash
./scripts/run_in_qfusion_env.sh uv run --locked python scripts/export_domain_schemas.py
```

CI 会重新生成并要求工作树无差异。任何契约字段变更都必须同步更新 Pydantic 验证、Schema、
契约测试、数据模型文档，并在引入物理数据库表时附带迁移。本阶段尚未创建数据库 Schema。
