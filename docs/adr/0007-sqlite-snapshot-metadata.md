# ADR-0007：SQLite 快照元数据与连接注入迁移

- 状态：Accepted
- 日期：2026-07-29

## 背景

M1-A 已建立不可变的 `AnalysisSnapshot` 与 Repository Protocol，但尚无物理持久化。
ADR-0001 同时要求 SQLite 只承担应用元数据，而高体量行情、特征和回测数据属于
DuckDB + Parquet。若把通用 `DataSourceRecord.payload` 写入 SQLite，会破坏这项分工。

桌面应用还必须在 Windows 本地安全升级数据库，且不能从 Shell、用户配置或环境变量读取
任意数据库 URL。

## 决策

M1-B 使用 SQLAlchemy 2 和 Alembic 建立最小 SQLite 元数据边界：

1. `analysis_snapshots` 保存完整快照元数据、版本映射、质量状态和内容指纹。
2. `analysis_snapshot_facts` 只保存快照到外部 `fact_id` 的跨存储引用；事实载荷仍由
   后续 DuckDB/Parquet/Raw Store Repository 保存。
3. 时间写入前统一转换为无时区 UTC，读取后恢复为带 `UTC` 时区的 `datetime`。
4. Point-in-Time、市场时区、质量分数和指纹长度同时受 Domain 校验和数据库
   `CHECK` 约束保护。
5. SQLite 每个连接显式启用外键；删除快照时仅级联其引用行，不删除外部事实。
6. Alembic 配置不包含数据库 URL。应用必须创建 Engine，并通过
   `Config.attributes["connection"]` 注入连接。
7. 生产代码只暴露升级入口。降级脚本保留并只在仓库本地临时数据库上验证。
8. Repository 写入使用插入语义，重复 `snapshot_id` 不允许覆盖；读取时重新验证
   Pydantic 契约和内容指纹。

## 后果

优点：

- 不会把高体量金融事实误放入 SQLite；
- 快照可离线读取、可追溯并可检测持久化损坏；
- 迁移不依赖 Shell、全局配置或用户级数据库工具；
- 物理 Schema 可从空库升级、降级并再次升级。

代价：

- SQLite 无法对外部 DuckDB/Parquet 事实建立真实外键；
- 快照构建服务必须在后续切片中验证所有 `fact_id` 已写入分析仓库；
- 备份恢复必须跨 SQLite、DuckDB/Parquet 和 Raw Store 编排，仍属于后续 M1 范围。
