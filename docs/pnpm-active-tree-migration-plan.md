# pnpm 活动依赖树迁移与回滚方案

状态：Gate A 候选验证通过；Gate B 活动迁移未授权  
日期：2026-07-27  
适用决策：[ADR-0006：项目本地工具链与干净执行环境](adr/0006-project-local-toolchains.md)

## 1. 目的

当前活动 `node_modules` 的 pnpm 元数据仍记录仓库外 Store。为满足 QFusion 的宿主环境
隔离要求，最终活动依赖树应只连接到仓库内 `.cache/pnpm/store`。

本文定义迁移门禁、切换步骤和回滚边界。Gate A 已获批准并只在项目最终 Store 与临时
候选工作区中完成；活动树切换和旧树清理仍分别需要新的明确批准。

## 2. 已验证基线

2026-07-27 的只读检查与隔离验证记录如下：

| 项目 | 已验证值 |
| --- | --- |
| Node.js | `22.23.1` |
| pnpm | `10.13.1` |
| 根 `pnpm-lock.yaml` SHA-256 | `5caf5ad00b6f4bd7d2a9d9f093e38c000592ec35601441c8720a7ce04ed78f0e` |
| 活动 `.modules.yaml` SHA-256 | `a4fe95857e2dfe5cfbc88904751a0dc1ea7e285b57c7b61e2b95b03de6cb0006` |
| 活动虚拟 Store 锁 SHA-256 | 与根锁一致 |
| 锁定包数量 | 416 |
| 已比较直接依赖 | 28，版本差异 0 |
| 生成客户端 SHA-256 | `216beb8687f10a2800a4fd03fdca95d5400aeece5a92976017ef78a9d2276ddb` |
| 隔离验证 | OpenAPI 生成、Lint、类型检查、2 项 Vitest、Vite 构建通过 |
| 外部 Store 复用 | 0 |
| 活动树在验证期间变化 | 否 |

活动工作区由以下三个 pnpm 管理目录组成，必须作为一个事务处理：

1. `node_modules`
2. `apps/desktop/node_modules`
3. `packages/generated-client/node_modules`

当前三者占用约 416 MiB。现有隔离验证树位于
`.tmp/pnpm-isolation-validation`，验证 Store 位于 `.cache/pnpm-validation`。它们只能作为
兼容性证据，不能直接移动为活动树，因为其工作区路径和 Store 路径不是最终路径。

已知限制：隔离验证使用 `--ignore-scripts`，因此记录有
`esbuild@0.25.12` 待执行构建脚本；现有 Vite 生产构建仍已通过。任何生命周期脚本都不在
本方案的默认授权范围内。

pnpm 10 在 `.modules.yaml` 中记录版本化的有效 Store 路径，例如配置目录
`.cache/pnpm/store` 下的 `v10`。`scripts/check_pnpm_isolation.py` 已修正为只接受该精确
项目内路径，并拒绝未版本化路径、其他版本、父路径穿越、仓库外路径、重复 Store 字段及
带符号链接的元数据或 Store 路径。14 项边界单元测试和真实 pnpm 10 验证元数据检查通过；
当前外部 Store 活动树仍会按预期被阻断。该修复本身只消除了检查器实现阻断；Gate A
随后才经单独批准执行，且没有授权活动迁移。

Gate A 随后已在 `.tmp/pnpm-final-store-gate-a` 完成：

- 使用最终项目 Store `.cache/pnpm/store/v10` 下载锁定的 416 个包，外部 Store 复用为 0；
- 安装使用 `--frozen-lockfile --ignore-scripts`，两次离线幂等检查通过；
- 28 个直接依赖无差异，1,311 个候选符号链接全部留在候选工作区；
- OpenAPI 与生成客户端哈希一致；
- ESLint、Prettier、两套 TypeScript 检查、2 项 Vitest 和 Vite 生产构建通过；
- 活动 `node_modules`、清单和锁文件均未变化。

机器可读证据保存在候选工作区的 `VALIDATION_SCOPE.json` 和
`VALIDATION_RESULT.json`。Gate A 通过不代表 Gate B 已授权。

## 3. 不可破坏的约束

整个迁移事务必须同时满足：

1. 只读写当前 QFusion 仓库。
2. 不搜索、读取、检查或修改 `franka-setup`、其进程、任务、数据、日志、网络或配置。
   无法确认其状态时，继续按其正在运行处理。
3. 不读取或修改当前活动树所记录的仓库外 pnpm Store。
4. 不访问 localhost、局域网、Docker/Podman Socket 或宿主服务。
5. 只使用 `scripts/run_in_qfusion_env.sh` 提供的干净、非登录环境。
6. 不修改宿主 Node.js、pnpm、Shell 配置、用户配置、全局缓存或系统依赖。
7. 不修改任何 `package.json`、`pnpm-workspace.yaml` 或 `pnpm-lock.yaml`。
8. 不升级、降级、替换或重锁任何既有依赖。
9. 旧活动依赖树只能在仓库内做同文件系统改名并完整保留；不得覆盖或删除。
10. 默认禁止执行依赖生命周期脚本。
11. 任一门禁失败都停止；不能在项目内安全完成时输出
    `BLOCKED_BY_HOST_ISOLATION`。

