# Windows 部署基线

状态：M0 构建骨架，尚未完成真实 Windows 验证  
最后更新：2026-07-27

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

后端只监听 localhost，使用精确 CORS，支持优雅退出和单写入实例锁。M0 开发模式中的固定 `127.0.0.1:8000` 仅用于通信演示。

## 3. 构建组成

- Python 3.12+；
- `uv` 管理 Python 依赖；
- Nuitka standalone 优先构建 Sidecar，PyInstaller 仅作备选；
- Node.js + pnpm 构建 React；
- Rust MSVC 工具链构建 Tauri；
- Tauri NSIS bundler 生成安装程序。

项目脚本不会调用全局安装器。`scripts/bootstrap_windows.ps1` 会使用
`scripts/toolchain-versions.json` 中的固定版本和 SHA-256，把 Node.js、uv、Rust/rustup
与 just 安装到仓库内 `.toolchains/`，并将包管理器缓存写入 `.cache/`。脚本以
`-NoProfile` 运行，不修改用户 PowerShell 配置、系统工具链或现有科研环境。

最终 Sidecar 文件名必须包含 Tauri 目标三元组，并由构建脚本复制到 `externalBin` 约定位置。该集成属于 M8；M0 只生成相互独立的后端和空桌面构建骨架。

## 4. 用户数据

默认数据目录：

```text
%LOCALAPPDATA%\QFusion\
```

程序升级保留数据。卸载默认不删除用户数据，只有用户明确选择后才允许删除。安装文件与用户数据库必须分离。

## 5. Windows CI

M0 工作流应在 `windows-latest` 上：

1. 安装 Python、uv、Node/pnpm 和 Rust stable-msvc；
2. 运行后端 lint、类型检查和测试；
3. 运行前端 lint、类型检查、测试和 Web 构建；
4. 运行 Rust fmt、clippy 和 test；
5. 构建后端可执行文件骨架；
6. 构建 Tauri NSIS 安装包；
7. 上传构建产物。

CI 成功不能替代干净 Windows 10/11 实机的安装、启动、升级和卸载烟雾测试。

## 6. 当前限制

当前工作区尚未验证：

- Windows Runner 构建；
- Sidecar 打包和动态端口握手；
- WebView2 检测；
- 安装/升级/卸载；
- Windows Credential Manager；
- 无 Python 环境启动。

已在 Linux 验证 Nuitka standalone 后端能够启动并返回健康响应；Tauri CLI 能解析 M0 配置。当前 Linux 主机缺少 WebKitGTK/Pango/GDK/RSVG2 开发库，因此没有把 Linux 原生 Tauri 编译标记为通过。

这些项目在真实命令或 CI 有证据前不得标记通过。
