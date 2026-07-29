# Windows 部署基线

状态：M0 GitHub 托管 Windows 构建与独立后端烟雾测试已通过
最后更新：2026-07-29

## 1. 交付目标

正式版本面向 Windows 10/11，以 Tauri 2 生成当前用户级 NSIS `setup.exe`。用户不需要预装 Python、Node.js 或 Docker Desktop。

## 2. 进程生命周期

正式流程：

```text
QFusion.exe
  → 生成临时会话令牌
  → 启动已编译 Python Sidecar
  → Sidecar 绑定 127.0.0.1 随机端口
  → 受控握手返回端口和健康状态
  → React 携带会话令牌连接
  → 加载缓存并执行增量检查
```

后端只监听 localhost，使用精确 CORS，支持优雅退出和单写入实例锁。M0 开发模式中的固定
`127.0.0.1:8000` 仅用于人工通信演示；自动化测试使用操作系统分配的动态 Loopback
端口。Tauri 启动 Sidecar、临时会话令牌和动态端口握手仍属于后续 Windows 集成工作。

## 3. 构建组成

- Python 3.12+；
- `uv` 管理 Python 依赖；
- Nuitka standalone 优先构建 Sidecar，PyInstaller 仅作备选；
- Node.js + pnpm 构建 React；
- Rust MSVC 工具链构建 Tauri；
- Tauri NSIS bundler 生成安装程序。

项目脚本不会调用全局安装器。`scripts/build_windows.ps1` 通过
`scripts/toolchain-versions.json` 中的固定版本和 SHA-256，把 Node.js、uv、Rust/rustup
与 just 安装到仓库内 `.toolchains/`，并将依赖、包管理器缓存和临时文件写入仓库内。
脚本不加载 PowerShell Profile，不修改用户配置、系统工具链或现有科研环境。

Windows 原生命令启用严格失败传播：任一外部可执行文件返回非零状态时，构建立即失败，
后续测试、打包和 Artifact 上传不会继续。该规则已在修复过程中的失败运行中实际证明，
避免把失败的 Nuitka 或 Rust 构建误报为成功。

应用图标的唯一源文件是 `apps/desktop/src-tauri/app-icon.svg`。构建脚本在依赖安装后
使用锁定的 Tauri CLI 将它生成到被忽略的 `src-tauri/icons/`，随后才运行 Rust 检查和
NSIS 构建，避免提交平台生成物或依赖宿主图形工具。

Windows Nuitka 构建使用项目本地缓存，并启用内置 `pefile` 依赖扫描方式，避免下载或
调用 Dependency Walker。构建成功后生成 `dist/backend/build-manifest.json`，记录相对
可执行文件路径与 SHA-256。M0 的后端与桌面安装包仍是两个独立 Artifact；将 Sidecar
复制为带 Tauri 目标三元组的 `externalBin` 并由桌面端启动属于 M8。

## 4. 独立后端烟雾测试

`scripts/smoke_backend_standalone.py` 只验证本次构建生成的 Windows 可执行文件：

1. 解析构建清单，拒绝越出 `dist/backend` 的路径；
2. 重新计算 SHA-256 并与清单比较；
3. 由操作系统分配动态 `127.0.0.1` 端口；
4. 记录 PID、启动时间、工作目录、端口和用途；
5. 禁止 HTTP 重定向，只请求精确 `/api/v1/health`；
6. 验证 M0 健康响应；
7. 停止前再次核验所持进程对象和身份。

日志与运行记录写入 Runner 当前仓库内的 `.tmp/`，不连接本机、局域网、科研服务或其他
进程。

## 5. 用户数据

默认数据目录：

```text
%LOCALAPPDATA%\QFusion\
```

程序升级保留数据。卸载默认不删除用户数据，只有用户明确选择后才允许删除。安装文件与用户数据库必须分离。

## 6. Windows CI

M0 工作流只使用 GitHub 托管的 `windows-latest` Runner，不使用本机或自托管 Runner。
工作流执行：

1. 仅检出当前 QFusion commit；
2. 通过项目脚本安装锁定的项目本地工具链和依赖；
3. 生成桌面图标和 OpenAPI 客户端并保持锁文件不变；
4. 运行后端 Ruff、mypy 和 pytest；
5. 运行前端 Lint、类型检查、Vitest 和 Web 构建；
6. 运行 Rust fmt、clippy 和 test；
7. 完成 Nuitka standalone 编译并执行独立 EXE 健康烟雾测试；
8. 构建 Tauri release 与 NSIS 空壳安装包；
9. 仅在上述步骤全部成功后上传两个独立 Artifact。

代码提交 `ed6fffdaa785e018ebf051d073b7cba070cac423` 的
[Windows M0 Build run 30430746596](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30430746596)
已通过：

- 22 项 pytest 与 2 项 Vitest 通过，Rust fmt、clippy 和 test 通过；
- standalone EXE 为 `dist/backend/qfusion.dist/qfusion-backend.exe`，SHA-256 为
  `b910fa57bb67b1a01046e9f13d552e3f28b0cf0607461805e94531caed50c1cb`；
- EXE 在动态端口 52277 完成健康烟雾测试；
- 生成 `QFusion Desktop_0.1.0_x64-setup.exe`；
- 后端 Artifact ID 8716425226，ZIP SHA-256 为
  `533980c0d22325d0dc0be35e287babbcf7ff3090692b47b62a612d035703a9b0`；
- 桌面 Artifact ID 8716426029，ZIP SHA-256 为
  `94b34f7486f66a915dbd5801b8ed364eb6a491de657269f9fc83e050d94a74b4`。

CI 成功不能替代干净 Windows 10/11 实机的安装、首次启动、升级和卸载烟雾测试。

## 7. 当前限制

尚未验证或实现：

- 将 Nuitka 后端作为 Tauri Sidecar 打入同一安装包并自动启动；
- 临时会话令牌、动态端口握手、Sidecar 崩溃恢复和单写入实例锁；
- 干净 Windows 10/11 上的安装、首次启动、升级、卸载和用户数据保留；
- WebView2 缺失场景的检测与引导；
- Windows Credential Manager；
- 最终安装包在完全没有 Python/Node.js/Rust 的机器上运行；
- 正式发行签名、更新渠道和长期 Artifact 保留。

Tauri bundler 在 Runner 内下载其公开发布的 NSIS 3.11 与
`nsis-tauri-utils` 0.5.3，并执行自身的包验证；本项目没有额外维护这两个传递构建工具的
独立 SHA-256 清单。正式发布前应把该供应链验证提升为可审计的发布门禁。

因此，当前证据证明“M0 空壳安装包可在真实 GitHub Windows Runner 构建”和“独立后端
EXE 可运行”，不代表 M8 Windows 正式部署已经完成。
