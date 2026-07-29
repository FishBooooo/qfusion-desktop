# ADR-0008：DuckDB、Parquet 与内容寻址 Raw Store

- 状态：Accepted
- 日期：2026-07-30

## 背景

ADR-0001 已确定 Local Lite 使用 SQLite、DuckDB、Parquet 与 Raw Store 的组合。M1-B 只把
不可变快照元数据和外部 fact ID 引用写入 SQLite；Mock 日线、分钟线、公告和新闻仍缺少
高容量事实载荷的物理 Repository。

该仓库必须同时满足 Point-in-Time 查询、单写入器、离线运行、Windows 打包、原始证据去重
和宿主环境隔离。DuckDB SQL 具有文件访问能力，因此连接配置本身也是安全边界，不能依赖
用户级配置、自动扩展下载或仓库外临时目录。

## 决策

M1-C 采用以下边界：

1. DuckDB `source_facts` 保存 `DataSourceRecord` 的规范 JSON、内容 SHA-256，以及
   `fact_id`、`instrument_id`、`fact_type` 和 `available_at` 查询列。
2. Repository 查询必须先在 SQL 中执行 `available_at <= decision_time`，恢复对象后再通过
   Pydantic 与 `require_point_in_time` 重复验证；索引列必须与规范 JSON 一致。
3. 每个成功写入批次生成一份按 `fact_id` 排序、ZSTD 压缩的不可变 Parquet 归档；
   `fact_batches` 保存相对路径、行数、生成时间和 SHA-256。
4. `FactWriteQueue` 是应用进程拥有的单写入入口。Repository 自身还使用异步写锁，避免同一
   实例绕过队列造成并发写入；读取使用短生命周期独立连接。
5. DuckDB 初始物理 Schema 版本写入 `warehouse_metadata`。未知版本必须拒绝打开，后续变更
   必须新增显式迁移，不允许静默改表。
6. DuckDB 连接关闭扩展自动安装、自动加载和社区扩展，只加载随发行包提供的 Parquet
   扩展；扩展、临时目录和允许访问目录全部固定在调用方提供的项目/用户数据根内。配置完成
   后关闭一般外部访问并锁定连接配置。
7. Raw Store 使用原始字节的 SHA-256 作为分片路径。相同内容幂等复用；路径、现有对象和读取
   结果都必须重新校验，禁止符号链接、路径穿越和静默覆盖损坏对象。
8. DuckDB/Parquet 与 Raw Store 路径只能由组合根传入绝对、已存在且不经过符号链接的目录。
   业务层仍只依赖 Domain Repository 契约，不直接执行 DuckDB SQL。

Parquet 文件在数据库事务提交前以项目内临时文件生成并校验，再通过同文件系统原子改名
进入最终路径。进程内异常会回滚数据库并移除本次归档。机器突然断电可能留下未被
`fact_batches` 引用的孤立文件；不得自动删除，后续备份/恢复切片必须提供只读审计和显式
恢复策略。

## 后果

优点：

- 高容量事实不会误写入 SQLite；
- 查询和返回边界都执行 Point-in-Time 检查；
- Parquet 批次可独立审计、备份和跨版本读取；
- 原始公告、新闻和供应商响应可以按内容去重并检测篡改；
- 不需要数据库服务、容器或宿主级依赖。

代价：

- DuckDB 与 Parquet 之间不是跨文件系统事务，需审计潜在孤立归档；
- 单写入队列目前是进程内所有权，正式 Sidecar 组合根还必须防止双实例写入；
- 初始 Schema 版本只有 `1`，后续升级需要专门的 DuckDB 迁移机制；
- M1-C 尚不生成 `AnalysisSnapshot`，也不实现备份恢复、供应商连接或真实金融数据。

## 验证要求

Linux 与 Windows 专用 Runner 必须从锁文件安装 DuckDB，并实际验证：

- Mock 日线、分钟线、公告和新闻写入、筛选与重开读取；
- 未来事实排除、instrument/fact type 过滤和返回后防前视守卫；
- 重复 fact ID 事务回滚及写入队列在失败后的可用性；
- 规范 JSON、索引列、Schema 版本、Parquet 路径、行数和 SHA-256 篡改检测；
- Raw Store 幂等写入、哈希审计和非法路径拒绝；
- standalone Windows Sidecar 能包含 DuckDB 原生模块并完成既有受控 Loopback 烟雾测试。
