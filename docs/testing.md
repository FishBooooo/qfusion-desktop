# 测试策略基线

最后更新：2026-07-30

## M0 测试层

- 后端：健康响应、CORS、localhost 绑定和无订单路由。
- Fixture：明确合成标识、带时区时间、永久证券 ID 和四视角集合。
- 前端：Mock 警告、离线降级和后端健康响应验证。
- E2E：浏览器中可见 Mock 页面、`PAPER_TRADE_ONLY` 与后端健康状态。
- Rust/Tauri：在隔离的 GitHub 托管 Windows Runner 中运行 fmt、clippy、test 和空壳构建。
- Windows：构建独立后端 EXE，校验其哈希和健康响应，并生成 NSIS 空壳安装包。

## 统一命令

命令以 `justfile` 为准。Linux 上必须通过项目隔离执行器运行，例如：

```bash
./scripts/run_in_qfusion_env.sh just lint
./scripts/run_in_qfusion_env.sh just typecheck
./scripts/run_in_qfusion_env.sh just test
```

依赖准备只允许运行 `./scripts/bootstrap_linux.sh`，并使用 `uv --locked`、
`pnpm --frozen-lockfile` 和 Cargo `--locked` 保持锁文件不变。测试结果只能在命令实际
运行后报告。Windows 构建和安装烟雾测试不能由 Linux 静态检查替代。

bootstrap 在调用 pnpm 前检查 `node_modules/.modules.yaml`。如果现有模块树关联仓库外
Store，脚本必须输出 `BLOCKED_BY_HOST_ISOLATION` 并停止，不能自动清空或迁移依赖。

## E2E Loopback 边界

自动化 E2E 只能在 QFusion 专用 GitHub 托管 Runner 内运行。测试必须：

- 分别请求操作系统分配后端与前端动态端口，不扫描或复用已有端口；
- 只连接本次测试记录的 `127.0.0.1` 端点；
- 记录子进程句柄、启动时间、工作目录、端口和用途；
- 关闭时使用持有的子进程对象并再次核对身份，不按未验证 PID 终止进程；
- 禁止 `--with-deps`、系统包管理器、Docker/Podman Socket 和非 Loopback 绑定。

Playwright 浏览器下载到仓库内 `.cache/playwright/`。CI 标志由隔离执行器规范化为
布尔值后传入，以保持 `forbidOnly`、重试和不可复用既有服务的测试语义。

## Windows standalone 边界

Windows standalone 健康测试必须由构建工作流直接持有新进程句柄，并满足：

- 只接受 `dist/backend/build-manifest.json` 记录的仓库内相对路径；
- 启动前重新计算 EXE SHA-256；
- 解析 schema v3 清单，逐文件验证打包的 Alembic 迁移和 `tzdata` IANA 资产；
- 必须包含 `America/New_York` 与 `Asia/Hong_Kong`，并以空
  `PYTHONTZPATH` 调用 compiled CLI，使 EXE 清空系统 `TZPATH` 后实际解析两个时区；
- 仅绑定操作系统分配的 Runner 自身动态 Loopback 端口；
- 不扫描端口、不跟随 HTTP 重定向、不访问其他服务；
- 验证精确健康端点与 M0 响应字段；
- 记录 PID、启动时间、工作目录、端口和用途；
- 停止前再次核验所持进程，不按可复用 PID 盲目终止；
- 任一原生命令、哈希、启动、响应或身份检查失败都阻止 Artifact 上传。

该测试证明独立 Nuitka EXE 能运行，不证明 Tauri Sidecar 集成、安装、升级或卸载成功。

## M0 实际证据

验证代码提交：`ed6fffdaa785e018ebf051d073b7cba070cac423`。

Linux：
[CI run 30430746448](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30430746448)。

- Ruff、mypy、OpenAPI/生成客户端一致性检查通过；
- 22 项 pytest 通过，保留 1 条 Starlette `TestClient` 弃用警告；
- ESLint、Prettier、TypeScript、2 项 Vitest 与 Vite 生产构建通过；
- Playwright 1 项通过，后端动态端口 37125、前端动态端口 41371。

Windows：
[Windows M0 Build run 30430746596](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30430746596)。

- Rust fmt、clippy、test 通过；
- Ruff、mypy、22 项 pytest、前端 Lint、类型检查、2 项 Vitest 与生产构建通过；
- Nuitka standalone 编译、EXE SHA-256 校验和动态端口 52277 健康烟雾测试通过；
- Tauri release 与 NSIS 空壳安装包构建通过；
- 两个 Artifact 只在全部前置步骤成功后上传。

最新必需运行没有失败测试。修复过程中的两次 Windows 失败运行正确阻止了后续打包和上传，
证明原生命令非零状态不再被 PowerShell 吞掉。

## M1 实际证据

