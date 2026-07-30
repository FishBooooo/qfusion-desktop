# Windows 部署基线

状态：M2-B Instrument Registry 迁移资产与 standalone 已通过 Windows Runner 验证
最后更新：2026-07-30

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
调用 Dependency Walker。构建保留 Alembic 运行所需的 SQLAlchemy 服务端方言入口，只
排除在当前 Runner 上导致编译内存问题且 QFusion 不使用的
`sqlalchemy.dialects.oracle.dictionary` 模块；SQLite `pysqlite` 驱动必须显式包含。

Windows 通常不提供 Python 可直接读取的系统 IANA 数据库。后端因此通过
`pyproject.toml` 与 `uv.lock` 锁定项目本地 `tzdata` 2026.3；Nuitka 命令显式包含
`tzdata` 包及数据，不读取或修改宿主机时区配置。构建后必须找到并校验
`tzdata/zoneinfo/America/New_York` 与 `tzdata/zoneinfo/Asia/Hong_Kong`。

构建成功后生成 `dist/backend/build-manifest.json` schema v3，记录相对可执行文件路径、
SHA-256、迁移目录、唯一 Alembic head、完整文件清单、逐文件 SHA-256，以及两个必需
IANA 时区资产的相对路径和摘要。迁移资产复制到
standalone 可执行文件旁的 `qfusion_migrations/`，运行时不依赖源码目录。M1-B 的后端
与桌面安装包仍是两个独立 Artifact；将 Sidecar 复制为带 Tauri 目标三元组的
`externalBin` 并由桌面端启动属于 M8。

## 4. 独立后端烟雾测试

`scripts/smoke_backend_standalone.py` 只验证本次构建生成的 Windows 可执行文件：

1. 解析 schema v3 构建清单，拒绝绝对路径、父路径穿越和越出
   `dist/backend` 的路径；
2. 重新计算 standalone EXE SHA-256 并与清单比较；
3. 验证迁移目录不是符号链接、位于可执行文件旁且文件清单完全一致；
4. 逐个验证迁移资产 SHA-256，并要求清单只声明一个 Alembic head；
5. 验证 `tzdata` 包名、两个必需 zoneinfo 相对路径及 SHA-256，拒绝缺失、重复、
   意外路径、符号链接和越界文件；
6. 执行 compiled CLI 的 `--verify-migration-assets`，接受 Windows CRLF 或 POSIX LF，
   但拒绝额外输出行；
7. 以空 `PYTHONTZPATH` 执行 compiled CLI 的 `--verify-timezone-data`，由独立 EXE
   清空系统 `TZPATH` 后实际构造 US/HK 两个 `ZoneInfo`，并拒绝额外输出行；
8. 由操作系统分配动态 `127.0.0.1` 端口；
9. 记录 PID、启动时间、工作目录、端口和用途；
10. 禁止 HTTP 重定向，只请求精确 `/api/v1/health` 并验证健康响应；
11. 停止前再次核验所持进程对象和身份。

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

M1-B 的最终验证提交为 `03b1ea96e219dda90c33b02b56b8761352dc3e27`，来自
[Windows run 30482961515](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30482961515)：

- Rust fmt/clippy/test、Ruff、mypy、55 项 pytest 和 2 项 Vitest 通过；
- Nuitka standalone EXE SHA-256 为
  `2b100d7c7dbeb8369238e618a6082af5dfabfaa96c208802c3c8cd1a710629e9`；
- 打包迁移 head 为 `0001_m1b_snapshots`，资产清单、逐文件哈希、compiled CLI
  验证和动态健康烟雾测试通过；
- 后端 PID 7280 使用动态端口 58994，测试完成后核验身份并停止；
- 后端 Artifact ID 8738589874，大小 132,528,418 bytes，ZIP SHA-256 为
  `948164b72be894bdffce243c3a88d73bb7ef38512f8e9186737d763a733b804e`；
- NSIS Artifact ID 8738590202，大小 1,248,650 bytes，ZIP SHA-256 为
  `c855c1046ff693b08771af59d044dc4277717c78c7b3bdc196bc727d29a4c07e`；
- 两个产物计划于 2026-10-27 到期，仅作为回归证据。

M2-A 精确提交 `a02b18e3375db91d870cef26c310d34a69aede68` 的
[Windows run 30526872204](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30526872204)
已通过：

- Rust、Python、React 全部回归门禁通过，pytest 为 143 项；
- standalone EXE SHA-256 为
  `b4e40aaa346d9354b73d1e98c8f1b16abc973534afbb9235eff2bbbe171c0131`；
- 清单验证两个 IANA 资产，compiled CLI 在空系统 `TZPATH` 下实际解析 US/HK 时区；
- 动态健康烟雾 PID 7404 使用端口 62574，并在身份核验后停止；
- 后端 Artifact ID 8754266230，ZIP SHA-256 为
  `cfb128eeeb4b1f20e5e11be44a0b84bec09f2525663ba1ad376137786176e7b2`；
- NSIS Artifact ID 8754267184，ZIP SHA-256 为
  `0df92e0c91fa3130cddf0f662412415db7856052a5c35f335d65e3c2b6721abe`；
- 两个 Artifact 计划于 2026-10-28 到期，只作为 M2-A 回归证据。


M2-B 精确提交 `6b6e48666c6645f1b843400ebace6ecbd4bf2c18` 的
[Windows run 30532454713](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30532454713)
在代码不变的重跑作业 `90851781616` 中通过：

- Rust、Python、React 全部回归门禁通过，pytest 为 164 项且总覆盖率 93.05%；
- standalone EXE SHA-256 为
  `a4fe52c8842a09db2852a03e074c3dd046e566ddbeb50c40682ed2cb0e857ba6`；
- 清单验证唯一迁移 head `0002_m2b_instruments`、完整迁移资产和两个 IANA 时区资产；
- compiled CLI 迁移/时区探针及动态健康烟雾通过，受控 PID 748 使用端口 58488 并在
  身份核验后停止；
- Tauri 生成 `QFusion Desktop_0.1.0_x64-setup.exe`；
- 后端 Artifact ID 8758224936，大小 148,004,573 bytes，ZIP SHA-256 为
  `cea5f717645d5bf0519ffb00800c49913b4afb13b892590703c23865ab6267f1`；
- NSIS Artifact ID 8758225748，大小 1,248,849 bytes，ZIP SHA-256 为
  `887c5c40cba5ac3383e973cd99b2f9ed7bc553cd8c66758e6aa2554502e4466f`；
- 两个 Artifact 计划于 2026-10-28 到期，仅作为 M2-B 回归证据。

首次作业在 standalone 步骤尚报告 `in_progress` 时被平台异常结束，且 GitHub 未生成该
作业日志；同一 exact-head 的未修改重跑完整通过，因此未对代码或隔离策略做猜测性调整。

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
