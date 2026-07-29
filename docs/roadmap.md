# QFusion Desktop 路线图

状态：M0 验收候选已通过 GitHub 托管 CI，Draft PR #1 待审查合并
最后更新：2026-07-29
最高依据：[PROJECT_TASKBOOK.md](../PROJECT_TASKBOOK.md)

## 里程碑门禁

任何里程碑只有在退出条件有实际测试证据后才能标记完成。未运行的 Windows、供应商或金融逻辑测试必须明确保留为限制，不能用静态检查替代。

## M0：项目基线

目标是建立可运行、可测试、可审查的最小骨架，不进入存储、供应商或真实模型实现。

- [x] 规范化任务书与必读文档
- [x] 记录 5 项基础 ADR
- [x] 创建 Python/FastAPI 健康检查
- [x] 创建 React/Tauri 空壳
- [x] 创建前后端健康通信演示
- [x] 创建合成 Mock 股票分析页
- [x] 创建统一 Linux 开发命令
- [x] 创建 Linux CI 与 Windows 构建骨架
- [x] 运行 M0 所需的 Linux 与 Windows 验证并记录证据

退出条件：

1. Linux 环境可启动后端并执行后端测试。
2. 项目本地 Node/Rust 工具链安装后，前端可构建、类型检查并测试。
3. Windows CI 能构建空安装包；必须由真实 Windows Runner 验证。
4. 前端能显示 Mock 数据并报告后端在线或离线状态。

### 验收候选

验证对象为 `fix/m0-ci-isolation` 分支代码提交
`ed6fffdaa785e018ebf051d073b7cba070cac423`。变更通过
[Draft PR #1](https://github.com/FishBooooo/qfusion-desktop/pull/1) 提交审查，尚未合并到
`main`。

Linux 证据来自 GitHub 托管 `ubuntu-latest`：
[CI run 30430746448](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30430746448)。

- Ruff 与 mypy 通过，mypy 检查 27 个 Python 源文件。
- 22 项 pytest 全部通过；保留 1 条 Starlette `TestClient` 弃用警告。
- OpenAPI 与生成客户端重新生成后无差异。
- ESLint、Prettier、两套 TypeScript 检查、2 项 Vitest 和 Vite 生产构建通过。
- Playwright 前后端集成测试 1 项通过。后端 PID 2937 使用动态端口 37125，前端 PID
  2944 使用动态端口 41371；均只绑定 Runner 自身 `127.0.0.1`，记录工作目录并通过持有
  的子进程句柄核验身份后停止。
- Node 22.23.1、pnpm 10.13.1、uv 0.11.16、Rust 1.97.1/rustup 1.29.0 与 just
  1.50.0 均由仓库内版本清单和 SHA-256 约束，缓存、临时文件与工具链使用项目路径。

Windows 证据来自 GitHub 托管 `windows-latest`：
[Windows M0 Build run 30430746596](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30430746596)。

- Rust fmt、clippy 和 test 通过；当前 Rust 空壳没有业务单元测试。
- Ruff、mypy、22 项 pytest、前端 Lint、类型检查、2 项 Vitest 和生产构建通过。
- Nuitka standalone 实际完成编译与链接，输出
  `dist/backend/qfusion.dist/qfusion-backend.exe`。构建清单记录的可执行文件 SHA-256
  为 `b910fa57bb67b1a01046e9f13d552e3f28b0cf0607461805e94531caed50c1cb`。
- 独立后端可执行文件在动态 `127.0.0.1:52277` 上完成健康烟雾测试；测试记录 PID
  7032、启动时间、工作目录和用途，校验文件哈希及精确 M0 健康响应后核验进程身份并停止。
- Tauri release 构建完成，生成
  `apps/desktop/src-tauri/target/release/bundle/nsis/QFusion Desktop_0.1.0_x64-setup.exe`。
- 后端构建产物 ID 8716425226，GitHub Artifact ZIP SHA-256 为
  `533980c0d22325d0dc0be35e287babbcf7ff3090692b47b62a612d035703a9b0`。
- NSIS 空壳安装包产物 ID 8716426029，GitHub Artifact ZIP SHA-256 为
  `94b34f7486f66a915dbd5801b8ed364eb6a491de657269f9fc83e050d94a74b4`。
- 两个产物当前计划于 2026-10-27 到期；它们是 M0 验收证据，不是正式发行版。

本机现有 `node_modules` 仍记录仓库外 pnpm Store。它没有被清空、迁移或用于上述 CI；
GitHub 托管 Runner 从锁文件在独立工作区重建依赖，因此 M0 候选验证不会读取或改变宿主
旧依赖树。Gate B 活动依赖树迁移仍未授权，也不是本次 M0 CI 修复的一部分。

该候选已满足 M0 的四项技术退出条件。由于证据提交仍位于 Draft PR，`main` 尚未包含
修复；在 PR 审查并合并或用户明确验收前，不进入 M1。

## M1：本地存储与数据契约

建立 SQLite、DuckDB、Parquet、Repository Interface、迁移、备份恢复和
`AnalysisSnapshot`。所有事实必须包含来源、时间、修订、质量和版本字段。

入口条件：M0 退出条件全部满足且验收候选已进入目标分支。
退出条件：可写入并查询 Mock 日线、分钟线、公告和新闻，且能生成可复现快照。

## M2：首批数据适配器

实现 SEC、FRED、一个美股行情源、一个港股行情源和必要的 Mock Adapter。逐一验证许可、字段、限流、时区、休市和延迟状态。

## M3：因子和特征系统

实现版本化的技术、基本面、宏观、事件、期权、板块宽度与主题特征。建立 Point-in-Time 和无泄漏测试。

## M4：三套独立模型 V0

实现华尔街规则模型、量化基线和游资状态机。三者只使用同一快照，独立运行、分别持久化、均可输出 `NO_TRADE`。

## M5：融合与风险引擎

实现 Fusion Packet 验证、周期对齐、置信度校准、分歧惩罚和独立全局风险否决。

## M6：完整 GUI

完成 Dashboard、股票与板块分析、四视角对比、数据中心、模型中心、设置和 Token 面板。

## M7：回测与模拟交易

完成含成本和滑点的可复现回测、模拟账户、交易日志与绩效归因；验证无已知前视偏差。

## M8：Windows 正式打包

在干净 Windows 10/11 环境完成 Sidecar 集成、NSIS 安装、首次启动、升级、卸载、备份恢复和烟雾测试。卸载默认保留用户数据。
