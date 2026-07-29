# ADR-0009：确定性 AnalysisSnapshot 构建

- 状态：Accepted
- 日期：2026-07-30

## 背景

M1-A 定义了不可变 `AnalysisSnapshot` 契约，M1-B 实现 SQLite 元数据 Repository，M1-C
实现 DuckDB/Parquet 事实 Repository，但此前没有应用服务把同一决策时点的事实选择、数据
截止时间、版本、缺失项和质量状态组合成快照。

快照构建是防止三套独立模型看到不同输入、历史回测使用未来数据以及供应商版本混用的关键
边界。该逻辑不能依赖数据库返回顺序、ticker、当前墙钟的隐式状态或对 fact type 的字符串
猜测。

## 决策

1. `SnapshotBuilder` 只依赖 `FactReadRepository` 与 `SnapshotRepository` Protocol，不依赖
   DuckDB、SQLite 或供应商 SDK。
2. `SnapshotBuildPolicy` 使用显式、唯一的 `fact_type -> SnapshotDataCategory` 规则。M1 默认
   只识别已经验证的 `market.bar.daily`、`market.bar.minute`、`filing` 与 `news`；后续类型必须
   通过政策扩展，不能使用前缀猜测。
3. `SnapshotBuildRequest` 必须携带永久 UUID、市场、周期、带时区决策时间和明确证券 UUID
   集合。股票快照只能查询与 `target_id` 相同的单一证券。
4. Builder 向 Repository 传入带 `decision_time`、证券范围和 fact type 白名单的
   `FactQuery`，并在返回后再次执行 Point-in-Time 与范围守卫。重复 fact ID、越界或未来事实
   均拒绝构建。
5. 每类 `*_as_of` 使用该类可用记录的最大 `event_time`，而不是抓取时间或构建时间。值天然
   必须满足 `event_time <= available_at <= decision_time`。
6. `provider_versions` 按来源唯一；`dataset_versions` 按 `来源::fact_type` 唯一。同一键出现
   不同版本时停止构建，禁止把混合版本静默压成一项。
7. 缺少必需类别时写入 `missing_data`。显式 `STALE` 标志或超过调用方注入 freshness policy
   的类别写入 `stale_data`。二者保持互斥。
8. 初始质量分数是必需类别分数的算术平均：`OK=1.0`、`DELAYED=0.75`、`STALE=0.5`、
   `CONFLICT=0.25`、`MISSING=0`、`SYNTHETIC_MOCK=0.5`；类别采用最保守记录权重，按新鲜度
   判定过期时上限为 `0.5`。这是可解释的 M1 元数据基线，不是预测置信度。
9. 事实、版本映射和质量列表在进入 Domain 契约前规范化。`snapshot_id` 与 `created_at` 可因
   两次构建而不同，但相同政策、请求和 Repository 状态必须产生相同
   `content_fingerprint()`。
10. Builder 只有在快照完整通过 Domain 校验后才调用 `SnapshotRepository.add`；持久化异常
    原样传播，不返回未持久化成功的快照。

## 后果

优点：

- 三套独立模型可以引用同一份可追溯、可复现输入；
- 历史决策不会因 Repository 实现错误而静默接收未来事实；
- 数据类别、版本冲突、缺失与过期均可测试和审计；
- 构建逻辑可在 DuckDB/SQLite 之外用纯 Mock Repository 验证。

代价与限制：

- M1 默认政策只覆盖四种 Mock fact type，M2 适配器必须显式扩展映射和新鲜度规则；
- 当前质量权重是确定性元数据政策，必须在真实供应商质量研究后版本化，不能当作模型概率；
- M1 只证明内容指纹可复现，不实现快照调度、模型运行或跨进程写入锁。

## 验证要求

Linux 与 Windows Runner 必须实际验证：

- DuckDB Mock 日线、分钟线、公告、新闻到 SQLite 快照的完整往返；
- 决策时间之后的事实被排除；
- 两次构建的身份字段不同但内容指纹一致；
- as-of、版本、缺失、过期和质量分数确定性一致；
- Repository 越界、重复 fact ID、版本冲突、非法时钟和持久化失败均拒绝或传播；
- 既有迁移、standalone Sidecar、前端和 NSIS 构建继续通过。