## 4. 独立批准门禁

本文的完成不代表后续步骤已获批准。

### Gate A：最终 Store 候选验证

已于 2026-07-27 获得单独批准并通过。锁定依赖已写入 `.cache/pnpm/store`，验证仅在新的
`.tmp/` 工作副本中进行，活动 `node_modules` 未改变。

### Gate B：活动树切换

只有 Gate A 报告全部通过、基线无变化并再次获得明确批准后，才可短暂停用 QFusion
自身的前端开发任务并执行活动树切换。不得通过宿主进程扫描确认状态，也不得接触或中断
任何 Franka 相关任务。

### Gate C：旧树和失败树清理

即使切换成功，也不得自动删除旧树、候选树或失败树。清理需要再次明确批准，并且只能
针对迁移日志中记录的仓库内精确路径。

## 5. 事务目录和日志

后续实现应为每次尝试创建唯一事务目录：

```text
.tmp/pnpm-active-tree-migration/<transaction-id>/
├── journal.json
├── baseline/
├── backup/
│   ├── node_modules/
│   ├── apps/desktop/node_modules/
│   └── packages/generated-client/node_modules/
├── failed-new/
└── reports/
```

事务目录不得包含指向仓库外部的符号链接。`journal.json` 至少记录：

- 事务 ID、开始时间和当前阶段；
- 工具版本；
- 清单、工作区配置和锁文件哈希；
- 三个活动目录的精确路径、inode、大小和修改时间；
- `.modules.yaml` 和虚拟 Store 锁的哈希；
- 最终 Store 和候选工作区路径；
- 每次改名的完成顺序；
- 测试结果；
- 最终状态：`VALIDATED`、`COMMITTED`、`ROLLED_BACK` 或 `BLOCKED`。

事务日志不得记录用户环境变量、外部 Store 内容或任何科研环境信息。

## 6. Gate A：非活动候选预检

Gate A 获批后按以下顺序执行：

1. 重新阅读强制文档和 ADR-0006。
2. 只读计算清单、锁文件、生成客户端和活动 pnpm 元数据哈希。
3. 使用明确文件白名单创建新的 `.tmp/` 工作副本；不复制任何
   `node_modules`、缓存、工具链、构建产物或符号链接。
4. 确认 Node.js 和 pnpm 版本与基线一致。
5. 将 pnpm Store 固定为最终路径 `.cache/pnpm/store`，缓存和状态仍位于仓库内。
6. 使用 `--frozen-lockfile --ignore-scripts` 从锁文件构建候选树。
7. 再次使用 `--offline --frozen-lockfile --ignore-scripts` 验证 Store 完整且安装幂等。
8. 检查候选树：
   - 锁哈希与根锁完全一致；
   - 28 个直接依赖版本差异为 0；
   - `.modules.yaml` 只记录 `.cache/pnpm/store` 内预期的 pnpm 版本子目录；
   - 所有符号链接目标都位于候选工作区或当前仓库；
   - 未执行生命周期脚本；
   - 未修改活动树、清单或锁文件。
9. 在候选树中运行 OpenAPI 客户端生成并比较产物哈希。
10. 在候选树中运行前端 Lint、类型检查、Vitest 和 Vite 生产构建。

Gate A 必须生成独立报告。若任何命令尝试修改锁文件、访问外部 Store、执行未批准脚本或
产生依赖版本差异，立即停止并报告，不得进入 Gate B。

## 7. Gate B 前置条件

活动切换前必须全部满足：

- Gate A 报告为 `passed`；
- 用户已明确批准 Gate B；
- 用户确认 QFusion 自身的开发/构建任务已停止；
- 不使用全局进程扫描、端口探测或 localhost 请求进行确认；
- 三个活动目录与事务备份目录位于同一文件系统；
- 事务目录不存在路径冲突；
- 当前清单、锁、生成客户端和活动元数据哈希仍等于获批基线；
- 可用空间至少为“活动树 + 候选树 + 最终 Store + 25% 余量”，且不低于 2 GiB；
- `.cache/pnpm/store` 已通过离线完整性验证；
- 没有需要执行的未批准生命周期脚本；
- pnpm 隔离检查器已正确识别并限制版本化 Store 子目录，且单元测试通过；
- 专用切换脚本已经过静态审查，并默认以 dry-run 模式运行。

若 QFusion 是否仍在使用活动树无法安全确认，不执行切换。`franka-setup` 的运行状态不属于
本项目的确认范围，也不得检查。

## 8. Gate B：活动树切换

