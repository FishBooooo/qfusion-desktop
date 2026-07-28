# 架构决策日志

最后更新：2026-07-27

本日志只登记重要决策及状态；完整背景和后果写入对应 ADR。任何改变核心方向的提议都必须先获得确认，再新增或替代 ADR。

| ADR | 决策 | 状态 | 日期 |
| --- | --- | --- | --- |
| [0001](adr/0001-local-lite-storage.md) | Local Lite 使用 SQLite + DuckDB + Parquet + Raw Store | Accepted | 2026-07-27 |
| [0002](adr/0002-tauri-fastapi-sidecar.md) | 桌面端采用 Tauri 2 + FastAPI Sidecar | Accepted | 2026-07-27 |
| [0003](adr/0003-independent-model-isolation.md) | 三套独立模型使用能力受限输入和隔离运行边界 | Accepted | 2026-07-27 |
| [0004](adr/0004-versioned-fusion-packet.md) | 融合只接收版本化、验证后的 Fusion Packet | Accepted | 2026-07-27 |
| [0005](adr/0005-cache-first-llm-budget.md) | LLM 使用缓存优先、模式化开关和硬预算 | Accepted | 2026-07-27 |
| [0006](adr/0006-project-local-toolchains.md) | 开发工具链、依赖缓存和子进程环境全部限制在项目内 | Accepted | 2026-07-27 |

## 状态定义

- `Proposed`：待评审，不能作为实现依据。
- `Accepted`：当前实现必须遵循。
- `Superseded`：已由新 ADR 替代，但保留历史。
- `Rejected`：评审后不采用。
