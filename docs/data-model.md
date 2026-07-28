# 数据模型基线

状态：M0 概念模型，M1 前不得视为已迁移数据库 Schema  
最后更新：2026-07-27

## 1. 标识原则

- `instrument_id` 是证券永久内部主键，建议使用 UUID。
- ticker、交易所代码和供应商代码属于 `InstrumentIdentifier`，必须带来源和有效期。
- `snapshot_id`、`run_id`、`report_id`、`evidence_id` 使用不可复用标识。
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

回测选择条件必须包含 `available_at <= decision_time`。盘前、盘后、午间休市、夏令时、半日市和公司行为均不得通过日期字符串隐式推断。

## 3. 核心实体

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| `Instrument` | `instrument_id`, `market`, `asset_type`, `status` | 永久证券记录 |
| `InstrumentIdentifier` | `instrument_id`, `scheme`, `value`, `valid_from`, `valid_to` | ticker/供应商代码历史 |
| `DataSourceRecord` | `source`, `source_record_id`, `provider_version`, time fields, `raw_payload_hash` | 可追溯事实包装 |
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

独立模型 Repository 只能读取快照事实并写入自身命名空间。Fusion Repository 可以读取已经验证的三份 Packet，但独立模型不能获得该读取能力。

## 5. 数据质量与版本

每条事实应保存：

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

缺失值必须显式保存或列入快照的 `missing_data`；不得用零值冒充缺失。实时、延迟和修订状态不能互相替代。

## 6. 存储映射

- SQLite：实体索引、配置、运行元数据、风险、报告、模拟订单和审计。
- DuckDB/Parquet：高体量时间序列、特征、标签、预测和回测明细。
- Raw Store：未加工响应和原始文档，以内容哈希去重。

M1 必须在 Alembic 迁移和契约测试中确定物理表结构。本文件本身不授权无迁移的 Schema 修改。