M1-A 至 M1-E 已分别通过 Linux 与 Windows 托管门禁。最终三个集成切片：

- M1-C：Linux [30490564432](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30490564432)，Windows [30490564436](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30490564436)；
- M1-D：Linux [30497685427](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30497685427)，Windows [30497685371](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30497685371)；
- M1-E：Linux [30498825886](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30498825886)，Windows [30498825891](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30498825891)。

精确 M1-E 头部实际通过 79 项 pytest、91.52% 总覆盖率、2 项 Vitest、Vite、动态
Loopback Playwright、Rust 检查、Nuitka standalone 健康烟雾和 NSIS。Windows 后端
Artifact 摘要为
`sha256:ddf5fb910b9401be352af8c8f3d5e9f18d77dc8f7c7d1edfeebf793903a4e9c1`，
桌面 Artifact 摘要为
`sha256:7f14d969fb9d25c4423bee85f8a2f099b84619a0c6961f235eb98a791ef35bee`。

M1 测试覆盖 Point-in-Time 时间边界、迁移、Repository 往返、单写入、失败回滚、Parquet
与 Raw Store 完整性、可复现快照、备份恢复、恶意归档和 Windows 路径可移植性。完整矩阵、
历史运行和限制见 [M1 正式验收](m1-acceptance.md)。

## M2-A 测试门禁与验收证据

供应商边界单元测试必须覆盖：

- 能力声明集合规范化、重复值、特性布尔值、操作与限流一致性；
- 账户权限状态、UTC 验证时间，以及按“市场 + 操作”匹配的数据质量和技术能力；
- 技术能力与账户权限均拒绝跨市场、跨操作形成的实时或延长时段虚假组合；
- bar 请求的时区、起止时间、决策时间、市场、周期、逐周期历史起点及盘前盘后双重权限；
- 每个受支持 bar 周期恰有一个历史窗口，缺少、重复或多余窗口均被拒绝；
- 清空 Python 系统 `TZPATH` 后，锁定的项目本地 `tzdata` 仍能解析 US/HK 市场时区；
- 内部 UUID 与供应商不透明证券 ID 的映射一致性；
- Synthetic Mock 的来源、许可、质量、版本和事实类型拒绝边界；
- 按证券、事件区间、bar 类型与 `available_at <= decision_time` 的确定性过滤；
- 空响应、未知证券、重复事实，以及输入记录或返回记录的嵌套载荷变更不影响 Adapter
  内部状态和后续确定性结果。

M2-A 不执行真实 HTTP、重试或供应商 SDK 测试。Windows 门禁还必须实际完成 Nuitka
standalone 构建，由清单验证两个 IANA 文件位于 Artifact 内，并由 compiled CLI 在空系统
`TZPATH` 下实际解析两个时区。每个真实 Adapter
进入后，必须另增官方响应
Fixture、字段变化、限流、超时、重试、空响应、时区、休市、修订和账户权限 Contract 测试。

M2-A 精确提交 `a02b18e3375db91d870cef26c310d34a69aede68` 已通过 Linux run
30526872201 和 Windows run 30526872204：Linux 运行 143 项 pytest、2 项 Vitest、
生产构建与 1 项动态 Loopback E2E；Windows 运行 Rust、Python、React 回归、Nuitka
standalone compiled timezone/health smoke 与 NSIS 构建。9 个审查线程均已解决。

## M2-B Instrument Registry 测试门禁

Registry 单元与集成测试必须覆盖：

- 永久 UUID 主键，确认 ticker 不出现在 `instruments` 或 ticker 表主键；
- UTC 规范化、冻结契约、ticker 大写、供应商名称 casefold 和供应商 ID 大小写保留；
- 半开有效期边界、`effective_at <= decision_time` 和
  `available_at <= decision_time`；
- ticker 变化、间隔、复用，以及同一供应商 ID 与同一证券映射的双向重叠拒绝；
- 未知证券、市场错配、映射早于证券注册和持久化 Domain 损坏；
- SQLite 从 base 到单一 head 的升级、幂等、降级、再升级、ORM 列漂移和触发器清单；
- Registry 解析出的双重标识驱动 Synthetic Mock bar 请求，全程不访问网络或凭证；
- 既有快照、分析仓库、备份恢复、Provider、前端、standalone 和 NSIS 回归。

M2-B 不执行真实供应商网络、许可或凭证测试；这些门禁必须在每个真实 Adapter 切片中使用
官方响应 Fixture 单独完成。

## 后续金融测试门禁

涉及行情、财务、新闻、预测或回测时，必须增加时区、交易日、截止时间、盘前盘后、复权、
公司行为、`available_at`、修订、退市、缺失值、成本、滑点和延迟状态测试。

CI 中供应商和 LLM 永远使用 Mock，不允许真实付费调用。
