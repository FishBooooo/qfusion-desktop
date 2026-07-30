# ADR-0015：供应商使用许可必须结构化并默认拒绝

- 状态：Accepted
- 日期：2026-07-30

## 背景

M2-A 的 `ProviderCapability.license_scope` 能保存简短许可标签，但无法机器判断“可个人研究”
是否同时意味着“可缓存、长期落库、展示、再分发或进入模型”。这种歧义会让技术上可用的
Adapter 绕过供应商条款，尤其会与 QFusion 的本地持久化、离线运行和模型处理目标发生冲突。

2026-07-30 对官方条款的复核发现，当前 FRED® Services Terms of Use 明确禁止存储、缓存、
归档 FRED 内容或把它并入数据库，也禁止把 FRED 服务或内容用于软件、机器学习或 AI 系统
的开发或训练。FRED API 另有账户/API key、署名和非背书声明要求。由此，原计划中的
FRED/ALFRED API 与 QFusion 的 Raw Store、DuckDB/Parquet、离线缓存和模型输入路径存在直接
冲突；只检查 API key 或技术字段不足以保证合规。

官方依据：

- [FRED Services Terms of Use](https://fred.stlouisfed.org/legal/terms/)
- [FRED API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html)
- [SEC Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)

## 决策

1. `ProviderCapability` Schema 升级为 `2.0.0`，每个 Adapter 必须提供冻结的
   `ProviderUsagePolicy`；旧的 `1.0.0` 能力对象不再通过边界验证。
2. 策略必须记录官方条款 URL、复核日期、署名要求、必需提示，以及以下八种精确用途：
   `personal_research`、`local_cache`、`persistent_storage`、`private_display`、
   `public_display`、`commercial_use`、`redistribution`、`model_processing`。
3. 每种用途只能是 `ALLOWED`、`PROHIBITED` 或 `UNVERIFIED`。只有 `ALLOWED` 可以通过
   `validate_provider_usage`；其他状态统一抛出带
   `BLOCKED_BY_PROVIDER_LICENSE` 的 `PermissionError`，不得用默认值或产品能力推断许可。
4. `model_processing` 覆盖规则、统计、机器学习和 LLM 路径。某项许可只允许人工查看时，
   不能把它解释为允许进入任何模型。
5. `license_scope` 继续保留在 `DataSourceRecord` 中作为逐事实的简短来源标签；它不能替代
   结构化策略，也不能单独授权任何用途。
6. Adapter 或应用服务在产生网络、缓存、落库、展示或模型副作用之前，必须校验相应用途。
   M2-D0 先把 SEC `get_filings` 的持久化意图放到网络请求之前校验，并用测试证明拒绝时
   Transport 不被调用。
7. Synthetic Mock 只在 QFusion 测试/演示范围内允许缓存、持久化、展示和模型处理，必须
   保留“合成数据”提示；商业使用和再分发仍禁止。
8. SEC 官方说明允许访问和复用政府创建内容及 EDGAR 公开 filing 内容，因此当前采集边界
   允许个人研究、项目本地缓存、持久化和私有展示。公开展示、商业使用、再分发与模型处理
   在没有逐用途复核前保持 `UNVERIFIED`。
9. 不创建 FRED/ALFRED Adapter，不配置 API key，不请求端点，也不保存其响应。只要当前
   条款与 QFusion 必需用途冲突，该方向保持 `BLOCKED_BY_PROVIDER_LICENSE`。BLS、BEA、
   Treasury 等原始官方来源可作为后续候选，但必须分别完成同样的条款和 Point-in-Time
   语义复核后才能选定。

## 后果

供应商接入会多一层显式策略和测试，但许可冲突能在网络或存储副作用前失败，且审查者可以
区分技术能力、账户权限和使用许可。新增或变更 Adapter 时必须更新条款复核日期和相关文档；
条款变化不能通过静默修改标签放宽权限。

M2-D0 不改变数据库 Schema、不新增依赖、不调用任何供应商，也不代表对第三方条款的法律
意见。若许可状态仍不明确，系统必须保持 `UNVERIFIED` 并停止相应用途。