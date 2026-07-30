# ADR-0012：Point-in-Time Instrument Registry

- 状态：Accepted
- 日期：2026-07-30

## 背景

QFusion 的行情、公告、模型结果、持仓与回测必须长期引用同一证券身份。ticker 会因公司行为、
交易所规则和供应商命名发生变化，也可能在退市后被另一证券复用；供应商证券 ID 只在对应
供应商和市场内有意义。若把任一外部代码当作永久主键，历史数据会错误串联，或在回测时使用
当时尚未知晓的映射。

M2-A 已要求市场数据请求同时携带内部 `instrument_id` 和供应商不透明 ID，但当时只使用调用方
传入的 Synthetic Mock 映射。M2-B 需要在不连接真实供应商的前提下建立可持久化、可审计且
Point-in-Time 安全的身份边界。

## 决策

1. `Instrument` 使用不可复用 UUID `instrument_id` 作为唯一永久身份。市场、资产类型和显示名称
   是注册时的静态身份元数据；ticker 与供应商 ID 不进入该表主键。
2. ticker 使用独立的 `TickerAlias`，供应商不透明 ID 使用独立的
   `ProviderInstrumentMapping`。两者均保存自身 UUID、`instrument_id`、市场、半开有效区间
   `[valid_from, valid_to)`、`available_at`、来源记录和修订信息。
3. ticker 在写入和查询边界统一去除首尾空白并转为大写；供应商名称统一为 Unicode
   `casefold` 形式。供应商不透明 ID 只去除首尾空白，内部大小写和内容保持不变，不能按 ticker
   规则改写。
4. 所有查询必须显式携带 `effective_at` 与 `decision_time`，并满足
   `effective_at <= decision_time`。物理查询同时要求有效区间覆盖 `effective_at` 且
   `available_at <= decision_time`；Repository 返回后再次执行同样的 Domain 守卫。
5. SQLite 保存 `instruments`、`instrument_ticker_aliases` 和
   `provider_instrument_mappings`。映射通过 `(instrument_id, market)` 复合外键保证市场与永久
   证券一致；不提供删除或覆盖 Repository 方法。
6. 同一市场 ticker 的有效区间不得重叠。供应商映射同时禁止：
   - 同一 `provider_name + market + provider_instrument_id` 的有效区间重叠；
   - 同一 `provider_name + market + instrument_id` 在同一时点映射到多个供应商 ID。
   SQLite 触发器和 Repository 错误映射共同执行这些约束，允许在不重叠区间内发生 ticker
   变化、供应商代码变化和 ticker 复用。
7. Instrument Registry Protocol 位于 Domain 层，SQLite 实现只返回重新通过 Pydantic 和
   Point-in-Time 校验的对象，不向 Provider、模型或 GUI 暴露 ORM Row 或 SQL。
8. M2-B 的 Synthetic Mock 集成只能使用测试内创建的证券与映射，不访问网络、凭证、本地服务
   或真实金融数据。

## 后果

优点：

- 公司更名、ticker 变化和 ticker 复用不会改变永久证券身份；
- 供应商 ID 保持真正不透明，且不能跨供应商或市场误用；
- 历史回测只能使用当时已经可知并在当时有效的映射；
- M2-A 的双标识请求可由统一 Repository 提供，而不是由 Adapter 私自维护 ticker 主键。

代价与限制：

- M2-B 只支持不重叠的有效期历史；对已写映射的事后纠错需要后续版本化知识区间设计，不能
  通过静默覆盖解决；
- 证券状态、公司行为、跨市场同一发行人关系、ISIN/FIGI 等额外标识方案尚未实现；
- 当前只用 Synthetic Mock 验证边界，真实供应商字段、许可和映射质量必须在各 Adapter
  切片中用官方 Fixture 和 Contract 测试确认。

## 验证要求

Linux 与 Windows 托管 Runner 必须实际验证：

- 空库升级到单一新 head、重复升级、降级到 base 并再次升级；
- ORM 与迁移列一致，复合外键、半开区间、重叠触发器和永久 UUID 约束生效；
- ticker 大小写规范化、供应商 ID 大小写保留和 US/HK 市场隔离；
- `valid_from`/`valid_to` 边界、ticker 变化、ticker 复用与供应商代码变化；
- `available_at > decision_time`、未来 `effective_at`、未知证券、市场错配和持久化损坏均被
  拒绝或不可见；
- 通过 Registry 解析的 Synthetic Mock 双标识能够完成网络隔离的 bar Contract 测试；
- 既有 Point-in-Time、Provider、备份、standalone Sidecar、前端和 NSIS 回归继续通过。
