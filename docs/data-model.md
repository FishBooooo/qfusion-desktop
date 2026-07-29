# 数据模型基线

状态：M1-A 版本化领域契约；尚未创建物理数据库 Schema
最后更新：2026-07-29

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

本切片只建立领域契约与 Repository Interface，未引入 SQLite、DuckDB、Parquet、Alembic
迁移、备份恢复或物理表。后续 M1 存储实现必须以迁移和 Repository 契约测试落地，禁止
业务逻辑直接依赖具体数据库。
