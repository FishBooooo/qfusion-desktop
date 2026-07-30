# ADR-0010：离线审计备份与非覆盖恢复

- 状态：Accepted
- 日期：2026-07-30

## 背景

Local Lite 数据跨越 SQLite、DuckDB、Parquet 和 Raw Store。简单复制整个目录可能捕获未提交
WAL、临时 Parquet、变化中的 DuckDB 文件或符号链接，也无法在恢复前验证路径和内容。
直接把归档解压到现有数据目录还可能覆盖有效数据，违反用户数据保护边界。

M1 尚未建立跨 SQLite 与 DuckDB 的全局在线写入屏障，因此不能声称运行中热备份具有跨存储
事务一致性。

## 决策

1. M1 提供 `LocalLiteBackupService`，其输入必须是已停止写入并关闭数据库句柄的离线、静止
   Local Lite 数据根。发现 SQLite WAL/SHM/journal 或 DuckDB WAL 时拒绝备份。
2. 备份只包含：
   - `database/app.sqlite3` 的 SQLite Online Backup 快照；
   - 稳定复制并重验 Schema 的 `database/warehouse.duckdb`；
   - `parquet/` 中除 `.tmp/` 外的普通文件；
   - `raw/` 中的普通文件。
3. 来源目录、数据库、载荷和归档均不得是符号链接，不得经过符号链接；特殊文件和备份期间
   大小/修改时间变化会停止操作。
4. `.qfbak` 使用 ZIP64 容器和版本化 `manifest.json`。清单记录 UTC 创建时间、SQLite
   Alembic head、DuckDB Schema 版本，以及每个规范相对路径的字节数和 SHA-256。路径还必须
   能安全还原到 Windows：拒绝设备保留名、ADS 冒号、控制/非法字符、尾随点或空格，以及
   大小写不敏感文件系统上的冲突。
5. 写归档时流式计算摘要，清单最后写入；完整临时归档在同一目录关闭并同步后原子改名。已存在
   的归档永不覆盖。
6. 恢复不调用通用 `extract`。它先校验 ZIP 路径、重复项、额外项、符号链接及其他非普通
   文件标志、文件数、总字节数、清单契约、逐文件大小和 SHA-256，再流式写入新建 staging
   目录。
7. 恢复后的 SQLite 执行 `integrity_check`，SQLite/DuckDB Schema 必须与清单和当前程序支持
   版本一致。
8. `destination_root` 必须不存在。验证成功后 staging 原子改名为目标；任何失败只清理本次
   唯一 staging，不修改已有数据目录。
9. M1 归档未加密，不能用于不可信介质或包含敏感账户数据的导出。加密、密钥管理、在线写入
   屏障和“切换到已恢复目录”属于后续单独安全功能。

## 后果

优点：

- 备份覆盖四种 Local Lite 存储并可逐文件审计；
- 归档路径穿越、ZIP 符号链接、额外文件、篡改和 Zip Bomb 基础风险被拒绝；
- 恢复永不覆盖现有用户数据，失败可安全重试；
- 不依赖容器、系统服务、宿主包管理器或外部数据库。

限制：

- 调用方必须先让 QFusion 写入器静止；M1 不提供跨进程热备份；
- M1 只恢复到新目录，不自动切换正在使用的数据根；
- 未加密备份必须由用户放在受信任存储中；
- 单个 ZIP 的恢复仍需要足够的本地临时与目标空间。

## 验证要求

Linux 与 Windows Runner 必须实际验证：

- SQLite、DuckDB、Parquet、Raw Store 完整备份并恢复到新目录；
- 恢复后快照、事实、Parquet receipt 和 Raw 对象可通过原 Repository 读取；
- 临时 Parquet 和 Local Lite 根外文件不进入清单；
- 内容篡改、损坏 ZIP、路径穿越、未列出的额外项、ZIP 符号链接与其他特殊文件被拒绝；
- Windows 设备保留名、ADS、非法/模糊字符和大小写路径冲突被拒绝；
- 活动 WAL、来源符号链接、文件/字节上限、未知 Schema 和非法时钟被拒绝；
- 已存在归档与目标目录保持不变；
- 既有 Linux E2E、Windows standalone Sidecar 和 NSIS 构建继续通过。
