# 数据供应商登记

状态：M2-A 供应商边界候选；仅实现确定性 Synthetic Mock，尚未连接真实供应商。
最后更新：2026-07-30

## 1. 强制登记字段

任何 Provider Adapter 进入代码前必须记录：

- 官方产品/API 名称与版本；
- 支持市场、资产、周期、盘前盘后和流式能力；
- 行情是实时、延迟、EOD、历史还是不可用；
- 历史起点、venue scope 和质量等级；
- rate limit、并发、重试与空响应行为；
- 个人研究、缓存、长期存储、展示、商业使用和再分发许可；
- 字段来源、时区、`available_at`、修订和公司行为语义。

供应商字段或权限未由官方文档和契约测试验证前，一律标记“待验证”，不能写入生产
Domain 契约。

## 2. 能力与账户权限是两份事实

`ProviderCapability` 描述 Adapter 实现与供应商产品的技术能力；`ProviderAccessProfile`
描述当前账户实际验证过的权限，以及逐市场数据质量、盘前和盘后权限。两者必须同时通过
校验，不能因为产品支持实时行情或延长时段就推断当前账户也有相同权限。

账户数据质量只允许：

```text
REALTIME
DELAYED
END_OF_DAY
HISTORICAL
SYNTHETIC_MOCK
UNAVAILABLE
```

未验证账户使用 `UNVERIFIED`，不得启用操作或宣称可用行情。凭证本身不属于
`ProviderAccessProfile`，不得进入日志、报告、Fixture 或模型上下文。

完整决策见 [ADR-0011](adr/0011-provider-capability-entitlement.md)。

## 3. M2-A 已实现：Synthetic Mock

| 字段 | 值 |
| --- | --- |
| Provider | `qfusion-synthetic-mock` |
| Provider version | `1.0.0` |
| 市场 | US、HK |
| 资产 | stock、ADR、ETF、sector ETF |
| 周期 | `1m`、`1d` |
| 操作 | bars |
| 数据质量 | `SYNTHETIC_MOCK` |
| Venue scope | `synthetic-us-hk` |
| License scope | `test-only` |
| 网络/凭证 | 不使用 |
| 真实金融数据 | 不包含 |

Mock Adapter 只过滤调用方传入的已通过 `DataSourceRecord` 校验的合成事实。请求同时携带
内部 UUID 和供应商不透明证券 ID；返回结果按证券、事实类型、事件时间及
`available_at <= decision_time` 过滤。请求起点必须位于按市场时区解释的供应商历史边界
内；盘前和盘后分别校验产品能力及逐市场账户权限。Mock 不能被标记为实时或用于交易许可。

## 4. 首批真实供应商计划

下表只表示已选实施方向，不表示已经连接、验证账户权限或获得再分发许可。

| 切片 | 供应商 | 预期用途 | 当前状态 |
| --- | --- | --- | --- |
| M2-C | SEC EDGAR `data.sec.gov` | 美股 submissions、filings、company facts | 官方契约研究完成；未实现 |
| M2-D | FRED/ALFRED | 美国宏观与 vintage/realtime period | 官方契约研究完成；需要用户自带 API key |
| M2-E | Tiingo | 美股 EOD/历史行情候选 | 官方契约研究完成；需要用户自带 token，许可待账户验证 |
| M2-F | Longbridge OpenAPI | 港股行情候选 | 官方契约研究完成；实际账户行情权限必须运行时验证 |

官方依据：

- SEC：[EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) 与
  [Developer Resources](https://www.sec.gov/about/developer-resources)；
- FRED：[API Overview](https://fred.stlouisfed.org/docs/api/fred/overview.html) 与
  [Series Observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)；
- Tiingo：[General Documentation](https://www.tiingo.com/documentation/general) 与
  [End-of-Day API](https://www.tiingo.com/documentation/end-of-day)；
- Longbridge：[OpenAPI Documentation](https://open.longbridge.com/docs) 与
  [Quote Overview](https://open.longbridge.com/docs/quote/overview)。

真实 Adapter 必须使用官方响应 Fixture 做解析测试，CI 禁止调用真实端点。付费订阅、真实
凭证注入和外部账户写入不在默认授权范围内。

## 5. 后续门禁

1. M2-B 先建立内部 Instrument Registry 与带有效期的供应商标识映射；ticker 不能作为
   永久主键。
2. M2-C 至 M2-F 逐个实现 Adapter，不共享供应商 SDK 类型。
3. 每个 Adapter 必须覆盖限流、超时、重试、空响应、字段变化、时区、休市、修订和延迟
   标记测试。
4. M2-G 才接入观察池增量同步和 GUI 数据状态；在此之前不声明 M2 完成。
