# ADR-0001：Local Lite 存储组合

- 状态：Accepted
- 日期：2026-07-27

## 背景

桌面应用必须离线可用、默认不依赖 Docker，并同时处理低容量应用状态和高容量分析数据。单一数据库难以同时满足简单迁移、列式分析、原始证据保留和 Windows 本地部署。

## 决策

Local Lite 使用：

- SQLite：设置、观察池、运行索引、风险、报告、模拟订单和审计；
- DuckDB + Parquet：行情、特征、预测、期权快照和回测；
- 本地 Raw Store：供应商原始响应、公告、新闻、财报和内容哈希。

Domain 只依赖 Repository Interface。DuckDB 和 Parquet 使用单写入队列。数据写入 `%LOCALAPPDATA%\QFusion\`，不写入安装目录。

## 后果

优点：

- 无需常驻数据库服务；
- 离线可读；
- 适合列式分析与可移植备份；
- 后续可通过 Repository 实现增加 PostgreSQL/TimescaleDB。

代价：

- 需要跨存储的一致性与备份编排；
- DuckDB 写入并发必须受控；
- Schema 变化必须分别迁移和测试。

## M0 说明

本 ADR 只确定边界。数据库、迁移、备份和恢复属于 M1，M0 不创建物理 Schema。