切换必须由一个后续单独审查的项目内脚本完成，不允许临时拼接破坏性 Shell 命令。

1. 创建事务日志并写入 `PREPARED`。
2. 按日志顺序将三个旧活动目录分别改名到 `backup/` 中的镜像路径。每次改名必须：
   - 不跟随符号链接；
   - 不复制或读取依赖文件内容；
   - 使用同文件系统改名；
   - 成功后立即写入事务日志。
3. 如果任一旧目录改名失败，立即按相反顺序恢复已改名目录，不运行 pnpm。
4. 旧目录全部保留后，才允许在真实工作区运行：

   ```text
   scripts/run_in_qfusion_env.sh pnpm install --offline --frozen-lockfile --ignore-scripts
   ```

5. 不直接复用或移动 Gate A 的候选 `node_modules`；真实工作区必须从已验证的最终 Store
   离线重建，以避免候选工作区路径残留。
6. 安装后立即运行项目现有的 pnpm 隔离检查，并验证：
   - 有效 Store 位于 `.cache/pnpm/store` 内预期的 pnpm 版本子目录；
   - 不存在指向仓库外部的符号链接；
   - 清单与锁哈希未改变；
   - 直接依赖版本与 Gate A 完全一致。
7. 通过结构检查后运行：

   ```text
   scripts/run_in_qfusion_env.sh pnpm lint
   scripts/run_in_qfusion_env.sh pnpm typecheck
   scripts/run_in_qfusion_env.sh pnpm test
   scripts/run_in_qfusion_env.sh pnpm build
   ```

8. 重复一次离线、冻结锁、忽略脚本的安装，确认幂等且不改锁。
9. 全部门禁通过后把事务标记为 `COMMITTED`，但继续保留 `backup/`。

本切换不运行 Playwright E2E，因为当前没有 localhost 授权；也不运行与 pnpm 活动树无关的
Rust 原生测试。

## 9. 自动回滚条件

出现以下任一情况必须立即回滚：

- 离线安装失败或尝试联网；
- pnpm 请求清空未记录的目录；
- 清单、工作区配置或锁哈希变化；
- 依赖版本与 Gate A 不一致；
- Store 路径或任一符号链接越出当前仓库；
- 隔离检查、Lint、类型检查、Vitest 或 Vite 构建失败；
- 出现需要宿主依赖、全局工具链或生命周期脚本才能解决的问题；
- 事务日志无法可靠写入。

## 10. 回滚流程

回滚不删除任何依赖树：

1. 停止后续 pnpm 命令并将事务标记为 `ROLLBACK_STARTED`。
2. 将新生成的三个 `node_modules` 目录按镜像结构改名到 `failed-new/`；不存在的目录按
   “未创建”记录。
3. 按旧树改名的相反顺序，把 `backup/` 中三个目录恢复到原始精确路径。
4. 使用不跟随链接的元数据检查确认：
   - 三个原路径均已恢复；
   - `.modules.yaml` 和虚拟 Store 锁哈希等于基线；
   - 被保留文件的 inode、大小和修改时间未变；
   - 清单、工作区配置和根锁未变。
5. 将事务标记为 `ROLLED_BACK` 并停止。

回滚后不运行会解析旧依赖链接的测试，因为这可能读取旧树记录的仓库外 Store。回滚验证
仅检查仓库内路径和元数据。

## 11. 冲突与阻断报告

若依赖无法在仓库内安装、最终 Store 不完整、候选版本漂移、需要宿主组件或旧依赖必须被
修改，输出：

```text
BLOCKED_BY_HOST_ISOLATION
```

报告必须包含：

- 冲突或缺失的依赖及版本约束；
- 为什么无法在项目内完成；
- 是否影响候选验证或活动切换；
- 可采用的项目内隔离替代方案；
- 对 M0 验收的影响。

不得请求修改宿主环境或放宽到系统级权限。

## 12. 成功标准

只有以下条件全部满足，活动迁移才可报告成功：

1. 活动 `.modules.yaml` 只指向 `.cache/pnpm/store` 内预期的 pnpm 版本子目录。
2. 所有依赖、缓存、状态和构建产物均位于当前仓库。
3. 清单、工作区配置、锁文件及直接依赖版本均未变化。
4. 不存在指向仓库外部的依赖链接。
5. Lint、类型检查、Vitest 和 Vite 构建实际通过。
6. 离线冻结锁安装幂等通过。
7. 未访问或影响 `franka-setup`、宿主依赖、外部 Store、localhost 或本地服务。
8. 旧活动树仍完整保留，可在同一事务中恢复。

## 13. Gate A 完成后仍明确不执行

- 不在活动工作区运行 `pnpm install`；
- 不移动或修改任何活动 `node_modules`；
- 不修改任何依赖清单或锁文件；
- 不实现或运行切换脚本；
- 不删除现有验证树、缓存或旧依赖；
- 不检查任何 QFusion 之外的工作空间或进程。
