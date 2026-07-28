# ADR-0006：项目本地工具链与干净执行环境

- 状态：Accepted
- 日期：2026-07-27

## 背景

QFusion 与宿主机中的科研工作空间、科研环境和全局开发依赖必须完全隔离。直接继承登录
Shell、用户级缓存、Conda/ROS 环境或全局包管理器状态，会让构建不可复现，也可能影响
与本项目无关的任务。

## 决策

Linux 和 Windows 启动入口都必须先建立 QFusion 专用环境：

- 工具版本和发布文件 SHA-256 记录在 `scripts/toolchain-versions.json`；
- Node.js、uv、Rust/rustup 和 just 安装到仓库内 `.toolchains/`；
- Python 依赖只同步到 `.venv`，pnpm 依赖只同步到本地 `node_modules`；
- uv、Corepack、pnpm、Cargo、Playwright、XDG 和临时文件写入 `.cache/` 或 `.tmp/`；
- Linux 子进程从空环境启动，Windows 显式排除 Conda、ROS、CUDA、容器和代理变量；
- 不读取 `.env`，不修改 Shell 配置，不运行全局 Corepack、npm、pnpm 或 rustup 安装；
- Python、pnpm 和 Cargo 操作分别使用 `--locked`、`--frozen-lockfile` 和 `--locked`。

下载只允许使用记录的 HTTPS URL。校验失败、已有本地工具版本冲突或无法在仓库内完成
安装时，立即停止并输出 `BLOCKED_BY_HOST_ISOLATION`，不得修改宿主环境来规避问题。

## 后果

首次启动需要联网下载经过校验的工具，仓库内会占用额外磁盘空间。普通开发命令需通过
`scripts/run_in_qfusion_env.sh` 或 PowerShell 隔离入口执行。Windows 仍需宿主机已具备
MSVC Build Tools 和 WebView2；本项目脚本不会安装或修改这些系统组件。
