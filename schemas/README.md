# Versioned financial schemas

M0 只生成 HTTP OpenAPI 契约。`AnalysisSnapshot`、`ModelResult`、`FusionPacket` 和 `TradePlan` 的正式 JSON Schema 属于后续里程碑，必须与 Pydantic 类型、迁移和契约测试一起引入，不能先放置未经验证的占位 Schema。
