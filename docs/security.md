# 安全基线

## M0 已实施

- `.env`、密钥格式、本地数据库和构建产物被忽略。
- FastAPI 配置把监听地址限制为 `127.0.0.1`。
- CORS 只允许明确的开发桌面来源。
- OpenAPI 测试确认 M0 只有健康路由。
- 前端拒绝非 localhost 的 API Base URL。
- Tauri 能力文件只启用 `core:default`，没有 shell、文件系统或订单权限。

## 后续必须实现

- 每次启动的临时会话令牌和随机端口握手；
- Windows Credential Manager / Linux Secret Service；
- 结构化日志脱敏；
- Sidecar 参数白名单和单实例写入锁；
- 导入路径与文件类型验证；
- 备份加密选项与恢复审计。

M0 没有真实密钥、账户、供应商请求或订单入口。任何新增外部写入或实盘能力必须单独评审。
