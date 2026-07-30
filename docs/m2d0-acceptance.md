# M2-D0 供应商使用许可门禁验收

状态：Accepted
日期：2026-07-31
实现 PR：[PR #19](https://github.com/FishBooooo/qfusion-desktop/pull/19)

## 1. 验收范围

M2-D0 验收供应商数据用途许可的机器可执行边界。它不代表 FRED/ALFRED、SEC 在线采集、
宏观数据源或整个 M2 已完成。

已验收：

- `ProviderCapability` Schema `2.0.0` 强制包含冻结、禁止未知字段的
  `ProviderUsagePolicy`；旧 Schema 或缺失策略均被拒绝；
- 个人研究、项目缓存、长期持久化、私有展示、公开展示、商业使用、再分发和模型处理分别
  使用 `ALLOWED`、`PROHIBITED` 或 `UNVERIFIED`；
- 只有明确 `ALLOWED` 的用途可以通过 `validate_provider_usage`，其他状态统一以
  `BLOCKED_BY_PROVIDER_LICENSE` fail closed；
- 条款 URL、复核日期、署名要求和必需提示进入结构化契约，必需提示去重并确定性排序；
- Synthetic Mock 保留“合成数据”提示，商业使用与再分发禁止；
- SEC 当前只允许已复核的个人研究、本地缓存、持久化和私有展示；公开展示、商业使用、
  再分发与模型处理保持 `UNVERIFIED`；
- SEC filing 持久化用途在 Transport 调用前校验，拒绝测试证明请求计数保持为零；
- FRED/ALFRED 因官方条款与本地持久化、离线缓存及模型处理路径冲突而保持
  `BLOCKED_BY_PROVIDER_LICENSE`；没有创建 Adapter、配置 key、调用端点或保存响应；
- ADR-0015、供应商登记、架构、安全、测试和路线图已同步。

## 2. 提交与审查

精确测试提交为 `0ee020548c6e8fc25dffea7110ab347d743c9617`。合并前 PR 相对
`main` 落后 0 个提交、可合并，且没有评论、评审提交或未解决线程。

PR #19 已使用预期 head SHA 锁定并 squash 合并到 `main` 提交
`b7959fb33cc92a704504e2887b0b5e5a8807c1e3`。

本切片没有新增、升级、降级或重锁依赖；没有修改数据库 Schema，也没有执行真实供应商
请求。

## 3. Linux 证据

[CI run 30555808959](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30555808959)
的作业 `90915834060` 在精确测试提交上通过：

- 锁更新守卫保持所有既有 Python 包版本不变，最终 `uv.lock` 无漂移；
- Workspace baseline、OpenAPI、生成客户端和 Domain Schema 一致性检查通过；
- Ruff 与 50 个 Python 源文件的 mypy 通过；
- 199 项 pytest 全部通过，总覆盖率 92.87%（显示为 93%），保留 1 条已知
  Starlette 弃用警告；
- 1 个测试文件中的 2 项 Vitest、TypeScript 与 Vite 生产构建通过；
- 1 项动态 Loopback Playwright E2E 通过；
- E2E 后端 PID/端口为 3652/37425，前端为 3663/40311，均由测试持有进程句柄并在
  身份核验后停止；
- 运行没有调用任何真实供应商，也没有访问本机或其他工作区。

## 4. Windows 证据

[Windows run 30556148216](https://github.com/FishBooooo/qfusion-desktop/actions/runs/30556148216)
的作业 `90916988183` 在同一精确测试提交上通过：

- 项目本地锁定工具链、Python 依赖和 Node 依赖同步通过；
- Rust fmt/clippy/test、Ruff、50 个源文件的 mypy、199 项 pytest、92.87% 覆盖率、
  前端 Lint/类型检查、2 项 Vitest 和生产构建全部通过；
- Nuitka standalone EXE SHA-256 为
  `668ac8a25465cd633d3f19dc1dae4ed5acca35ce4e81988695579328965d8eda`；
- 打包迁移 head 为 `0002_m2b_instruments`，两个项目本地 IANA 时区资产通过验证；
- 独立后端由受控 PID 8140 在动态端口 50797 完成健康烟雾测试；
- Tauri release 生成 `QFusion Desktop_0.1.0_x64-setup.exe`；
- 后端 Artifact ID 8766509693，大小 148,004,493 bytes，ZIP SHA-256 为
  `c49efcd135b2a5d3240072c236c3abb4f179db58a0a68b6547308eebd96f9cc2`；
- NSIS Artifact ID 8766510716，大小 1,249,229 bytes，ZIP SHA-256 为
  `eb438731c67c28a7af1bc143ee902a0513d55fc85d18d00de27bd8ab75218361`；
- 两个 Artifact 计划于 2026-08-06 到期，只作为回归证据，不是正式发行版；
- Windows 回归没有执行真实供应商请求或读取任何供应商凭证。

## 5. 隔离证明

验证只运行在 GitHub 托管的 QFusion 专用标准 Runner。CI 没有访问本机、兄弟工作区、
`franka-setup`、局域网、容器 Socket、科研环境或外部账户。Linux E2E 与 Windows
standalone 只连接各自 Runner 内由当前测试直接启动并持有的动态 Loopback 进程。

公开仓库仅用于运行标准 GitHub 托管 CI；没有注册或使用本机自托管 Runner。

## 6. 许可结论与保留项

官方依据：

- [FRED Services Terms of Use](https://fred.stlouisfed.org/legal/terms/)
- [FRED API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html)
- [SEC Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)

以下项目仍未完成：

- FRED/ALFRED 保持许可阻断，不得通过放宽断言、绕过缓存边界或只标记
  `license_scope` 来启用；
- BLS、BEA、Treasury 等宏观候选来源仍需分别复核许可、修订和 Point-in-Time 语义；
- SEC 公开展示、商业使用、再分发与模型处理仍为 `UNVERIFIED`；
- 尚未配置 SEC 联系标识、执行 live request、取得官方响应 Fixture，或完成 Raw Store、
  Repository、Scheduler 与 company facts；
- `terms_checked_at` 当前用于审计，尚未实现自动到期或条款变更检测；
- `terms_url` 是不会由运行时自动访问的审计元数据；当前校验 HTTPS、主机和无用户信息，
  不执行 DNS 解析。

因此 M2-D0 已完成跨平台验收，但 M2 的真实宏观、行情、港股和增量同步退出条件仍未满足。
