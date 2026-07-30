# QFusion Desktop 架构基线

状态：M1 已验收；M2-A 供应商能力与账户权限边界候选
最后更新：2026-07-30
最高依据：[PROJECT_TASKBOOK.md](../PROJECT_TASKBOOK.md)

## 1. 目标与边界

QFusion Desktop 是本地优先的美股与港股科技板块多视角交易决策平台。第一阶段采用：

- Tauri 2 桌面外壳；
- React + TypeScript 前端；
- Python 3.12+ FastAPI 本地 Sidecar；
- SQLite 保存元数据和应用状态；
- DuckDB + Parquet 保存分析数据；
- 本地文件系统保存原始数据。

MVP 只支持研究、模拟交易、订单预览和人工确认，不提供自动实盘下单路径。

## 2. 不可破坏的架构约束

1. 华尔街、量化、游资三套独立模型使用同一个 `snapshot_id`。
2. 三套模型只能读取获准的数据快照，不能读取彼此的结果、置信度或交易建议。
3. 融合模型只能读取已通过契约验证的 Fusion Packet。
4. 融合结果必须进入独立的全局风险引擎；风险引擎拥有最终否决权。
5. 数值、时间、成本、仓位和风险许可由确定性代码计算，不交给 LLM。
6. 证券永久标识使用内部 `instrument_id`，ticker 只作为带有效期的别名。
7. 所有金融事实保留来源、时间、版本、修订与质量元数据。
8. 回测和历史决策只能使用 `available_at <= decision_time` 的数据。

## 3. 运行时拓扑

```text
Tauri Desktop
  └─ React UI
       └─ localhost API + session token
            └─ FastAPI Sidecar
                 ├─ API / application services
                 ├─ data ingestion + provider adapters
                 ├─ snapshot service
                 ├─ model orchestrator
                 │    ├─ WallStreet worker
                 │    ├─ Quant worker
                 │    └─ HotMoney worker
                 ├─ fusion service
                 ├─ global risk engine
                 └─ repositories
                      ├─ SQLite
                      ├─ DuckDB / Parquet
                      └─ raw file store
```

正式桌面运行时只监听 `127.0.0.1`，由 Tauri 为每次会话生成临时令牌并启动 Sidecar。
Sidecar 选择随机空闲端口，通过受控握手把端口和健康状态交给桌面端。当前开发演示仍使用
M0 健康端点；正式 Sidecar 握手不属于 M1-A。

## 4. 后端分层

依赖方向必须从外向内：

```text
API / Scheduler
      ↓
Application services
      ↓
Domain contracts and rules
      ↑
Provider adapters / Repository implementations
```

- `domain`：纯业务类型、规则和 Repository Protocol，不依赖 FastAPI、供应商 SDK 或
  具体数据库。
- `providers`：外部数据源 Adapter；不得从路由或模型直接调用供应商。
- `storage`：Repository 实现、迁移和单写入队列。
- `snapshots`：构建不可变、可追溯的分析快照。
- `models`：三套独立模型与融合模型；独立模型只接收能力受限的快照输入。
- `risk`：确定性全局风险检查，位于融合结果之后。
- `api`：Pydantic 边界验证和 HTTP 映射，不承载金融业务计算。

业务逻辑不直接读取环境变量。配置只在组合根加载，并以类型化设置传入。

M1-A 已在 Domain 层定义：

- 带完整来源、版本、时间、修订、质量和载荷哈希的 `DataSourceRecord`；
- 显式携带 `decision_time` 的 `FactQuery`；
- 三套独立模型共享的不可变 `AnalysisSnapshot`；
- `FactReadRepository` 与 `SnapshotRepository` Protocol。

具体 Repository 实现必须在返回后再次通过 Point-in-Time 守卫，不能依赖 SQL 正确性作为
唯一的防前视边界。

M1-B 已实现 SQLite `SnapshotRepository`。异步 Protocol 通过线程卸载调用短生命周期
SQLAlchemy Session，避免阻塞 FastAPI 事件循环；Repository 只返回重新通过 Pydantic 与
内容指纹验证的 Domain 对象，不向上层暴露 ORM Row。

