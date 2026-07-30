# ADR-0014：SEC 官方响应使用手动短期采集门禁

- 状态：Accepted
- 日期：2026-07-30

## 背景

M2-C1 已建立固定 `data.sec.gov` 出站、声明式 User-Agent、首次观察时间和无网络解析
测试，但仓库中的 submissions Fixture 仍是手工合成的 Schema 形状。后续需要一份官方
响应来审计字段漂移，同时常规 CI 不得调用真实供应商，联系标识不得写入公开仓库、日志、
命令行或测试 Fixture。

仓库现为公开仓库并不改变供应商网络和隐私边界。公开可见的代码可以描述采集过程，但运行
时联系标识和采集动作仍必须显式分离。

## 决策

新增仅由 `workflow_dispatch` 触发的 GitHub 托管 Runner 门禁：

1. 工作流没有 `push`、`pull_request` 或定时触发器。
2. 精确 10 位 CIK 是唯一业务输入；URL 仍由 SEC Transport 固定生成。
3. 联系标识只从仓库 Secret `SEC_USER_AGENT` 注入到权限为 `0600` 的 Runner 临时文件，
   不作为进程参数、环境透传、日志字段、清单字段或 Artifact 内容。
4. Secret 缺失、格式不合规或 CIK 非法时，必须在供应商请求前失败。
5. 联网前先运行 SEC 相关 Ruff、mypy 和 Mock-only pytest。
6. Transport 同时保存精确响应字节和解码对象，并要求两者语义一致；响应大小有硬上限。
7. Artifact 只包含原始响应和无秘密清单。清单记录固定来源、CIK、首次接收时间、精确
   commit、run ID、字节数、SHA-256、HTTP 验证头和已验证 filing 数量。
8. Artifact 保留 1 天，不自动提交、不写 Raw Store、不进入常规 Fixture；运行结束后
   删除联系标识临时文件。
9. 常规 CI 和 Windows 构建继续完全使用 Mock，不执行 live SEC 请求。

## 后果

该门禁把“实现安全采集能力”和“实际访问 SEC”分成两个可审查动作。当前代码合并和测试
不需要真实联系标识，也不会产生供应商请求。只有用户后续在 GitHub 中配置合规、可监控的
联系标识并手动触发默认分支工作流，才会生成短期官方响应 Artifact。

取得 Artifact 后仍需单独审查响应内容、许可、字段稳定性和脱敏要求；只有审查通过的最小
Fixture 才能以新的提交进入仓库。该 ADR 不授权 Scheduler、自动联网、Raw Store 持久化、
company facts 或任何付费服务。
