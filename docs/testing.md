# 测试策略基线

## M0 测试层

- 后端：健康响应、CORS、localhost 绑定和无订单路由。
- Fixture：明确合成标识、带时区时间、永久证券 ID 和四视角集合。
- 前端：Mock 警告、离线降级和后端健康响应验证。
- E2E：浏览器中可见 Mock 页面、`PAPER_TRADE_ONLY` 与后端健康状态。
- Rust/Tauri：在隔离的 Windows Runner 中运行 fmt、clippy、test 和空壳构建。
- Windows：GitHub 托管 Runner 构建独立后端产物和 NSIS 空壳安装包。

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

## 后续金融测试门禁

涉及行情、财务、新闻、预测或回测时，必须增加时区、交易日、截止时间、盘前盘后、复权、公司行为、`available_at`、修订、退市、缺失值、成本、滑点和延迟状态测试。

CI 中供应商和 LLM 永远使用 Mock，不允许真实付费调用。
