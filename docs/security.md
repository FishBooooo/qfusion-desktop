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

## 后续必须实现

- 每次启动的临时会话令牌和随机端口握手；
- Windows Credential Manager / Linux Secret Service；
- 结构化日志脱敏；
- Sidecar 参数白名单和单实例写入锁；
- 导入路径与文件类型验证；
- 跨存储在线写入屏障、备份加密选项、密钥管理、恢复切换确认与审计。

当前没有真实密钥、外部账户写入或订单入口。SEC 只存在尚未接入运行时的公共读取边界，
CI 未执行真实供应商请求。任何新增外部写入或实盘能力必须单独评审。
