# ADR-0013：SEC EDGAR Adapter 与公共网络出站边界

- 状态：Accepted
- 日期：2026-07-30

## 背景

M2-C 需要读取 SEC EDGAR 的公开 submissions 数据。SEC 官方说明 `data.sec.gov` API
不需要认证或 API Key，CI 仍不得调用真实供应商端点。SEC 要求声明 User-Agent，并将当前
最大访问速率限制为每秒 10 个请求。

宿主保护规则同时禁止继承代理、访问本地和私有网络，以及把 ticker 当作永久证券标识。
此外，SEC 没有提供“文件首次可从 sec.gov 下载”的精确时间戳；直接把 EDGAR acceptance
time 当作 `available_at` 会给历史决策引入不可证明的提前可用假设。

## 决策

1. SEC Adapter 只接收 Instrument Registry 在显式 Point-in-Time 边界下解析出的
   `instrument_id` 与 10 位补零 CIK。CIK 是 `sec-edgar` 的不透明供应商标识，ticker
   不参与请求路径或事实主键。
2. M2-C 首个可运行切片实现 submissions recent filing metadata。company facts 只有在能用
   accession number 关联到 filing availability 后才能进入 Domain；不能用只有日期的
   `filed` 字段伪造精确可用时间。
3. 生产传输只允许固定 HTTPS origin `https://data.sec.gov:443` 和由已验证 CIK生成的
   submissions 路径。禁止调用方传入 URL，禁止重定向，禁止继承宿主代理，并在每次请求前
   解析 DNS；空结果或任一非公网地址都会拒绝。
4. HTTP 客户端使用显式 connect/read/write/pool timeout、`trust_env=False` 和
   `follow_redirects=False`。只重试传输错误、429 和选定 5xx；其他 4xx、重定向、无效
   JSON 或契约错误立即失败。重试次数和等待均有上限。
5. QFusion 内部限速为每秒最多 5 请求、并发 1，低于 SEC 公布上限。每个真实请求必须携带
   由类型化配置提供的组织/产品名和联系邮箱；仓库不保存私人凭证，CI 只用测试值。
6. 网络获取与纯解析分离。CI 使用仓库 Fixture 和注入式 Mock Transport，不访问 SEC。
   外层新增字段可以保留兼容；filings recent 的必需列必须存在，所有列式数组长度必须
   一致，否则 fail closed，不能静默截断。
7. `published_at` 记录 SEC acceptance datetime；`available_at` 记录 QFusion 第一次
   实际收到该 payload 的 `received_at`。这会牺牲未经历史采集的数据回测覆盖率，但不会
   假装内容在接收前已经可用。
8. Adapter 是采集边界，返回带首次观察时间的事实供 Repository 持久化，不接收模型决策
   时间，也不直接向模型供数。后续 `FactReadRepository` 和 Snapshot Builder 必须执行
   `available_at <= decision_time`；这样新采集事实可以入库，同时历史决策仍不能看到
   当时尚未观察到的数据。
9. 每条 filing metadata 生成稳定 accession 身份、规范 raw-row SHA-256、来源/许可/版本和
   修订元数据。
10. `httpx` 从开发依赖提升为同版本运行时依赖；锁更新只允许改变根包依赖归属，不允许
   升级、降级或增加其他包。
11. Windows 构建 Artifact 的未来保留期设为 7 天，减少公开仓库仍可能产生的 Actions
    存储占用；不删除既有 Artifact。
12. 同一 PR 的 Linux/Windows workflow 使用 concurrency 取消过时运行；完整 Windows
    打包在草稿阶段跳过，只在 ready-for-review 或手动触发时执行，避免每个小修复都重复
    编译和上传。

## 后果

该边界不支持任意 URL、重定向或代理环境，减少 SSRF、私网访问和科研网络串扰风险。
Submissions 的首次观察时间是保守的 Point-in-Time 边界；采集结果必须先持久化，再由
Repository/Snapshot 的决策时间过滤。在建立可信历史采集前，旧 filing 不会被回填为当时
“已知”。M2-C 的 CI 能验证解析、限流、重试、重定向拒绝和网络地址策略，
但不能证明当前 SEC 在线可达，也不完成 company facts、观察池增量调度或 GUI 数据状态。
