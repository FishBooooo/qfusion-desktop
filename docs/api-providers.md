# 数据供应商登记

状态：M2-D0 结构化供应商使用许可门禁已实现，等待跨平台验证；未执行 FRED 请求。
最后更新：2026-07-30

## 1. 强制登记字段

任何 Provider Adapter 进入代码前必须记录：

- 官方产品/API 名称与版本；
- 按“市场 + 操作”支持的周期、实时、盘前盘后和流式能力；
- 按同一键记录行情是实时、延迟、EOD、历史还是不可用；
- 按“市场 + bars + 周期”记录历史起点；每个受支持周期必须且只能有一个窗口，
  缺失不能视为无限历史，并声明 venue scope 和质量等级；
- rate limit、并发、重试与空响应行为；
- 个人研究、缓存、长期存储、私有/公开展示、商业使用、再分发和模型处理许可；
- 字段来源、时区、`available_at`、修订和公司行为语义。

供应商字段或权限未由官方文档和契约测试验证前，一律标记“待验证”，不能写入生产
Domain 契约。

## 2. 能力与账户权限是两份事实

`ProviderCapability` 描述 Adapter 实现与供应商产品的技术能力；其中市场数据能力通过
`MarketDataCapability` 按精确“市场 + 操作”键声明周期、实时和盘前盘后；每个 bar 周期
通过 `BarHistoryWindow` 单独声明历史起点，且窗口键集合必须与受支持周期集合完全
一致。
`ProviderAccessProfile` 描述当前账户实际验证过的权限，并按相同键记录数据质量、盘前
和盘后权限。两者必须同时通过同一键的校验，不能跨市场或跨操作组合能力，也不能因为产品
支持实时行情或延长时段就推断当前账户有相同权限。

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

### 2.1 使用许可是第三份独立事实

`license_scope` 仍随每条 `DataSourceRecord` 保存，但不能授权缓存、落库、展示或模型使用。
`ProviderCapability` Schema `2.0.0` 强制包含 `ProviderUsagePolicy`，并逐项记录：

```text
personal_research
local_cache
persistent_storage
private_display
public_display
commercial_use
redistribution
model_processing
```

每项只能是 `ALLOWED`、`PROHIBITED` 或 `UNVERIFIED`。只有 `ALLOWED` 可通过
`validate_provider_usage`；其余状态必须在副作用前输出
`BLOCKED_BY_PROVIDER_LICENSE` 并拒绝。`model_processing` 同时覆盖规则、统计、机器学习
和 LLM，不能从“个人研究可用”推断模型可用。完整决策见
[ADR-0015](adr/0015-machine-enforced-provider-usage-policy.md)。

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
| Usage policy | 项目内研究/缓存/持久化/展示/模型处理允许；商业使用和再分发禁止 |
| 网络/凭证 | 不使用 |
| 真实金融数据 | 不包含 |

Mock Adapter 只过滤调用方传入的已通过 `DataSourceRecord` 校验的合成事实。内部 UUID、
供应商不透明证券 ID 与市场必须组成同一条映射；请求中的任一项不匹配都在查询前拒绝。
返回结果按证券、事实类型、事件时间及
`available_at <= decision_time` 过滤。请求起点必须位于按市场时区解释的对应
“市场 + bars + 周期”历史边界内；盘前和盘后分别校验同一键下的产品能力及账户权限。Adapter
在接收输入和返回结果时都深拷贝记录，避免调用方通过嵌套载荷修改内部状态。Mock 不能被
标记为实时或用于交易许可。

市场时区边界不依赖 Windows 宿主数据库：项目通过 `pyproject.toml` 与 `uv.lock` 锁定
`tzdata` 2026.3，standalone 构建显式包含包与数据，并校验美股与港股使用的两个 IANA
zoneinfo 文件。该依赖只安装和打包在 QFusion 项目/Artifact 内。

M2-A 已在精确提交 `a02b18e3375db91d870cef26c310d34a69aede68` 通过 Linux run
30526872201 与 Windows run 30526872204；compiled CLI 时区探针、standalone 健康烟雾
测试和 NSIS 构建均成功。实现已通过 PR #11 合并到 `main`。

## 4. M2-B 证券映射责任

Adapter 不拥有永久证券主键。应用必须先通过 Instrument Registry 在显式
`effective_at`/ `decision_time` 下解析：

```text
market + ticker -> instrument_id
instrument_id + provider_name + market -> provider_instrument_id
```

然后才可构造 M2-A 的双标识请求。供应商不透明 ID 保持大小写和原始语义，不能被当作 ticker
改写；任一市场、UUID 或供应商 ID 不匹配时都必须拒绝。M2-B 只用 Synthetic Mock 验证此
链路，未调用任何真实端点。

## 5. 首批真实供应商计划

下表只表示已选实施方向，不表示已经连接、验证账户权限或获得再分发许可。

| 切片 | 供应商 | 预期用途 | 当前状态 |
| --- | --- | --- | --- |
| M2-C | SEC EDGAR `data.sec.gov` | 美股 submissions、filings、company facts | C2a 手动采集门禁已验收；官方响应、持久化与 company facts 待完成 |
| M2-D | FRED/ALFRED | 美国宏观与 vintage/realtime period | `BLOCKED_BY_PROVIDER_LICENSE`；不创建 Adapter、不配置 key、不调用 |
| M2-E | Tiingo | 美股 EOD/历史行情候选 | 官方契约研究完成；需要用户自带 token，许可待账户验证 |
| M2-F | Longbridge OpenAPI | 港股行情候选 | 官方契约研究完成；实际账户行情权限必须运行时验证 |

