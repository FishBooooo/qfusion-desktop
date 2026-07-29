# QFusion Desktop

QFusion Desktop 是一个本地优先的美股与港股科技板块“3+1”多视角交易决策平台。项目当前处于 **M1 本地存储与数据契约阶段**：M0 桌面基线与 M1-A Point-in-Time 契约已经验收，正在落地可迁移的本地存储。

> 当前版本不连接真实行情、不运行交易模型、不提供投资建议，也不存在实盘提交路径。M1-B 仅持久化合成测试使用的分析快照元数据。

## 架构不变量

- 华尔街、量化和游资模型共享同一个数据快照，但互相不能读取结论。
- 融合模型只读取验证后的 Fusion Packet。
- 所有融合结果必须经过独立全局风险引擎。
- ticker 不是永久证券主键。
- 数值计算、时间有效性、成本、仓位和风险许可不交给 LLM。

完整约束见 [PROJECT_TASKBOOK.md](PROJECT_TASKBOOK.md)，架构基线见 [docs/architecture.md](docs/architecture.md)。

## 目录

```text
apps/desktop/          React + Tauri 桌面空壳
services/backend/      FastAPI Sidecar
packages/contracts/    导出的 OpenAPI 契约
packages/generated-client/  OpenAPI 生成的 TypeScript 类型
docs/                  架构、模型、GUI、部署与 ADR
fixtures/              只包含明确标记的合成测试数据
scripts/               开发与构建脚本
```

## 开发前置

- Linux：系统只需提供 Python 3.12、`curl`、`tar`、`xz` 和 SHA-256 校验工具；
- Linux：原生 Tauri 检查还需要 Tauri 2 的 GUI 系统库；
- Windows：PowerShell 7、MSVC C++ Build Tools 与 WebView2。

Node.js、pnpm、uv、Rust/rustup 和 `just` 使用
[`scripts/toolchain-versions.json`](scripts/toolchain-versions.json) 中的精确版本及校验值，
并只安装到仓库内 `.toolchains/`。所有缓存和临时文件写入 `.cache/` 与 `.tmp/`；
不会修改用户 Shell、全局包管理器或已有科研环境。

## 快速开始（Linux）

```bash
./scripts/bootstrap_linux.sh
./scripts/run_in_qfusion_env.sh just test
```

首次启动会从官方发布源下载并校验项目本地工具，然后使用现有锁文件同步依赖。后续命令
仍以 `justfile` 中的统一命令为准，但必须通过隔离执行器运行。例如：

```bash
./scripts/run_in_qfusion_env.sh just lint
./scripts/run_in_qfusion_env.sh just typecheck
./scripts/run_in_qfusion_env.sh just run-backend
./scripts/run_in_qfusion_env.sh just run-desktop
```

Windows 首次启动使用 `pwsh -NoProfile -File scripts/bootstrap_windows.ps1`，Windows 构建
使用 `pwsh -NoProfile -File scripts/build_windows.ps1`。两个入口都会清除冲突的科研环境
变量并将工具、缓存和临时文件限制在当前仓库。

如果现有 `node_modules` 是由仓库外 pnpm Store 创建，bootstrap 会输出
`BLOCKED_BY_HOST_ISOLATION` 并保留它，不会确认 pnpm 的清空重装提示。迁移该目录必须
作为单独任务获得明确批准。

开发后端默认监听 `127.0.0.1:8000`。桌面开发服务器使用 `127.0.0.1:1420`。固定端口仅用于 M0 开发演示，正式 Sidecar 将使用随机端口和临时会话令牌。

## 统一命令

```text
just setup
just lint
just typecheck
just test
just test-backend
just test-frontend
just test-e2e
just run-backend
just run-desktop
just build-backend
just build-windows
```

Windows 安装包必须在真实 Windows 环境或 Windows CI Runner 构建。当前验证状态见 [docs/roadmap.md](docs/roadmap.md)。