M1-C 已实现 `DuckDBFactRepository`、`FactWriteQueue` 和
`ContentAddressedRawStore`。DuckDB 只保存规范化 Domain JSON 和最小查询列，读取后同时
校验内容指纹、索引列、Pydantic 契约及 Point-in-Time 守卫；业务层不接触 DuckDB SQL。

M1-D 已实现 `SnapshotBuilder`。它只接收 Repository Protocol、显式 fact type 分类政策、
目标 UUID 和决策时间；Repository 查询后再次验证 Point-in-Time 边界，拒绝版本混用，确定
性派生 as-of、缺失、过期、质量和内容指纹，再把通过 Domain 校验的快照写入 SQLite。

M2-A 候选在 Provider 层新增 `ProviderCapability`、`ProviderAccessProfile`、
`ProviderBarRequest` 以及结构化 `ProviderAdapter`/`MarketDataProvider` Protocol。产品技术能力
与当前账户实际权限必须分开验证；市场数据的技术能力、数据质量、实时性、盘前盘后权限、
周期与历史起点均按精确“市场 + 操作”键校验，不能跨键传播。请求同时使用内部 UUID 和
供应商不透明标识，并按市场时区检查对应键的历史起点。Adapter 只返回
`DataSourceRecord`。Synthetic Mock 不访问网络或凭证，完整决策见
[ADR-0011](adr/0011-provider-capability-entitlement.md)。

## 5. 模型数据流

```text
point-in-time facts
      ↓
AnalysisSnapshot(snapshot_id)
      ├─→ WallStreet result ─┐
      ├─→ Quant result ──────┼─→ validate Fusion Packets
      └─→ HotMoney result ───┘            ↓
                                      Fusion
                                         ↓
                                  Global Risk Engine
                                         ↓
                                  Final/Paper Report
```

独立模型输出分别持久化。Fusion Packet 只包含融合所需的结构化字段和证据引用，不把自由
文本报告当作主要输入。每一步记录输入版本、模型版本、参数版本和运行 ID。

M1-D 已补齐上图从 Point-in-Time 事实到持久化 `AnalysisSnapshot` 的构建边界；尚未实现任何
交易模型、融合、风险运行或调度。

## 6. 存储边界