### 5.1 M2-C1 SEC submissions recent 边界（已验收）

| 字段 | 值 |
| --- | --- |
| Provider | `sec-edgar` |
| Provider version | `1.0.0` |
| 市场/资产 | US；stock、ADR、ETF、sector ETF |
| 当前操作 | filings：`submissions/CIK##########.json` 的 `filings.recent` |
| 标识 | Instrument Registry 解析的内部 UUID + 精确 10 位 CIK |
| 数据质量 | `official-public-filings` |
| License scope | `public-government-content` |
| 凭证 | 无；真实请求必须声明产品/组织和联系邮箱 |
| 内部限流 | 每秒最多 5 次，并发 1 |
| 网络 | 固定 `https://data.sec.gov:443`，禁代理、重定向和任意 URL |

采集与决策查询严格分离。Adapter 把 SEC acceptance datetime 记为 `published_at`，把
QFusion 首次实际收到响应的时间记为 `available_at`，并返回事实供 Repository
持久化；模型不能直接调用 Adapter。后续 Repository 与 Snapshot Builder 才执行
`available_at <= decision_time`，既不会丢弃刚采集的数据，也不会把它回填成历史时点
已知事实。

仓库 Fixture 只是依据公开字段说明手工构造的契约形状，明确不是 SEC 官方响应，也不包含
真实发行人数据。当前实现未接入 Scheduler、Raw Store 或观察池，没有执行 live request，
也未完成 company facts。进入下一切片前仍必须在隔离 Runner 中取得并审计官方响应 Fixture，
记录原始摘要和字段漂移测试。完整决策见
[ADR-0013](adr/0013-sec-edgar-public-egress.md)，精确跨平台证据见
[M2-C1 验收记录](m2c1-acceptance.md)。实现已通过 PR #15 合并到 `main` 提交
`ab50e28c16c4dd6b8908ee7e37fdd2ab98bc65f0`。

### 5.2 M2-C2a 官方响应采集门禁（已验收，未执行 live request）

官方响应只能由默认分支的手动 GitHub 工作流取得。工作流先验证精确 CIK 和仓库 Secret
`SEC_USER_AGENT`，再运行无网络 SEC 测试，最后通过 M2-C1 的固定 origin Transport
执行一次请求。原始字节与解码对象必须一致，且受 10 MiB 默认、50 MiB 绝对上限保护。

短期 Artifact 只包含原始响应和无秘密清单，保留 1 天，不自动写入仓库或 Raw Store。
门禁实现的精确提交已通过 Linux/Windows 跨平台回归，并通过
[PR #17](https://github.com/FishBooooo/qfusion-desktop/pull/17) squash 合并到 `main`
提交 `bff5094302152f05cbf45162fe9b066743b08a8f`。完整证据见
[M2-C2a 验收记录](m2c2a-acceptance.md)，设计决策见
[ADR-0014](adr/0014-manual-sec-official-capture.md)。

该验收没有执行 live request，也不代表官方 Fixture 已取得或审查。

### 5.3 M2-D0 结构化使用许可门禁

M2-D0 将供应商用途从自由文本标签升级为可执行契约。SEC filing 采集在发起 Transport
请求前校验 `persistent_storage`；测试会把该权限改为 `PROHIBITED` 并确认请求在网络前
失败。Synthetic Mock 同样声明精确用途，且必须继续显示合成数据提示。

2026-07-30 的官方条款复核确认，当前 FRED 条款禁止存储、缓存或归档 FRED 内容，也禁止
把 FRED 内容用于软件、机器学习或 AI 系统相关开发/训练。该边界与 QFusion 的 Raw Store、
离线缓存、DuckDB/Parquet 和模型输入要求直接冲突，因此 M2-D 不会通过“只加 API key”
继续。BLS、BEA、Treasury 等原始官方来源只是候选，必须分别完成许可、修订、
`available_at` 和 vintage 语义审查后再选定。

官方依据：

- SEC：[EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) 与
  [Developer Resources](https://www.sec.gov/about/developer-resources)；
- FRED：[Services Terms of Use](https://fred.stlouisfed.org/legal/terms/) 与
  [API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html)；
- Tiingo：[General Documentation](https://www.tiingo.com/documentation/general) 与
  [End-of-Day API](https://www.tiingo.com/documentation/end-of-day)；
- Longbridge：[OpenAPI Documentation](https://open.longbridge.com/docs) 与
  [Quote Overview](https://open.longbridge.com/docs/quote/overview)。

真实 Adapter 必须使用官方响应 Fixture 做解析测试，CI 禁止调用真实端点。付费订阅、真实
凭证注入和外部账户写入不在默认授权范围内。

## 6. 后续门禁

1. M2-B 的 Instrument Registry 已完成；真实 Adapter 只能接收其解析出的永久 UUID 与
   供应商不透明标识，ticker 不能作为永久主键。
2. M2-C1 SEC submissions 采集边界与 M2-C2a 手动采集门禁已完成；实际官方响应、
   Fixture 审查、持久化与 company facts 仍是 M2-C 后续门禁。
3. M2-D 的 FRED/ALFRED 方向因当前条款保持 `BLOCKED_BY_PROVIDER_LICENSE`；不得创建
   会缓存、持久化或进入模型的 FRED Adapter。宏观替代来源必须先单独通过用途许可门禁。
4. 每个 Adapter 必须覆盖限流、超时、重试、空响应、字段变化、时区、休市、修订和延迟
   标记测试。
5. M2-G 才接入观察池增量同步和 GUI 数据状态；在此之前不声明 M2 完成。
