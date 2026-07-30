# M2-C2a SEC 官方响应手动采集门禁验收

状态：Accepted（仅验收采集门禁；未执行 live SEC request）
日期：2026-07-30
实现 PR：[PR #17](https://github.com/FishBooooo/qfusion-desktop/pull/17)

## 1. 验收范围

M2-C2a 只验收“如何在隔离 GitHub Runner 中人工取得一份可审计 SEC 官方响应”的代码与
执行门禁。它不宣称 SEC 在线接入、官方响应 Fixture、Raw Store 持久化或整个 M2-C 已完成。

已验收：

- SEC Transport 保留精确响应字节、首次接收时间、Content-Type、ETag 与 Last-Modified，
  并要求原始 JSON 对象与已解码载荷语义一致；
- `Content-Length` 和流式读取均执行大小上限，默认 10 MiB、绝对上限 50 MiB；请求固定
  `Accept-Encoding: identity`；
- 审计清单记录固定来源 URL、CIK、原始文件名、commit、run ID、接收时间、字节数、
  SHA-256、验证头和已解析 filing 数量，不记录运行时联系标识；
- 捕获 bundle 精确写入原始字节和清单，并拒绝覆盖既有输出目录；
- CLI 只从仓库 `.tmp/` 下无符号链接、权限不超过 `0600` 的 UTF-8 文件读取
  User-Agent，联系标识不进入 argv 或成功日志；
- GitHub 工作流只有 `workflow_dispatch` 触发器、contents read 权限、固定标准
  `ubuntu-latest` Runner、同一 CIK 串行门禁和 20 分钟超时；
- 缺少 `SEC_USER_AGENT`、非法 CIK 或无网络预检失败时均在供应商请求前停止；
- 常规 Linux/Windows CI 保持 Mock-only，手动采集结果只进入保留 1 天的 Artifact，
  不自动提交、不写 Raw Store；
- ADR-0014、供应商、安全、测试、架构和路线图文档已同步。

## 2. 提交与审查

精确测试提交为 `d60c5f31302c558dd3d11789e6269335c9d6ce6f`。合并前 PR 相对
`main` 落后 0 个提交、可合并，且没有评论、评审提交或未解决线程。

PR #17 已 squash 合并到 `main` 提交
`bff5094302152f05cbf45162fe9b066743b08a8f`。

本切片没有新增、升级、降级或重锁依赖；`pyproject.toml`、`uv.lock`、所有
`package.json`、`pnpm-lock.yaml`、`Cargo.toml` 和 `Cargo.lock` 均未修改。

## 3. Linux 证据

[CI run 30549140882](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30549140882)
的作业 `90892933533` 在精确测试提交上通过：

- 锁更新守卫确认所有既有 Python 包版本保持不变，最终 `uv.lock` 无漂移；
- Workspace baseline schema 1、里程碑 M2 验证通过；
- Ruff 与 50 个 Python 源文件的 mypy 通过；
- 194 项 pytest 全部通过，总覆盖率 92.73%（显示为 93%），保留 1 条已知
  Starlette 弃用警告；
- 1 个测试文件中的 2 项 Vitest、TypeScript 与 Vite 生产构建通过；
- 1 项动态 Loopback Playwright E2E 通过；
- E2E 后端 PID/端口为 3705/40059，前端为 3715/39763，均由测试持有进程句柄并在
  身份核验后停止；
- OpenAPI、生成客户端、Domain Schema 和依赖锁均无漂移；
- 该运行没有执行手动 SEC 工作流，也没有 live 供应商请求。

## 4. Windows 证据

[Windows run 30549332084](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30549332084)
的作业 `90893592598` 在同一精确测试提交上通过：

- 项目本地锁定工具链、Python 依赖和 Node 依赖同步通过；
- Rust fmt/clippy/test、Ruff、50 个源文件的 mypy、194 项 pytest、92.73% 覆盖率、
  前端 Lint/类型检查、2 项 Vitest 和生产构建全部通过；
- Nuitka standalone EXE SHA-256 为
  `735904b477631faef8228b37a3acac9090f0c49939bada17853802ae49283f2a`；
- 打包迁移 head 为 `0002_m2b_instruments`，两个项目本地 IANA 时区资产通过验证；
- 独立后端由受控 PID 5184 在动态端口 54597 完成健康烟雾测试，并在身份核验后停止；
- Tauri release 生成 `QFusion Desktop_0.1.0_x64-setup.exe`；
- 后端 Artifact ID 8763597635，大小 148,004,553 bytes，ZIP SHA-256 为
  `f47ae394be68992d1cd8039739cb317fd1dacad737052057e0ff39ca17719243`；
- NSIS Artifact ID 8763598519，大小 1,249,323 bytes，ZIP SHA-256 为
  `7b749ffae13705207fcfc23b62597054932783081f049bca38772fe5173ec13d`；
- 两个 Artifact 计划于 2026-08-06 到期，只作为回归证据，不是正式发行版；
- Windows 回归没有执行手动 SEC 工作流，也没有 live 供应商请求。

## 5. 隔离证明

验证只运行在 GitHub 托管的 QFusion 专用 Runner。常规 CI 没有访问本机、兄弟工作区、
`franka-setup`、局域网、容器 Socket、科研环境或外部账户。E2E 与 standalone 只连接
各自 Runner 内由当前测试直接启动并持有的动态 Loopback 进程。

手动采集工作流已随代码进入默认分支，但本次验收没有配置联系标识、没有调度该工作流、
没有向 SEC 发出请求，也没有生成官方响应 Artifact。

## 6. 候选修复记录

进入精确绿色提交前，候选运行曾发现并修复：

- `scripts/capture_sec_fixture.py` 的 Ruff `PTH100` 报告；实现保留词法规范化并记录
  `resolve()` 会在拒绝前跟随符号链接的理由；
- 有界流读取辅助方法误放入 Protocol 导致的 mypy 错误；方法已移回具体 Transport。

两次失败均在后续门禁前停止。只有最终精确提交的完整 Linux 与 Windows 成功结果被用于
本验收。

## 7. 明确保留项

以下项目仍属于 M2-C 后续门禁：

- 由用户在 GitHub 仓库 Secret 中配置合规、可监控的 `SEC_USER_AGENT`；
- 在默认分支人工触发一次固定 CIK 的官方响应采集；
- 审查短期 Artifact 的响应内容、摘要、字段、许可和脱敏要求；
- 只在审查通过后固定最小官方 Fixture 并增加字段漂移测试；
- 将原始响应写入 Raw Store，并通过 Repository 增量持久化 filing metadata；
- 接入观察池 Scheduler、空响应、分页文件和 company facts 的严格可用时间语义。

因此 M2-C2a 的采集门禁实现已验收，但真实 SEC 可达性、官方响应 Fixture、M2-C 与整个
M2 仍未完成。
