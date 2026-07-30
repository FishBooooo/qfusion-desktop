# M2-C1 SEC EDGAR Adapter 边界验收

状态：Accepted  
日期：2026-07-30  
实现 PR：[PR #15](https://github.com/FishBooooo/qfusion-desktop/pull/15)

## 1. 验收范围

M2-C1 只验收 SEC EDGAR submissions recent 的安全采集边界，不宣称 SEC 在线接入或整个
M2-C 已完成。

已验收：

- 无凭证、filings-only 的 SEC capability/access 契约；
- Instrument Registry 解析的永久 `instrument_id` 与精确 10 位 CIK 请求边界；
- `filings.recent` 列式数组的严格、前向兼容解析；
- SEC acceptance 作为 `published_at`，QFusion 首次响应接收时间作为
  `available_at`；
- Adapter 负责采集并返回新观察事实，Repository/Snapshot 独立执行
  `available_at <= decision_time`；
- 固定 `https://data.sec.gov:443`、禁宿主代理、禁重定向、全公网 DNS、并发 1、
  每秒最多 5 次和有界重试；
- 合成 Schema Fixture、注入式 Mock Transport 和无网络测试；
- `httpx` 以同一锁定版本从开发依赖提升为运行时依赖，没有其他包版本变化；
- Linux/Windows exact-head 回归、Nuitka standalone 烟雾测试和 NSIS 构建。

## 2. 提交与审查

精确测试提交为 `8619df35f457efaf134b9796e1bc92cdb3e2c835`。合并前 PR 相对
`main` 落后 0 个提交，且没有评论、评审提交或未解决线程。

PR #15 已 squash 合并到 `main` 提交
`ab50e28c16c4dd6b8908ee7e37fdd2ab98bc65f0`。

## 3. Linux 证据

[CI run 30542904326](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30542904326)
在精确测试提交上通过：

- Ruff 与 49 个 Python 源文件的 mypy 通过；
- 189 项 pytest 全部通过，总覆盖率 93%，保留 1 条已知 Starlette 弃用警告；
- 1 个测试文件中的 2 项 Vitest、TypeScript 与 Vite 生产构建通过；
- 1 项动态 Loopback Playwright E2E 通过；
- E2E 后端 PID/端口为 3650/44265，前端为 3660/38549，均由测试持有进程句柄并在
  身份核验后停止；
- OpenAPI、生成客户端、Domain Schema 与 `uv.lock` 无漂移。

## 4. Windows 证据

[Windows run 30543035477](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30543035477)
在同一精确测试提交上通过：

- Rust fmt/clippy/test、Ruff、49 个源文件的 mypy、189 项 pytest、93% 覆盖率、
  前端 Lint/类型检查和 2 项 Vitest 全部通过；
- Nuitka standalone EXE SHA-256 为
  `0dfddd4f7ed1de1e17db9bf29287bf2fdeac7772fd436016307529d10cc65f0e`；
- 打包迁移 head 为 `0002_m2b_instruments`，两个项目本地 IANA 时区资产通过验证；
- 独立后端由受控 PID 2044 在动态端口 56056 完成健康烟雾测试，并在身份核验后停止；
- Tauri release 生成 `QFusion Desktop_0.1.0_x64-setup.exe`；
- 后端 Artifact ID 8760836913，大小 148,004,426 bytes，ZIP SHA-256 为
  `34adaa806e9e7fd3db38e438ff77b3f071998c78c0bbbc80cd790bedb65f328c`；
- NSIS Artifact ID 8760837971，大小 1,249,157 bytes，ZIP SHA-256 为
  `bc58fa375c19f3e329128b76b3b5e8873d2e9f556d3fa73abbc6c6da6c2a2e02`；
- 两个 Artifact 计划于 2026-08-06 到期，只作为验收证据，不是正式发行版。

## 5. 隔离证明

验证只运行在 GitHub 托管的 QFusion 专用 Runner。常规 CI 没有执行 live SEC 请求，也没有
访问宿主机、兄弟工作区、`franka-setup`、局域网、容器 Socket 或外部账户。E2E 和
standalone 只连接各自 Runner 内由当前测试直接启动并持有的动态 Loopback 进程。

## 6. 明确保留项

以下项目仍属于 M2-C 后续工作：

- 在隔离 Runner 中取得、审计并固定 SEC 官方响应 Fixture；
- Raw Store 原始响应和 Repository 增量持久化；
- 观察池 Scheduler、空响应、分页文件与字段漂移处理；
- 只有在 accession 可证明关联 filing availability 后实现 company facts；
- 在线可达性和声明式 User-Agent 的受控验证。

因此 M2-C1 已验收，但 M2-C 与整个 M2 仍未完成。
