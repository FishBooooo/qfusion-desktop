# 测试策略基线

## M0 测试层

- 后端：健康响应、CORS、localhost 绑定和无订单路由。
- Fixture：明确合成标识、带时区时间、永久证券 ID 和四视角集合。
- 前端：Mock 警告、离线降级和后端健康响应验证。
- E2E：浏览器中可见 Mock 页面与 `PAPER_TRADE_ONLY`。
- Rust/Tauri：fmt、clippy、test 和空壳构建。
- Windows：CI Runner 构建独立后端产物和 NSIS 空壳安装包。

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

## 后续金融测试门禁

涉及行情、财务、新闻、预测或回测时，必须增加时区、交易日、截止时间、盘前盘后、复权、公司行为、`available_at`、修订、退市、缺失值、成本、滑点和延迟状态测试。

CI 中供应商和 LLM 永远使用 Mock，不允许真实付费调用。
