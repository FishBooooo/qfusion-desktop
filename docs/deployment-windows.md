# Windows 部署基线

状态：M0 构建骨架，尚未完成真实 Windows 验证
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

后端只监听 localhost，使用精确 CORS，支持优雅退出和单写入实例锁。M0 开发模式中的固定 `127.0.0.1:8000` 仅用于人工通信演示；自动化 E2E 必须使用操作系统分配的动态 Loopback 端口。

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

应用图标的唯一源文件是 `apps/desktop/src-tauri/app-icon.svg`。构建脚本在依赖安装后
使用锁定的 Tauri CLI 将它生成到被忽略的 `src-tauri/icons/`，随后才运行 Rust 检查和
NSIS 构建，避免提交平台生成物或依赖宿主图形工具。

最终 Sidecar 文件名必须包含 Tauri 目标三元组，并由构建脚本复制到 `externalBin` 约定位置。该集成属于 M8；M0 只生成相互独立的后端和空桌面构建骨架。

## 4. 用户数据

默认数据目录：

```text
%LOCALAPPDATA%\QFusion\
```

程序升级保留数据。卸载默认不删除用户数据，只有用户明确选择后才允许删除。安装文件与用户数据库必须分离。

## 5. Windows CI

M0 工作流只允许使用 GitHub 托管的 `windows-latest` Runner，不使用本机或自托管 Runner。工作流应：

1. 仅检出当前 QFusion commit；
2. 通过项目脚本安装锁定的项目本地工具链和依赖；
3. 生成桌面图标和 OpenAPI 客户端并保持锁文件不变；
4. 运行后端 lint、类型检查和测试；
5. 运行前端 lint、类型检查、测试和 Web 构建；
6. 运行 Rust fmt、clippy 和 test；
7. 构建后端可执行文件骨架与 Tauri NSIS 安装包；
8. 上传两个独立构建产物。

CI 成功不能替代干净 Windows 10/11 实机的安装、启动、升级和卸载烟雾测试。

## 6. 当前限制

当前工作区尚未验证：

- Windows Runner 构建；
- Sidecar 打包和动态端口握手；
- WebView2 检测；
- 安装/升级/卸载；
- Windows Credential Manager；
- 无 Python 环境启动。

已在 Linux 验证 Nuitka standalone 后端能够启动并返回健康响应；Tauri CLI 能解析 M0 配置。当前 Linux 主机缺少 WebKitGTK/Pango/GDK/RSVG2 开发库，因此 Linux 不承担原生 Tauri 编译；Rust/Tauri 验证转移到隔离的 Windows Runner。

这些项目在真实命令或 CI 有证据前不得标记通过。
