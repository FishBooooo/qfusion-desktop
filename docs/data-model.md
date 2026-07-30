# 数据模型基线

状态：M1 本地存储与数据契约已正式验收
最后更新：2026-07-30

## 1. 标识原则

- `instrument_id` 是证券永久内部主键，使用 UUID。
- ticker、交易所代码和供应商代码属于 `InstrumentIdentifier`，必须带来源和有效期。
- `fact_id`、`snapshot_id`、`run_id`、`report_id`、`evidence_id` 使用不可复用标识。
- 不允许使用 ticker 连接长期历史、公司行为、持仓或模型结果。

## 2. 时间原则

持久化时间使用带时区的 UTC 时间；市场日历和界面显示同时保留 IANA 市场时区。

金融事实至少区分：

- `event_time`：市场或业务事件发生时间；
- `published_at`：来源公布时间；
- `available_at`：系统在历史上最早可以合法使用该事实的时间；
- `received_at`：客户端收到时间；
- `ingested_at`：进入本地仓库时间；
- `effective_from` / `effective_to`：修订或标识有效区间。

回测选择条件必须包含 `available_at <= decision_time`。盘前、盘后、午间休市、夏令时、
半日市和公司行为均不得通过日期字符串隐式推断。

M1-A 契约把所有输入时间标准化为 UTC，并强制：

```text
event_time <= published_at <= available_at <= received_at <= ingested_at
```

Repository 返回值还必须通过 Point-in-Time 守卫复核，不能仅依赖具体数据库查询实现。

## 3. 核心实体

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| `Instrument` | `instrument_id`, `market`, `asset_type`, `status` | 永久证券记录 |
| `InstrumentIdentifier` | `instrument_id`, `scheme`, `value`, `valid_from`, `valid_to` | ticker/供应商代码历史 |
| `DataSourceRecord` | `fact_id`, source/version/time/revision/quality fields, `raw_payload_hash` | 可追溯 Point-in-Time 事实包装 |
| `CorporateAction` | `instrument_id`, `action_type`, `effective_at`, adjustment fields | 拆股、分红、代码变化等 |
| `AnalysisSnapshot` | `snapshot_id`, target, `decision_time`, as-of fields, versions, quality | 三模型共享的不可变输入视图 |
| `ModelRun` | `run_id`, `model_type`, versions, `snapshot_id`, status | 独立模型运行记录 |
| `ModelResult` | `run_id`, horizon views, action, trade plan, evidence, quality | 各模型分别保存的结构化结果 |
| `FusionPacket` | contract version, `run_id`, `snapshot_id`, calibrated fields | 最小融合输入 |
| `FusionRun` | three packet IDs, weights, agreement/disagreement | 融合运行 |
| `RiskDecision` | fusion ID, ruleset version, permission, reasons | 最终风险许可 |
| `Report` | source run IDs, template/prompt version, generated time | 可缓存报告 |
| `PaperOrder` | portfolio ID, instrument ID, preview/risk IDs, state | 仅模拟交易 |
| `AuditEvent` | actor, action, target, result, redacted metadata | 安全审计 |

## 4. 关系与隔离

```text
Instrument ──< Source Facts ──> AnalysisSnapshot
                                  ├─ ModelRun(wallstreet)
                                  ├─ ModelRun(quant)
                                  └─ ModelRun(hotmoney)
                                         ↓ validated packets
                                      FusionRun
                                         ↓
                                    RiskDecision
                                         ↓
                                  Report/PaperOrder
```

独立模型 Repository 只能读取快照事实并写入自身命名空间。Fusion Repository 可以读取已经
验证的三份 Packet，但独立模型不能获得该读取能力。

## 5. 数据质量与版本

每条事实保存：

```text
source
source_record_id
source_quality_level
venue_scope
license_scope
provider_version
dataset_version
revision_id
quality_flag
raw_payload_hash
is_adjusted
adjustment_type
```

缺失值必须显式保存或列入快照的 `missing_data`；不得用零值冒充缺失。实时、延迟和修订
状态不能互相替代。`is_adjusted` 与 `adjustment_type` 必须同时表达一致的复权状态。

## 6. M1-A 领域契约

代码位置：

- `qfusion.domain.contracts.DataSourceRecord`；
- `qfusion.domain.contracts.FactQuery`；
- `qfusion.domain.contracts.AnalysisSnapshot`；
- `qfusion.domain.repositories.FactReadRepository`；
- `qfusion.domain.repositories.SnapshotRepository`。

契约具备以下边界：

1. Pydantic 模型禁止未知字段且创建后不可变。
2. 股票、板块和篮子均使用 UUID `target_id`，ticker 不进入永久主键。
3. 美股和港股快照分别使用 `America/New_York` 与 `Asia/Hong_Kong`。
4. as-of 时间不得晚于 `decision_time`。
5. 快照显式引用去重并排序后的 `fact_ids`、供应商版本和数据集版本。
6. `missing_data` 与 `stale_data` 互斥。
7. 快照内容指纹排除分配时的 `snapshot_id` 和 `created_at`，用于验证同一输入可复现。
8. JSON Schema 由 Pydantic 类型确定性生成，CI 检查漂移。

## 7. 存储映射

