# ADR-0011：供应商能力与账户权限分离

- 状态：Accepted
- 日期：2026-07-30

## 背景

同一供应商的官方 API 可能支持实时行情、期权或流式订阅，但具体用户账户未必拥有相同
权限。若只保存一份“供应商支持能力”，系统会把延迟行情误标为实时，或在未验证权限时
调用不可用端点。供应商 ticker 也不能作为 QFusion 的永久证券主键。

## 决策

所有 Adapter 必须同时公开两份独立、版本化的 Pydantic 契约：

1. `ProviderCapability` 描述当前 Adapter 实现和官方产品层面的技术能力，包括市场、资产、
   周期、实时/盘前盘后、期权、基本面、新闻、公告、流式能力、限流、历史起点、venue、
   质量和许可范围；
2. `ProviderAccessProfile` 只描述当前账户实际验证过的操作权限及逐市场数据质量。未验证、
   禁用和不可用状态必须显式表示，不能从产品能力推断账户权限。

调用前必须把请求同时与两份契约校验。`REALTIME` 只能在 Adapter 技术支持且账户实际验证
后声明；否则使用 `DELAYED`、`END_OF_DAY`、`HISTORICAL`、`UNAVAILABLE` 或明确的
`SYNTHETIC_MOCK`。

市场数据请求同时携带内部永久 `instrument_id` 和供应商不透明标识。ticker 只作为后续
Instrument Registry 中带有效期的别名，不能承担跨供应商或跨公司行为的永久身份。

Adapter 输出必须转换为 `DataSourceRecord`，保留来源、许可、事件时间、`available_at`、
修订、质量、供应商版本、数据集版本和原始载荷哈希；供应商 SDK 类型不能进入 Domain、
Repository、模型或 GUI。

M2-A 的 `SyntheticMockMarketDataProvider` 只消费调用方传入的已验证合成事实，不访问网络、
凭证或本地服务，并始终使用 `SYNTHETIC_MOCK` 与 `test-only` 许可标记。

## 后果

每个真实 Adapter 都要维护产品能力和账户权限两套测试，代码量略有增加，但延迟/实时标记、
许可边界和端点权限可以被独立审计。新增供应商不能仅因为官方产品页面列出某功能就启用；
必须以运行时账户权限和契约测试结果为准。

M2-A 尚未实现真实供应商、Instrument Registry、限流执行器、重试、凭证存储或增量同步。
这些能力必须在后续小切片中继续遵守本 ADR。
