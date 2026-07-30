# ADR-0016：BLS v1 首次观察宏观序列边界

- 状态：Accepted
- 日期：2026-07-31

## 背景

FRED/ALFRED 当前条款与 QFusion 的本地持久化、缓存和模型处理路径冲突，因此 ADR-0015
要求在实现宏观 Adapter 前选择许可允许这些用途的原始官方来源。

美国劳工统计局（BLS）Public Data API v1 无需注册，允许二次使用其数据，但要求记录
检索日期、提供来源说明，且 BLS 不为取回后的衍生数据或分析背书。未注册 v1 的公开限制
包括每次最多 25 个序列、最多 10 年、每日最多 25 次请求和每 10 秒最多 50 次请求。

v1 同时存在重要的 Point-in-Time 缺口：它不提供目录元数据、真实发布时间或历史
vintage；API 数据相对 BLS 发布页面可能晚一天。把月度观察值回填成“在月份结束时已知”
会制造前视偏差。

官方依据：

- [BLS API Terms of Service](https://www.bls.gov/developers/termsOfService.htm)
- [BLS Public Data API Getting Started](https://www.bls.gov/developers/home.htm)
- [BLS API Frequently Asked Questions](https://www.bls.gov/developers/api_faqs.htm)
- [BLS v1 Signatures](https://www.bls.gov/developers/api_signature.htm)
- [BLS API Features](https://www.bls.gov/bls/api_features.htm)

## 决策

M2-D1 首批宏观候选实现采用无注册的 BLS Public Data API v1，并限制为月度序列：

1. `ProviderOperation.MACRO_SERIES` 是独立操作。宏观来源不伪装成股票、ETF 或 basket；
   `ProviderCapability` Schema 升级为 `3.0.0`，且只有纯宏观序列 Provider 可以声明空的
   `supported_asset_types`。
2. 每个请求最多 25 个唯一序列，起止年份为闭区间且最多 10 年。请求体不得包含注册密钥。
3. Transport 只允许固定 `https://api.bls.gov/publicAPI/v1/timeseries/data/`，使用 POST、
   禁止代理和重定向；DNS 每次请求前必须全部解析为公网地址。响应字节数、超时、重试、
   并发、每 10 秒和每日预算均有项目内上限。
4. 常规测试只使用明确标记为合成的 v1 Schema Fixture 和 `httpx.MockTransport`，不得访问
   live BLS 端点。
5. 对每条月度观察：
   - `event_time` 仅锚定为该月第一天 UTC，用于表示观察期，不代表发布日期；
   - `published_at`、`available_at` 和 `received_at` 都设置为 QFusion 首次收到该响应的
     时间；
   - `ingested_at` 不得早于首次收到时间；
   - 原始字符串值和脚注原样保留，不用浮点数重新格式化；
   - `series_id + year + period` 是稳定来源记录键，规范行 SHA-256 是 revision，二者共同
     生成不可变 fact ID；后续值变化形成新修订，不覆盖旧观察；
   - `M13` 年度行不作为月度事实写入。
6. `persistent_storage` 与 `model_processing` 必须在 Transport 前分别通过用途许可门禁。
   公开展示、商业使用和再分发暂为 `UNVERIFIED`，不得从个人研究许可推断。
7. 每条事实保存 BLS 来源、检索时间、首次观察语义和必要声明；对外报告不得暗示 BLS 对
   QFusion 分析背书。

## 后果

优点：

- 不需要 API key 或付费账户；
- 宏观事实可以合法进入项目本地缓存、持久化和模型路径；
- 缺少 vintage 时仍保持严格、可审计且不会回填的 Point-in-Time 边界；
- 固定 origin、无代理、无重定向和本地预算降低 SSRF、共享环境与配额风险。

限制：

- 首次采集前的历史值只能视为“本次才观察到”，不能用于声称历史决策当时已知；
- v1 的一天发布滞后、无 metadata 和无 vintage 会降低回测覆盖与修订分析能力；
- 本切片不接入 Scheduler、Raw Store、Repository、Snapshot、GUI 或真实在线同步；
- 公开展示、商业使用和再分发仍需单独许可复核；
- 后续若需要严格历史 vintage，应新增经过许可与时间语义审查的来源，不能改写本 Adapter
  已保存的首次观察记录。

## 被否决的替代方案

- FRED/ALFRED：当前用途条款与项目本地缓存、持久化和模型处理冲突。
- BEA API：数据本身可公开使用，但 API 需要注册 key；本切片优先实现无凭证基线。
- Federal Reserve Data Download Program：只有当前修订数据，且服务处于退役迁移阶段，
  不适合作为本切片稳定基线。
- 根据观察月份推测发布日期：会制造前视偏差，明确禁止。
