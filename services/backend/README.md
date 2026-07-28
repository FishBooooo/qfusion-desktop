# QFusion Backend

M0 FastAPI Sidecar 只提供：

```text
GET /api/v1/health
```

它不初始化数据库、不调用数据供应商、不调用 LLM，也不提供交易路由。

开发运行：

```bash
uv run qfusion-backend
```

默认绑定 `127.0.0.1:8000`。正式 Sidecar 的随机端口、临时令牌和进程监督将在后续里程碑实现。