- SQLite：设置、观察池、运行索引、风险配置、模拟订单、审计与报告索引。
- DuckDB + Parquet：K 线、因子、标签、预测、期权快照与回测结果。
- Raw Store：供应商原始响应、公告、新闻、财报和文件哈希。
- 系统采用单写入器原则；并发读取可以存在，并发任务不能直接写同一个 DuckDB 文件。
- 用户数据位于 `%LOCALAPPDATA%\QFusion\`，不写入安装目录。

上述仍是 ADR-0001 确定的目标映射。M1-B 只新增：

- SQLite `analysis_snapshots` 元数据表；
- SQLite `analysis_snapshot_facts` 跨存储 fact ID 引用表；
- URL-free、连接注入的可逆 Alembic 迁移；
- 每连接启用外键、UTC 时间类型和数据库级 Point-in-Time 检查约束。

跨存储 fact ID 不伪造 SQLite 外键。M1-C 候选实现把规范 `DataSourceRecord` 写入
DuckDB，并为每个成功批次生成带行数和 SHA-256 的不可变 Parquet 归档；所有写入通过单个
进程内异步队列串行执行。Raw Store 以原始字节 SHA-256 内容寻址并拒绝符号链接、路径穿越
和损坏对象复用。

DuckDB 连接禁用扩展自动安装、自动加载和社区扩展，只允许访问调用方提供的 Parquet 根，
临时文件与扩展目录也位于该根内；完成配置后关闭一般外部访问并锁定配置。详细契约见
[data-model.md](data-model.md)，存储选择见 [ADR-0001](adr/0001-local-lite-storage.md)，
SQLite 决策见 [ADR-0007](adr/0007-sqlite-snapshot-metadata.md)，分析事实存储见
[ADR-0008](adr/0008-duckdb-parquet-raw-fact-storage.md)。

M1-E 已把 SQLite Online Backup 快照、静止 DuckDB、非临时 Parquet 和 Raw Store 写入
带版本与逐文件 SHA-256 清单的 `.qfbak`。恢复先在新 staging 中完成路径、大小、摘要、
SQLite integrity 和两种 Schema 校验。恢复在服务内锁保护下要求目标不存在，再把 staging
改名为目标；它不主动覆盖当前数据，但同一用户的外部进程若并发制造目标路径，仍属于已知
竞态边界。在跨存储在线写入屏障实现前，备份调用方必须先停止写入并关闭数据库句柄。完整决策见
[ADR-0010](adr/0010-offline-audited-backup-restore.md)。

## 7. 前端边界

- 服务端状态由 TanStack Query 管理。
- 仅 UI 本地状态使用轻量 Store。
- API 类型从后端 OpenAPI Schema 生成。
- 金额、百分比和时间使用显式解析与格式化。
- 数据状态至少区分 `FRESH`、`DELAYED`、`STALE`、`MISSING`。
- 风险和数据质量不能只依赖颜色表达。

## 8. 安全边界

- API Key 不进入前端、普通日志、报告或异常正文。
- 正式本地 API 使用临时会话认证、精确 CORS 和 localhost 绑定。
- 导入路径与 Sidecar 参数使用白名单。
- CI 中所有供应商与 LLM 调用必须 Mock。
- 供应商产品能力不能替代当前账户的实时、盘前或盘后权限验证；两者必须按精确市场与
  操作键匹配，凭证不进入 Provider Access 契约。
- 仓库中不存在实盘提交路由。
- 开发工具链、依赖缓存和临时文件必须保留在仓库内，并从不继承科研、Conda、ROS、
  CUDA、容器或用户代理环境；完整决策见 [ADR-0006](adr/0006-project-local-toolchains.md)。

## 9. 当前验证范围

M0 的 FastAPI 健康检查、React/Tauri 空壳、前后端 Mock 通信、Linux CI 和 Windows 构建
基线继续有效。

M1-A 至 M1-E 均已通过 Linux 与 Windows 托管验证：

- Pydantic 类型和生成的 JSON Schema 必须确定性一致；
- 所有时间必须带时区并规范化为 UTC；
- `available_at` 晚于 `decision_time` 的事实必须被拒绝；
- as-of 时间不能晚于快照决策时间；
- UUID 永久标识、版本映射、缺失/过期数据和复权状态必须显式；
- Repository Protocol 不依赖供应商或具体数据库；
- Linux 与 Windows 托管 CI 同时执行契约测试；
- 空 SQLite 数据库可升级到 head、重复升级、降级到 base 并再次升级；
- 迁移列与 ORM metadata 一致，外键、级联和数据库检查约束实际生效；
- Snapshot Repository 可往返不可变元数据，并拒绝重复标识和指纹/契约损坏；
- Mock 日线、分钟线、公告和新闻可写入 DuckDB 并按 Point-in-Time 查询；
- 每个成功批次的 Parquet 行数、路径和 SHA-256 可审计，失败批次回滚；
- Raw Store 相同内容幂等，损坏、非法摘要和非法路径被拒绝；
- 快照只使用显式映射的 fact type，并在 Repository 返回后再次执行范围和防前视守卫；
- 相同请求和事实状态的两次构建具有相同内容指纹，身份与创建时间不参与指纹；
- as-of 使用最大事件时间，版本混用、重复 fact ID、非法时钟和持久化失败均被拒绝；
- DuckDB Mock 日线、分钟线、公告和新闻可以生成并从 SQLite 读回同一快照；
- SQLite、DuckDB、Parquet 和 Raw Store 可归档并恢复到新目录，原 Repository 可重新读取；
- 备份跳过 Parquet 临时目录，发现 WAL、符号链接、变化文件或未知 Schema 时拒绝；
- 恢复拒绝路径穿越、额外项、ZIP 链接、内容篡改和超限，且不覆盖已有目录；
- 测试数据库、归档和原始对象只位于 Runner 仓库内临时目录；
- Synthetic Mock 已通过统一 Adapter 边界提供 Point-in-Time bar 过滤，并验证技术能力
  与账户权限不会跨市场或跨操作形成虚假组合；
- 尚未实现真实供应商连接、Instrument Registry、模型、订单或真实金融调用。

M1 的退出条件、精确 Runner、Artifact 摘要和已知限制见
[M1 正式验收](m1-acceptance.md)；后续进度见 [roadmap.md](roadmap.md)。