- SQLite：实体索引、配置、运行元数据、风险、报告、模拟订单和审计。
- DuckDB/Parquet：高体量时间序列、特征、标签、预测和回测明细。
- Raw Store：未加工响应和原始文档，以内容哈希去重。

M1-B 已用 Alembic 建立两个 SQLite 表：

| 表 | 用途 | 关键约束 |
| --- | --- | --- |
| `analysis_snapshots` | 完整快照元数据与内容指纹 | UUID 主键、UTC 时间、as-of 不晚于决策时间、市场/时区配对、质量范围 |
| `analysis_snapshot_facts` | 指向分析仓库事实的跨存储 UUID 引用 | 复合主键；删除快照只级联引用行 |

`provider_versions`、`dataset_versions`、`missing_data` 与 `stale_data` 使用 SQLite
JSON 列保存，但读取后必须重新通过 Pydantic 校验。所有时间由 SQLAlchemy
`UTCDateTime` 写成无时区 UTC、读回为带 UTC 时区值。Repository 还重新计算
`content_fingerprint`，拒绝静默损坏或被外部修改的行。

`analysis_snapshot_facts.fact_id` 有查询索引但没有 SQLite 外键，因为目标事实属于
DuckDB/Parquet/Raw Store。`DataSourceRecord.payload` 不写入 SQLite。

## 8. M1-C 分析事实与原始对象物理映射

DuckDB Schema 版本为 `1`：

| 表 | 用途 | 关键约束 |
| --- | --- | --- |
| `warehouse_metadata` | DuckDB 物理 Schema 版本 | 未知版本拒绝打开 |
| `source_facts` | 规范 `DataSourceRecord` JSON 和 Point-in-Time 查询列 | `fact_id` 主键；内容 SHA-256；`available_at`、instrument 和 fact type 索引 |
| `fact_batches` | 不可变 Parquet 批次目录 | UUID 批次主键；正行数；唯一相对路径；文件 SHA-256 |

`source_facts.record_json` 是事实的规范表示。`instrument_id`、`fact_type` 和
`available_at` 是查询加速列，不是第二份真值；读取时必须与 JSON 恢复对象逐字段核对。
SQL 查询和返回后守卫都执行 `available_at <= decision_time`。DuckDB 物理列使用无时区
`TIMESTAMP` 表示规范 UTC；写入前显式去除 UTC 时区，读回时只接受无时区值并恢复为带
`UTC` 时区的 Domain 时间，避免 DuckDB 客户端隐式本地时区转换。

每个成功写入批次在 `parquet/batches/<batch_id>.parquet` 生成按 `fact_id` 排序的 ZSTD
归档。DuckDB 目录只保存相对路径，Repository 在读取前重建并验证固定批次路径、不经过
符号链接、仍位于根目录、SHA-256 和行数均一致。

Raw Store 使用：

```text
raw/objects/<sha256[0:2]>/<sha256[2:4]>/<sha256><suffix>
```

摘要由原始字节计算；相同摘要与后缀的对象只能幂等复用，不能覆盖已损坏对象。

## 9. M1-D 快照派生

`SnapshotBuilder` 使用显式政策把 M1 已验证的事实类型映射为价格、基本面和新闻类别。默认
映射不按前缀猜测，M2 新类型必须经过版本化政策扩展。

派生规则：

- `FactQuery` 固定 `decision_time`、证券 UUID 和允许的 fact type；返回后再次执行范围与
  Point-in-Time 守卫；
- 各类 as-of 使用可用事实最大的 `event_time`；
- `provider_versions` 按来源唯一，`dataset_versions` 按 `来源::fact_type` 唯一；冲突停止；
- 必需类别无可用事实时列入 `missing_data`，显式 `STALE` 或超过注入上限时列入
  `stale_data`；
- 质量分数是必需类别的可解释、保守元数据分数，不是预测概率；
- 事实 ID、版本和质量列表均规范排序，`snapshot_id` 与 `created_at` 不参与内容指纹。

相同请求、政策和 Repository 状态允许生成不同永久快照 ID，但必须得到相同
`content_fingerprint()`。快照通过 Pydantic 校验后才写入 SQLite。

## 10. M1-E 备份清单

`.qfbak` 的 `manifest.json` 使用 Schema `1.0.0`，至少包含：

```text
created_at
sqlite_revision
duckdb_schema_version
entries[].relative_path
entries[].byte_count
entries[].sha256
```

`entries` 按规范 POSIX 相对路径排序且唯一，只能指向两个固定数据库文件、`parquet/` 或
`raw/`。SQLite 和 DuckDB 版本必须同时匹配当前程序支持版本；恢复后再次执行 SQLite
`integrity_check` 和两种 Schema 校验。

M1-E 不把 `.tmp`、WAL、日志或数据根外文件写入归档。恢复目标必须不存在，成功前所有文件
位于唯一 staging；因此正常失败路径不会改变当前数据。服务内锁不覆盖同一用户外部进程在
目标检查与改名之间制造路径的竞态，调用方必须保证数据根由 QFusion 独占。当前仍未实现
跨存储在线写入屏障、备份加密、恢复后的活动数据根切换、供应商连接、模型、订单或真实
金融数据。
