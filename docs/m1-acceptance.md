# M1 正式验收

状态：Accepted
验收日期：2026-07-30
代码基线：`main` 提交 `9f5aeac16686b44ce1729f247eac5a2c5bbba90a`

## 1. 验收结论

M1“本地存储与数据契约”的入口、交付物和退出条件均有实际 Linux 与 Windows Runner
证据，允许进入 M2。M1 没有接入真实供应商、真实凭证、交易模型或订单能力。

纳入验收的切片：

| 切片 | 内容 | PR | `main` 提交 |
| --- | --- | --- | --- |
| M1-A | Point-in-Time 领域契约与 Repository Protocol | [#3](https://github.com/FishBooooo/qfusion-desktop/pull/3) | `af47840c35c7534e4c70438a44509aded1c9162b` |
| M1-B | SQLite 快照元数据、Alembic 与打包迁移 | [#5](https://github.com/FishBooooo/qfusion-desktop/pull/5) | `985acd6f7629f6f26679101d6edb1bdd01e3c598` |
| M1-C | DuckDB、Parquet、Raw Store 与单写入队列 | [#7](https://github.com/FishBooooo/qfusion-desktop/pull/7) | `14c40445b896ded5f20e84c1947d2c36227fa46c` |
| M1-D | 确定性 `AnalysisSnapshot` 构建 | [#8](https://github.com/FishBooooo/qfusion-desktop/pull/8) | `f99e713b9ca39fd46d8a72958203d2704b37a732` |
| M1-E | 离线审计备份与安全恢复 | [#9](https://github.com/FishBooooo/qfusion-desktop/pull/9) | `9f5aeac16686b44ce1729f247eac5a2c5bbba90a` |

## 2. 退出条件矩阵

| 退出条件 | 证据 | 结论 |
| --- | --- | --- |
| SQLite 元数据与迁移 | 单一 Alembic head、升级/降级/重复升级、ORM 漂移与打包迁移测试 | 通过 |
| DuckDB + Parquet + Raw Store | 受限 DuckDB Repository、不可变 Parquet 批次、内容寻址原始对象 | 通过 |
| Repository Interface | Domain Protocol 与 SQLite/DuckDB 物理实现分离，业务层不直接使用数据库 SQL | 通过 |
| Mock 日线、分钟线、公告、新闻写入与查询 | `test_analytical_storage.py` 的真实 Repository 往返和 Point-in-Time 查询 | 通过 |
| 完整来源、时间、修订、质量与版本字段 | 冻结 Pydantic 契约、生成 Schema、数据库索引列回读复核 | 通过 |
| 可复现分析快照 | 同一请求和事实状态生成相同内容指纹，未来事实、版本混用和重复事实被拒绝 | 通过 |
| 备份与恢复 | SQLite、DuckDB、Parquet、Raw Store `.qfbak` 往返和恶意归档边界测试 | 通过 |

## 3. 跨平台验证证据

### M1-A / M1-B

- M1-A Linux：[run 30451185229](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30451185229)；Windows：[run 30451185054](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30451185054)。
- M1-B Linux：[run 30482961540](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30482961540)；Windows：[run 30482961515](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30482961515)。

### M1-C

- Linux：[run 30490564432](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30490564432)，61 项 pytest、94.09% 覆盖率、前端与动态 Loopback E2E 通过。
- Windows：[run 30490564436](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30490564436)，Rust、Python、前端、Nuitka standalone 健康烟雾与 NSIS 通过。
- Windows EXE SHA-256：`4e4628a8175c28f85fab01390df8beef83872579e7bd63508a1fc58d54c57267`。
- 后端 Artifact `8741473091`，摘要 `sha256:ac0fa7aab3eb8de9c83207cba45fbba52649b9db14b53942f022065d094e1c66`。
- 桌面 Artifact `8741473569`，摘要 `sha256:e67827ca88396aa779df97cbd34961a8968ce13b9eeb36e284b2922a34ea74f9`。

### M1-D

- Linux：[run 30497685427](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30497685427)，67 项 pytest、94.09% 覆盖率、前端与动态 Loopback E2E 通过。
- Windows：[run 30497685371](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30497685371)，67 项 pytest、94.09% 覆盖率、2 项 Vitest、Nuitka standalone 与 NSIS 通过。
- Windows EXE SHA-256：`b4c8bdbfa66e52305eb28420dbd87cb305a84652d5cbc59664bbc69876805b2f`；迁移 head `0001_m1b_snapshots`；受控 PID 7752、动态端口 63527。
- 后端 Artifact `8744153279`，摘要 `sha256:213d91f31d2d8ee7b1265481457baebb0b742dc9d67a4bddb0658f3dd1dce24d`。
- 桌面 Artifact `8744153588`，摘要 `sha256:2bb66f0c0921b394d28f1592666f52b65455f865924beaf1c160596222b18f46`。

### M1-E

- Linux：[run 30498825886](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30498825886)，79 项 pytest、91.52% 覆盖率、`backup.py` 86% 覆盖率、2 项 Vitest 与动态 Loopback E2E 通过。
- Windows：[run 30498825891](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30498825891)，79 项 pytest、91.52% 覆盖率、2 项 Vitest、Nuitka standalone 与 NSIS 通过。
- Windows EXE SHA-256：`3b2974f6157acf26112d623eb6a38a0cd5402816ad579fa5275530761765cdaa`；迁移 head `0001_m1b_snapshots`；受控 PID 6220、动态端口 65265。
- 后端 Artifact `8744219773`，摘要 `sha256:ddf5fb910b9401be352af8c8f3d5e9f18d77dc8f7c7d1edfeebf793903a4e9c1`。
- 桌面 Artifact `8744220193`，摘要 `sha256:7f14d969fb9d25c4423bee85f8a2f099b84619a0c6961f235eb98a791ef35bee`。

所有 Windows Artifact 都是里程碑回归证据，不是面向用户的 M8 正式发行版。

## 4. 已知限制

1. M1 备份必须在 QFusion 写入器静止且数据库句柄关闭后执行；尚无跨存储在线写入屏障。
2. `.qfbak` 未加密，只能存放在受信任介质；尚未实现活动数据根切换与用户确认流程。
3. 服务内锁可阻止 QFusion 自身并发恢复，但不能防止同一用户的外部进程在目标不存在检查与目录改名之间制造竞态。调用方必须保证数据根由 QFusion 独占；不得把当前实现描述为对恶意本地并发进程的原子 no-replace。
4. 仍保留一条 Starlette `TestClient` 弃用警告，不影响 M1 行为。
5. Windows 证据验证 standalone Sidecar 与 NSIS 构建，不等同于 M8 的干净机器安装、首次启动、升级、卸载和用户数据保留验收。
6. 真实 SEC、FRED、Tiingo、Longbridge 等供应商连接、许可和凭证验证属于 M2。

## 5. 宿主隔离结论

所有验收运行都在 GitHub 托管的 QFusion 专用 Runner 中从锁文件重建依赖。未读取或修改
宿主科研环境、兄弟工作区、外部 pnpm Store、容器 Socket、私有网络或 `franka-setup`。
本机已有活动 `node_modules` 未被迁移、替换或用于验收。

## 6. 下一门禁

M1 已通过。M2 可以开始，但必须继续遵守：供应商统一 Adapter、用户自带凭证、CI 全 Mock、
实际账户权限与供应商总体能力分离、所有事实保留 `available_at` 与修订语义，以及禁止付费
订阅和真实订单的既有边界。
