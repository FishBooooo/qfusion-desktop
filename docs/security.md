# 安全基线

## M0 已实施

- `.env`、密钥格式、本地数据库和构建产物被忽略。
- FastAPI 配置把监听地址限制为 `127.0.0.1`。
- CORS 只允许明确的开发桌面来源。
- OpenAPI 测试确认 M0 只有健康路由。
- 前端拒绝非 localhost 的 API Base URL。
- Tauri 能力文件只启用 `core:default`，没有 shell、文件系统或订单权限。

## M1-E 已验收备份与恢复

- `.qfbak` 清单记录 SQLite/DuckDB Schema、规范相对路径、字节数和逐文件 SHA-256。
- 备份拒绝活动 WAL、符号链接、特殊文件、变化中的 DuckDB 和仓库外路径。
- 恢复不调用通用 ZIP 解压；拒绝路径穿越、重复/额外项、ZIP 符号链接、特殊文件、超限和哈希篡改。
- 归档路径同时满足 Windows 可移植性：拒绝设备保留名、ADS 冒号、控制/非法字符、尾随点或空格，以及大小写不敏感路径冲突。
- 恢复只写唯一 staging，并在服务内锁保护下确认目标不存在后改名；正常流程不覆盖当前用户数据。同一用户外部进程制造目标路径的竞态不受该锁保护，调用方必须保证数据根由 QFusion 独占。
- M1 只支持写入器静止后的离线备份；未加密归档只能保存在受信任介质。

## M2-C1 SEC 公共出站边界

- 只允许固定 HTTPS origin `data.sec.gov:443` 与由精确 10 位 CIK构成的 submissions
  路径；调用方不能传入 URL。
- HTTP 客户端禁用宿主代理和重定向，每次尝试前要求固定主机的全部 DNS 结果均为公网地址。
- 空 DNS、私网、Loopback、链路本地、保留地址、无效 JSON、非预期状态码和契约漂移均
  fail closed。
- 内部限速为每秒最多 5 请求、并发 1；超时、重试次数与等待上限均由冻结配置约束。
- SEC 不需要 API Key；User-Agent 只由运行时类型化配置提供，仓库与日志不保存私人联系
  信息或凭证。
- CI 只使用注入式 Mock Transport 和合成契约 Fixture，不访问 SEC、localhost、局域网、
  容器 Socket 或任何其他工作空间。
- Adapter 只负责采集并标记首次观察时间，事实持久化后仍须经过 Repository/Snapshot 的
  Point-in-Time 守卫；模型不能直接读取 Provider 输出。

该传输边界尚未接入应用组合根或 Scheduler，官方响应 Fixture 和真实公网可达性也尚未在
隔离 Runner 中验证，因此不能宣称 SEC 在线接入已经完成。

## M2-C2a SEC 手动采集门禁

- 工作流只能手动触发，没有 push、PR 或定时 live 请求。
- 公开仓库只保存工作流与校验逻辑；联系标识保存在 GitHub Secret 中，并通过权限
  `0600` 的 Runner 临时文件传递，既不进入 argv，也不进入 Artifact 清单。
- 缺少联系标识、非法 CIK、非公网 DNS、重定向、代理、非 JSON、原始字节不一致或响应
  超限均 fail closed。
- Artifact 只含公开官方响应及其无秘密审计清单，保留 1 天，不自动提交。
- 常规 Linux/Windows CI 仍完全 Mock；门禁合并与跨平台回归没有触发真实 SEC 请求。

M2-C2a 门禁已通过精确提交的 Linux/Windows 验证并合并；审计与隔离证据见
[M2-C2a 验收记录](m2c2a-acceptance.md)。该验收不代表已配置联系标识、执行 live request
或取得官方响应 Fixture。

## M2-D0 供应商使用许可边界

- 技术能力、账户权限和使用许可分别建模，任何一份都不能替代另外两份。
- 缓存、长期持久化、展示、商业使用、再分发和模型处理都需要精确 `ALLOWED`。
- `PROHIBITED` 与 `UNVERIFIED` 统一在副作用前 fail closed，并输出
  `BLOCKED_BY_PROVIDER_LICENSE`。
- SEC filing 持久化校验位于固定 origin Transport 前；许可拒绝测试确认不发起请求。
- FRED/ALFRED 当前条款与 QFusion 本地持久化及模型路径冲突，因此没有 Adapter、key、
  live request、Fixture、缓存或数据库记录。
- 条款 URL、复核日期、署名和提示属于审计数据；真实凭证仍不得进入策略、日志或仓库。

## M2-D1 BLS v1 公共出站边界

- 只允许固定 HTTPS origin `api.bls.gov:443` 与固定 v1 timeseries POST 路径；调用方
  只能提供经过契约验证的序列 ID 和年份，不能提供 URL。
- 客户端禁用宿主代理与重定向，每次尝试前要求全部 DNS 结果为公网地址。
- 请求体不包含 registration key；User-Agent 使用项目运行时声明的产品名与联系地址，
  不保存用户凭证。
- 每次最多 25 个序列和 10 年；项目内预算进一步限制为每日最多 25 次、并发 1，并对
  响应大小、超时、重试和等待设硬上限。
- `persistent_storage` 与 `model_processing` 在 Transport 前分别 fail closed；公开
  展示、商业使用和再分发仍为 `UNVERIFIED`。
- BLS v1 缺少 vintage 和真实 API 发布时间，因此所有事实只在 QFusion 首次收到响应后
  可用，不根据月份或页面发布时间回填。
- CI 只使用合成 Fixture 与 `httpx.MockTransport`；本候选不执行 live BLS 请求，也
  尚未接入组合根、Scheduler、Raw Store 或 Repository。

## 后续必须实现

- 每次启动的临时会话令牌和随机端口握手；
- Windows Credential Manager / Linux Secret Service；
- 结构化日志脱敏；
- Sidecar 参数白名单和单实例写入锁；
- 导入路径与文件类型验证；
- 跨存储在线写入屏障、备份加密选项、密钥管理、恢复切换确认与审计。

当前没有真实密钥、外部账户写入或订单入口。SEC 只存在尚未接入运行时的公共读取边界，
CI 未执行真实供应商请求。任何新增外部写入或实盘能力必须单独评审。
