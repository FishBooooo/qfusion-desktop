# QFusion Desktop 路线图

状态：M2-D0 供应商使用许可门禁已验收；FRED 保持许可阻断，M2 继续进行
最后更新：2026-07-31
最高依据：[PROJECT_TASKBOOK.md](../PROJECT_TASKBOOK.md)

## 里程碑门禁

任何里程碑只有在退出条件有实际测试证据后才能标记完成。未运行的 Windows、供应商或金融
逻辑测试必须明确保留为限制，不能用静态检查替代。

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

### 正式验收

验证代码提交为 `ed6fffdaa785e018ebf051d073b7cba070cac423`，验收文档提交为
`d90d07f74cb9159199b89a9833bbd2350a603ab7`。两者通过
[PR #1](https://github.com/FishBooooo/qfusion-desktop/pull/1) 完成审查，并已 squash 合并到
`main` 提交 `0741e40fe6ad2d527bd4a251672bb5f493f6baff`。

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
旧依赖树。Gate B 活动依赖树迁移仍未授权，也不是 M0 CI 修复的一部分。

PR #1 已满足 M0 的四项技术退出条件且正式进入 `main`，因此 M0 已完成验收。

## M1：本地存储与数据契约

建立 SQLite、DuckDB、Parquet、Repository Interface、迁移、备份恢复和
`AnalysisSnapshot`。所有事实必须包含来源、时间、修订、质量和版本字段。

入口条件：已满足；M0 验收提交已进入 `main`。
退出条件：可写入并查询 Mock 日线、分钟线、公告和新闻，且能生成可复现快照。

### M1-A：Point-in-Time 契约基线

[PR #3](https://github.com/FishBooooo/qfusion-desktop/pull/3) 已审查并 squash 合并到
`main` 提交 `af47840c35c7534e4c70438a44509aded1c9162b`。

已完成：

- [x] 不可变、禁止未知字段的 `DataSourceRecord` 和 `AnalysisSnapshot`；
- [x] 永久 UUID 标识、来源、版本、修订、质量、复权和原始载荷哈希字段；
- [x] UTC 时间规范化和事实时间顺序校验；
- [x] `available_at <= decision_time` Repository 返回守卫；
- [x] 美股、港股市场时区与全部 as-of 时间校验；
- [x] `FactReadRepository` 与 `SnapshotRepository` Protocol；
- [x] 两份由 Pydantic 确定性生成的 JSON Schema 和 CI 漂移检查；
- [x] Linux 与 Windows 托管契约验证。

Linux 证据：
[CI run 30451185229](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30451185229)。

- Ruff、29 个源文件的 mypy、38 项 pytest 和 100% 覆盖率通过；
- 保留 1 条已知 Starlette `TestClient` 弃用警告；
- OpenAPI、生成客户端和两份领域 Schema 重新生成后无差异；
- 2 项 Vitest、Vite 构建和 1 项动态 Loopback Playwright 测试通过。

Windows 证据：
[Windows run 30451185054](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30451185054)。

- Rust fmt/clippy/test、Ruff、mypy、38 项 pytest、前端 Lint/类型检查/测试通过；
- Nuitka EXE 在 Runner 自身动态端口 `52889` 完成健康烟雾测试，受控 PID 为 `7836`；
- EXE SHA-256 为
  `8ccbe838c4c17a0f2f94333eb5c0e1f8d146858decafa32ded57b42c39c71d2f`；
- Tauri NSIS 构建完成；
- 后端 Artifact ID 8724787171，ZIP SHA-256 为
  `c72c9e628d8cec76a49e958235c088a98e1a848f632327aecd276834dd235859`；
- 桌面 Artifact ID 8724787865，ZIP SHA-256 为
  `dba3cf724cbe3d49c722369bc1b7a6e6b47250713643586f7b06b14cdd574ce9`；
- 两个产物计划于 2026-10-27 到期，仅作为 M1-A 回归证据。

M1-A 没有新增依赖、修改锁文件、创建数据库或实现任何供应商、模型、风险、订单或真实金融
调用。

### M1-B：SQLite 快照元数据与迁移

[PR #5](https://github.com/FishBooooo/qfusion-desktop/pull/5) 已审查并 squash 合并到
`main` 提交 `985acd6f7629f6f26679101d6edb1bdd01e3c598`。

已完成：

- [x] SQLite `analysis_snapshots` 与 `analysis_snapshot_facts` 元数据表；
- [x] 可逆、单一 head 的 Alembic 迁移与调用方注入连接；
- [x] 不可变 Snapshot Repository、内容指纹校验、UTC 与外键约束；
- [x] standalone 构建清单 v2、迁移资产清单、逐文件 SHA-256 与 head 校验；
- [x] Windows 原生换行兼容的迁移验证与受控动态 Loopback 健康烟雾测试；
- [x] 依赖锁守卫，确保所有既有锁定版本保持不变。

Linux 证据：
[CI run 30482961540](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30482961540)。

- Ruff、34 个源文件的 mypy、55 项 pytest 和 99% 显示覆盖率通过；
- 2 项 Vitest、Vite 生产构建和动态 Loopback Playwright E2E 通过；
- E2E 后端 PID 2771 使用端口 34339，前端 PID 2778 使用端口 39729；两者均由测试
  持有进程句柄并停止；
- `uv.lock` 无漂移，全部既有包版本保持不变。

Windows 证据：
[Windows run 30482961515](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30482961515)。

- Rust fmt/clippy/test、Ruff、mypy、55 项 pytest、前端 Lint/类型检查和 2 项 Vitest
  全部通过；
- Nuitka EXE SHA-256 为
  `2b100d7c7dbeb8369238e618a6082af5dfabfaa96c208802c3c8cd1a710629e9`；
- 打包迁移 head 为 `0001_m1b_snapshots`，迁移资产验证和动态健康烟雾测试通过；
- 受控后端 PID 7280 使用动态端口 58994，并由测试核验身份后停止；
- 后端 Artifact ID 8738589874，ZIP SHA-256 为
  `948164b72be894bdffce243c3a88d73bb7ef38512f8e9186737d763a733b804e`；
- NSIS Artifact ID 8738590202，ZIP SHA-256 为
  `c855c1046ff693b08771af59d044dc4277717c78c7b3bdc196bc727d29a4c07e`；
- 两个产物计划于 2026-10-27 到期，只作为 M1-B 回归证据。

M1-B 只在 SQLite 保存快照元数据和跨存储事实引用，没有把高容量金融事实载荷写入
SQLite，也没有接入供应商、模型、订单或真实金融数据。

### M1-C：DuckDB、Parquet 与 Raw Store

[PR #7](https://github.com/FishBooooo/qfusion-desktop/pull/7) 已审查并 squash 合并到
`main` 提交 `14c40445b896ded5f20e84c1947d2c36227fa46c`。

- [x] 受限 DuckDB `source_facts`、版本化初始 Schema 和 Point-in-Time 物理查询；
- [x] 单进程异步写入队列和重复 fact ID 事务回滚；
- [x] 带相对路径、行数和 SHA-256 的不可变 Parquet 批次归档；
- [x] SHA-256 内容寻址、幂等且拒绝损坏复用的 Raw Store；
- [x] Mock 日线、分钟线、公告、新闻及篡改/路径边界测试；
- [x] Linux Runner 锁解析、Lint、类型检查、测试、构建与 E2E 全部通过；
- [x] Windows Runner 原生模块打包、测试、standalone 与 NSIS 全部通过。

### M1-D：可复现 AnalysisSnapshot 构建

[PR #8](https://github.com/FishBooooo/qfusion-desktop/pull/8) 已审查并 squash 合并到
`main` 提交 `f99e713b9ca39fd46d8a72958203d2704b37a732`。

- [x] 显式、可验证的 fact type 到快照数据类别政策；
- [x] 目标 UUID、证券范围、市场、周期和 UTC 决策时间请求契约；
- [x] Repository 查询后第二重 Point-in-Time 与范围守卫；
- [x] 确定性 as-of、版本、缺失、过期、质量分数和内容指纹派生；
- [x] 供应商/数据集版本冲突、重复事实、非法时钟和持久化失败处理；
- [x] DuckDB Mock 事实到 SQLite 快照的真实 Repository 集成测试；
- [x] Linux Runner Lint、类型检查、测试、构建与 E2E 全部通过；
- [x] Windows Runner 测试、standalone Sidecar 与 NSIS 全部通过。

### M1-E：离线备份与安全恢复

[PR #9](https://github.com/FishBooooo/qfusion-desktop/pull/9) 已审查并 squash 合并到
`main` 提交 `9f5aeac16686b44ce1729f247eac5a2c5bbba90a`。

- [x] 版本化、规范化且逐文件记录 SHA-256 的 ZIP64 `.qfbak` 清单；
- [x] SQLite 在线一致性副本、稳定 DuckDB 副本及 Parquet/Raw Store 受限归档；
- [x] 路径穿越、符号链接、瞬态 WAL、重复/额外条目、篡改和资源上限拒绝；
- [x] 流式解压到唯一暂存目录、Schema/完整性复验和目标不存在时原子提交；
- [x] SQLite、DuckDB、Parquet 和 Raw Store 的 Repository 级往返恢复测试；
- [x] Linux Runner Lint、类型检查、测试、构建与 E2E 全部通过；
- [x] Windows Runner 测试、standalone Sidecar 与 NSIS 全部通过。

### M1 正式验收

- [x] SQLite 元数据 Schema 与 Alembic 迁移；
- [x] DuckDB/Parquet 分析存储和单写入队列；
- [x] Repository 物理实现与 Mock 日线、分钟线、公告、新闻读写；
- [x] 可复现快照构建服务；
- [x] 离线审计备份与安全恢复；
- [x] Linux 与 Windows 跨平台门禁。

完整退出条件、Runner、Artifact、摘要与限制见 [M1 正式验收](m1-acceptance.md)。M1 已完成，
允许进入 M2。

## M2：首批数据适配器

状态：M2-A、M2-B、M2-C1、M2-C2a 与 M2-D0 已验收；M2 其余退出条件继续进行。

实现 SEC、FRED、一个美股行情源、一个港股行情源和必要的 Mock Adapter。逐一验证许可、
字段、限流、时区、休市和延迟状态。

### M2-A：供应商能力、账户权限与 Synthetic Mock

已验收范围：

- [x] 供应商技术能力与当前账户实际权限使用两份独立、冻结的 Pydantic 契约；
- [x] 能力声明覆盖市场、资产、产品特性、限流、venue、质量与许可；市场数据周期、实时、
  盘前盘后按精确“市场 + 操作”键声明，每个受支持 bar 周期必须且只能声明一个历史起点；
- [x] 账户权限按相同键记录数据质量，并分别声明盘前与盘后权限；
- [x] 技术能力与账户权限均拒绝跨市场或跨操作形成虚假能力组合；
- [x] bar 请求携带双重证券标识，分别声明盘前/盘后，并按市场时区检查对应键历史起点；
- [x] `ProviderAdapter` 与 `MarketDataProvider` Protocol 不暴露供应商 SDK 类型；
- [x] Synthetic Mock 仅返回 `SYNTHETIC_MOCK`/`test-only` 的合成事实；
- [x] Mock 按证券、事实类型、事件区间和 `available_at <= decision_time` 过滤，并对输入
  与返回记录执行深拷贝以隔离嵌套载荷变更；
- [x] 锁定项目本地 `tzdata` 2026.3；Nuitka 显式包含并审计 US/HK 所需 IANA 资产，
  compiled CLI 在空系统 `TZPATH` 下实际解析两个时区；
- [x] ADR-0011、供应商登记、测试和 Windows 部署文档已更新；
- [x] Linux Runner 的 Lint、mypy、pytest、前端回归、构建与动态 E2E；
- [x] Windows Runner 的 Rust、Python、前端、standalone Sidecar 与 NSIS 回归。

M2-A 仅新增锁定的纯数据运行时依赖 `tzdata`，不改变任何既有依赖版本；不访问
供应商网络端点、不读取凭证，也不实现真实供应商或 Instrument Registry。

[PR #11](https://github.com/FishBooooo/qfusion-desktop/pull/11) 的精确测试提交为
`a02b18e3375db91d870cef26c310d34a69aede68`，已 squash 合并到 `main` 提交
`f3ef3edcd0e3da7f9a903610168364bbccb87f81`。

Linux 证据来自
[CI run 30526872201](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30526872201)：

- Ruff、41 个源文件的 mypy、143 项 pytest 和 93.24% 覆盖率通过；
- 2 项 Vitest、TypeScript、生成契约、Vite 生产构建和动态 Loopback E2E 通过；
- E2E 后端 PID 3692 使用动态端口 35475，前端 PID 3702 使用动态端口 42683；
  两者均由测试持有并在身份核验后停止；
- `uv.lock` 无漂移。

Windows 证据来自
[Windows run 30526872204](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30526872204)：

- Rust fmt/clippy/test、Ruff、41 个源文件的 mypy、143 项 pytest、前端检查和
  2 项 Vitest 通过；
- Nuitka EXE SHA-256 为
  `b4e40aaa346d9354b73d1e98c8f1b16abc973534afbb9235eff2bbbe171c0131`；
- 迁移 head、两个 IANA 时区资产、compiled CLI 时区探针和动态健康烟雾测试通过；
- 受控后端 PID 7404 使用动态端口 62574，并在身份核验后停止；
- 后端 Artifact ID 8754266230，ZIP SHA-256 为
  `cfb128eeeb4b1f20e5e11be44a0b84bec09f2525663ba1ad376137786176e7b2`；
- NSIS Artifact ID 8754267184，ZIP SHA-256 为
  `0df92e0c91fa3130cddf0f662412415db7856052a5c35f335d65e3c2b6721abe`；
- 两个 Artifact 计划于 2026-10-28 到期，仅作为 M2-A 回归证据。

### M2-B：Instrument Registry 与有效期映射

已验收范围：

- [x] 内部永久 UUID `instrument_id` 与静态市场/资产类型身份；
- [x] ticker 大写规范化、供应商名称 casefold 和大小写保留的不透明供应商 ID；
- [x] `[valid_from, valid_to)` 有效期、`available_at` 与显式决策时间查询；
- [x] Domain Repository Protocol 与查询后第二重 Point-in-Time 守卫；
- [x] SQLite 三表、复合市场外键、非重叠有效期触发器和可逆迁移；
- [x] ticker 变化、复用、供应商 ID 变化、冲突、损坏和 Synthetic Mock 集成测试；
- [x] ADR-0012、数据模型、架构与测试文档；
- [x] Linux Runner 的 Lint、mypy、pytest、前端回归、构建与动态 E2E；
- [x] Windows Runner 的迁移资产、Rust/Python/React、standalone Sidecar 与 NSIS 回归。

M2-B 不新增依赖、不访问真实供应商、不注入凭证，也不把 ticker 作为永久主键。证券状态
历史、公司行为、ISIN/FIGI 和真实 Adapter 仍不在本切片。

[PR #13](https://github.com/FishBooooo/qfusion-desktop/pull/13) 的精确测试提交为
`6b6e48666c6645f1b843400ebace6ecbd4bf2c18`，已 squash 合并到 `main` 提交
`e927afb583aa1d0d7e5def0992c3066fdce39580`。PR 合并前无评论、评审提交或未解决线程。

Linux 证据来自
[CI run 30532454710](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30532454710)：

- Ruff、42 个源文件的 mypy、164 项 pytest 和 93.05% 覆盖率通过；
- 2 项 Vitest、Vite 生产构建和动态 Loopback Playwright E2E 通过；
- E2E 后端 PID 3657 使用端口 34951，前端 PID 3667 使用端口 37421；两者均由测试
  持有进程句柄并在身份核验后停止；
- `uv lock` 保持全部既有包版本不变，最终 `uv.lock` 无差异。

Windows 证据来自
[Windows run 30532454713](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30532454713)；
首次作业在活动步骤尚标记 `in_progress` 时被平台异常结束且未生成日志，未修改代码的重跑
作业 `90851781616` 随后通过：

- Rust fmt/clippy/test、Ruff、42 个源文件的 mypy、164 项 pytest、前端检查和
  2 项 Vitest 全部通过；
- Nuitka EXE SHA-256 为
  `a4fe52c8842a09db2852a03e074c3dd046e566ddbeb50c40682ed2cb0e857ba6`；
- 打包迁移 head 为 `0002_m2b_instruments`，两个 IANA 时区资产和 compiled CLI
  验证通过；
- 动态健康烟雾 PID 748 使用端口 58488，并在身份核验后停止；
- 后端 Artifact ID 8758224936，大小 148,004,573 bytes，ZIP SHA-256 为
  `cea5f717645d5bf0519ffb00800c49913b4afb13b892590703c23865ab6267f1`；
- NSIS Artifact ID 8758225748，大小 1,248,849 bytes，ZIP SHA-256 为
  `887c5c40cba5ac3383e973cd99b2f9ed7bc553cd8c66758e6aa2554502e4466f`；
- 两个 Artifact 计划于 2026-10-28 到期，仅作为 M2-B 回归证据。

M2-B 已完成验收，允许进入 M2-C。

### M2-C：SEC EDGAR submissions、filings 与 company facts

M2-C1 已验收范围：

- [x] 无凭证、filings-only 的 SEC capability/access 契约；
- [x] 永久 `instrument_id` 与 Registry 解析的精确 10 位 CIK 请求边界；
- [x] submissions `filings.recent` 列式数组的严格、前向兼容解析；
- [x] acceptance 为 `published_at`、首次收到响应为 `available_at`；
- [x] 采集与决策查询分离，Repository/Snapshot 保留最终 Point-in-Time 守卫；
- [x] 固定 SEC 公共 origin、禁代理/重定向、全公网 DNS、限速 5/s、并发 1 和有界重试；
- [x] 合成 Schema Fixture 与 Mock-only 契约、解析、传输和 Adapter 测试；
- [x] `httpx` 以同一锁定版本从 dev 依赖提升为运行时依赖；
- [x] 草稿 PR 只跑 Linux；准备合并时才跑一次 Windows，旧同类运行自动取消，未来
  Windows Artifact 保留 7 天。

M2-C 后续门禁：

- [ ] 在隔离 Runner 中取得、审计并固定 SEC 官方响应 Fixture，不在常规 CI 调用 live
  endpoint；
- [ ] 将原始响应写入 Raw Store，并通过 Repository 增量持久化 filing metadata；
- [ ] 接入观察池 Scheduler、空响应/分页文件与字段漂移处理；
- [ ] 只有在 accession 可证明关联 filing availability 后实现 company facts；
- [x] 完成 M2-C1 Linux/Windows exact-head 门禁与验收记录。

M2-C1 的精确提交、Linux/Windows Runner、Artifact 与隔离证据见
[M2-C1 验收记录](m2c1-acceptance.md)。实现已通过
[PR #15](https://github.com/FishBooooo/qfusion-desktop/pull/15) squash 合并到 `main` 提交
`ab50e28c16c4dd6b8908ee7e37fdd2ab98bc65f0`。

M2-C1 只完成安全采集边界，不代表 SEC 在线接入或整个 M2-C 完成。CIK 只能作为 SEC
供应商不透明标识通过 Instrument Registry 解析。

#### M2-C2a：官方响应手动采集门禁（已验收，未执行 live request）

- [x] Transport 保留有大小上限的精确原始字节，并验证其与解码对象一致；
- [x] 生成不含联系标识的来源 URL、CIK、commit、run ID、时间、字节数和 SHA-256 清单；
- [x] 仅允许 GitHub 手动触发，缺少 `SEC_USER_AGENT` 时在供应商网络前失败；
- [x] 常规 CI/Windows 继续使用 Mock，手动 Artifact 只保留 1 天且不自动提交；
- [x] 精确提交通过 Linux/Windows 跨平台回归、standalone 烟雾测试和 NSIS 构建；
- [ ] 在默认分支配置合规联系标识并手动取得官方响应；
- [ ] 审查响应和许可后固定最小官方 Fixture，并增加字段漂移测试。

采集门禁已通过 [PR #17](https://github.com/FishBooooo/qfusion-desktop/pull/17)
squash 合并到 `main` 提交
`bff5094302152f05cbf45162fe9b066743b08a8f`。精确 Runner、Artifact、摘要与隔离证据见
[M2-C2a 验收记录](m2c2a-acceptance.md)。

本验收只确认门禁实现，不代表已执行真实 SEC 请求，也不完成 Raw Store、Repository、
Scheduler 或 company facts。完整决策见
[ADR-0014](adr/0014-manual-sec-official-capture.md)。

### M2-D0：结构化供应商使用许可门禁

实现范围：

- [x] `ProviderCapability` Schema `2.0.0` 强制包含冻结的 `ProviderUsagePolicy`；
- [x] 个人研究、缓存、持久化、私有/公开展示、商业使用、再分发和模型处理逐项记录；
- [x] 只有 `ALLOWED` 可通过；`PROHIBITED`/`UNVERIFIED` 输出
  `BLOCKED_BY_PROVIDER_LICENSE` 并在副作用前拒绝；
- [x] Synthetic Mock 与 SEC 声明显式用途策略，SEC 持久化校验位于 Transport 之前；
- [x] 拒绝测试证明持久化被禁时不调用 SEC Transport；
- [x] FRED 官方许可冲突和候选替代边界写入 ADR-0015 与供应商登记；
- [x] Linux/Windows exact-head 门禁与正式验收记录。

官方 FRED 条款当前禁止 API 内容的存储、缓存、归档以及软件/机器学习/AI 相关系统用途，
与 QFusion 的本地持久化、离线可用和模型输入路径直接冲突。因此不创建 FRED Adapter、
不配置 API key、不调用端点，并标记 `BLOCKED_BY_PROVIDER_LICENSE`。BLS、BEA、
Treasury 等原始官方宏观来源只作为候选，需分别验证许可、修订和 Point-in-Time 语义。

M2-D0 不新增依赖、不修改数据库、不执行真实供应商请求，也不完成 M2-D 的宏观数据接入。

精确测试提交 `0ee020548c6e8fc25dffea7110ab347d743c9617` 已通过 Linux
[CI run 30555808959](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30555808959)
和 Windows
[run 30556148216](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30556148216)，
并通过 [PR #19](https://github.com/FishBooooo/qfusion-desktop/pull/19) squash 合并到
`main` 提交 `b7959fb33cc92a704504e2887b0b5e5a8807c1e3`。完整测试、Artifact、隔离与
许可保留项见 [M2-D0 验收记录](m2d0-acceptance.md)。

## M3：因子和特征系统

实现版本化的技术、基本面、宏观、事件、期权、板块宽度与主题特征。建立 Point-in-Time
和无泄漏测试。

## M4：三套独立模型 V0

实现华尔街规则模型、量化基线和游资状态机。三者只使用同一快照，独立运行、分别持久化、
均可输出 `NO_TRADE`。

## M5：融合与风险引擎

实现 Fusion Packet 验证、周期对齐、置信度校准、分歧惩罚和独立全局风险否决。

## M6：完整 GUI

完成 Dashboard、股票与板块分析、四视角对比、数据中心、模型中心、设置和 Token 面板。

## M7：回测与模拟交易

完成含成本和滑点的可复现回测、模拟账户、交易日志与绩效归因；验证无已知前视偏差。

## M8：Windows 正式打包

在干净 Windows 10/11 环境完成 Sidecar 集成、NSIS 安装、首次启动、升级、卸载、备份恢复
和烟雾测试。卸载默认保留用户数据。
