# QFusion Desktop 路线图

状态：M0 基线已创建，等待 Windows CI/安装包验收  
最后更新：2026-07-27  
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
- [x] 运行当前环境能够支持的测试并记录缺口

退出条件：

1. Linux 环境可启动后端并执行后端测试。
2. 项目本地 Node/Rust 工具链安装后，前端可构建、类型检查并测试。
3. Windows CI 能构建空安装包；必须由真实 Windows Runner 验证。
4. 前端能显示 Mock 数据并报告后端在线或离线状态。

当前证据：

- 后端 Ruff、mypy、8 项 pytest 和 Nuitka standalone 健康烟雾测试通过；
- 前端 ESLint/Prettier、TypeScript、2 项 Vitest、生产构建和 1 项 Playwright 前后端集成测试通过；
- Node 22.23.1、pnpm 10.13.1、uv 0.11.16、Rust 1.97.1/rustup 1.29.0 与 just
  1.50.0 已通过 SHA-256 校验安装到仓库内；缓存、临时文件和工具链均使用项目路径；
- 当前 `node_modules` 仍记录仓库外 pnpm Store。为避免清空或替换已有依赖，bootstrap
  已按隔离规则输出 `BLOCKED_BY_HOST_ISOLATION` 并停止；
- 已在仓库内临时副本使用独立 Store 从零安装锁定的 416 个包；28 个直接依赖版本、
  完整锁哈希和生成客户端均一致，前端 Lint、类型检查、2 项 Vitest 与生产构建通过，
  且原 `node_modules` 的哈希、inode 和时间戳未变化。该证据不代表已迁移活动依赖树；
- pnpm 隔离检查器已支持 pnpm 10 的项目内 `store/v10` 元数据，并拒绝未版本化、其他
  版本、路径穿越、仓库外和符号链接路径；14 项边界测试通过，当前外部 Store 活动树仍
  按预期阻断；
- Gate A 已使用最终项目 Store `.cache/pnpm/store/v10` 从锁文件下载 416 个包且外部
  Store 复用为 0；28 个直接依赖、完整锁、OpenAPI 和生成客户端均一致，1,311 个候选
  链接全部留在候选工作区，离线幂等安装、Lint、类型检查、2 项 Vitest 与生产构建通过；
  活动依赖树仍未迁移且哈希、inode 和时间戳未变化；
- Tauri CLI 成功解析应用、CSP 和 bundler 配置，Rust fmt 与锁定元数据通过；
- 本 Linux 主机缺少 `pango`、`gdk-3.0`、`webkit2gtk-4.1` 和 `rsvg2`，因此原生 `cargo check/test/clippy` 未完成；
- 当前目录尚不是 Git 仓库，Windows GitHub Actions 工作流尚未被实际触发。

因此 M0 尚不能标记完成，也不能进入 M1。

## M1：本地存储与数据契约

建立 SQLite、DuckDB、Parquet、Repository Interface、迁移、备份恢复和 `AnalysisSnapshot`。所有事实必须包含来源、时间、修订、质量和版本字段。

入口条件：M0 退出条件全部满足。  
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

在干净 Windows 10/11 环境完成 Sidecar 打包、NSIS 安装、升级、卸载、备份恢复和烟雾测试。卸载默认保留用户数据。
