# 工作区交叉验证

`workspace-baseline.json` 是 M0 必需路径的机器可读清单，`scripts/validate_workspace.py` 是只读校验器。

在当前或另一个工作区根目录运行：

```bash
python3 scripts/validate_workspace.py
```

同时检查本地工具链：

```bash
python3 scripts/validate_workspace.py --with-tools
```

默认校验内容：

- 必需文件存在；
- 必需目录存在；
- 旧的非规范任务书文件名不存在；
- 仓库内 JSON 和 TOML 能被解析。

它有意不比较：

- `.venv`、`node_modules`、`target` 或构建产物；
- API Key、用户配置或本地数据库；
- 因平台与解析器而变化的缓存文件；
- Git 历史。

如需比较两个工作区的内容差异，先分别通过结构校验，再使用版本控制或目录 diff；不要复制 `.env`、密钥或用户数据。
