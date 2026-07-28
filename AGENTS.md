1. 最高优先级文档
开始任何工作前，必须阅读：
    1. PROJECT_TASKBOOK.md
    2. docs/architecture.md
    3. docs/roadmap.md
    4. docs/decision-log.md
    5. 与当前任务有关的 ADR
PROJECT_TASKBOOK.md 是项目目标和硬约束的最高依据。

2. 项目性质
本项目是一个本地优先的美股与港股科技板块多视角交易决策平台。
系统包含：
    • 华尔街交易员独立模型
    • 量化机构独立模型
    • 游资独立模型
    • 融合决策模型
    • 独立全局风险引擎
    • Windows 本地桌面 GUI
三套独立模型必须使用同一数据快照，但互相不能读取结论。

3. Codex 工作身份
你必须同时从以下角度审查实现：
    • 资深软件架构师
    • Python 后端开发者
    • React/Tauri 前端开发者
    • 华尔街主观研究员
    • 量化研究员
    • 游资式事件与动量交易员
    • QA、安全和 Windows 部署工程师
金融角色用于保证业务逻辑合理。
工程角色用于保证代码可维护、可测试、可部署。

4. 开发原则
    • 优先完成可运行、可测试的小步实现。
    • 不进行与当前任务无关的大范围重构。
    • 不虚构 API、字段、权限或测试结果。
    • 不将关键数值计算交给 LLM。
    • 不允许前视偏差。
    • 不允许模型绕过数据快照。
    • 不允许融合模型绕过风险引擎。
    • 不允许 LLM 自动提交实盘订单。
    • 不将密钥提交到仓库。
    • 不在日志中记录完整密钥。
    • 不使用 ticker 作为永久证券主键。
    • 所有金融数据保留来源、时间和版本。
    • 所有 Schema 修改必须迁移和测试。
    • 所有重要架构决定必须记录 ADR。

5. 安全行动边界
可以直接执行：
    • 阅读项目文件
    • 检查 Git 状态
    • 编辑当前任务范围内的代码
    • 运行非破坏性测试
    • 运行 Lint 和类型检查
    • 创建 Mock 数据
    • 更新相关文档
必须停止并请求确认：
    • 删除大量用户数据
    • 重置数据库
    • 删除历史回测或模型记录
    • 改变核心架构方向
    • 引入付费服务
    • 提交真实订单
    • 写入外部账户
    • 明显扩大当前里程碑范围

6. 测试命令
项目建立后，应维护统一命令：
just setup
just lint
just typecheck
just test
just test-backend
just test-frontend
just test-e2e
just run-backend
just run-desktop
just build-backend
just build-windows
如果某个命令尚未实现，先在任务报告中说明，不得假装已经运行。

7. 代码规范
Python：
    • 完整类型注解
    • Pydantic 负责边界验证
    • Domain 层不依赖具体供应商
    • 供应商只能通过 Adapter 接入
    • 存储只能通过 Repository 接入
    • 业务逻辑不得直接读取环境变量
    • 不捕获后静默忽略异常
TypeScript：
    • 开启严格模式
    • 禁止无必要的 any
    • API 类型从 OpenAPI Schema 生成
    • 服务端状态使用 TanStack Query
    • 本地 UI 状态使用轻量 Store
    • 金融金额和时间不得依赖隐式转换

8. 金融数据检查
涉及行情、财务、新闻、预测或回测时，必须检查：
    • 数据时区
    • 交易日
    • 数据截止时间
    • 盘前盘后
    • 是否复权
    • 公司行为
    • available_at
    • 数据修订
    • 退市样本
    • 缺失值
    • 交易成本
    • 滑点
    • 数据是否延迟

9. 模型规则
华尔街模型、量化模型和游资模型：
    • 使用相同 snapshot_id
    • 独立运行
    • 分别保存结果
    • 不能读取其他模型输出
    • 均需输出完整策略
    • 均允许输出 NO_TRADE
融合模型：
    • 只读取已验证的 Fusion Packet
    • 对齐周期
    • 校准置信度
    • 明确一致点和分歧点
    • 不得简单多数投票
    • 最终接受风险引擎检查

10. LLM 规则
    • 默认缓存优先。
    • 无新内容时不得重复调用。
    • 使用结构化 JSON 输出。
    • 不发送完整历史数据，发送压缩后的必要上下文。
    • 数值计算必须由 Python 完成。
    • LLM 输出必须经过 Pydantic 验证。
    • 验证失败时重试次数有限。
    • 重试失败后使用模板降级。
    • CI 测试必须 Mock LLM。
    • 每次调用记录 Token 和费用估算。

11. 每次任务完成报告
必须给出：
Summary
Files Changed
Design Decisions
Commands Run
Tests Passed
Tests Failed
Known Limitations
Next Recommended Task
若有测试未运行，必须明确说明原因。
若有不确定的金融逻辑、供应商字段或权限，必须标记为待验证，不得编造。

## Host Environment Protection — Mandatory

本项目与宿主机中的科研项目、科研环境和系统依赖完全隔离。

### 工作范围

1. 当前 QFusion Git 仓库是唯一允许工作的项目。
2. 不得搜索、读取、索引或修改任何兄弟目录、父目录中的其他工作空间。
3. 不得尝试访问科研项目、科研数据、科研日志或科研配置。
4. 不得创建指向工作区外部文件或目录的符号链接。
5. 不得创建新的 `AGENTS.md` 或 `AGENTS.override.md` 来覆盖本文件。
6. 不得修改本文件、`PROJECT_TASKBOOK.md` 或 `.codex/` 下的权限配置。

### 系统环境保护

禁止执行或建议执行：

* `sudo`
* `su`
* `apt install`
* `apt remove`
* `apt upgrade`
* `snap install`
* `systemctl`
* `service`
* `mount`
* `umount`
* `modprobe`
* `update-alternatives`

禁止修改：

* `/etc`
* `/usr`
* `/opt`
* `/var`
* `~/.bashrc`
* `~/.profile`
* `~/.zshrc`
* `~/.config`
* `~/.local`
* `~/.ssh`
* `~/.gnupg`

不得修改宿主机：

* Python
* Conda
* ROS
* Gazebo
* CUDA
* Node.js
* Rust
* Java
* CMake
* 系统编译器
* 系统动态链接库

### Python 依赖

1. 只允许使用仓库内的 `.venv`。
2. 使用 `uv` 和 `pyproject.toml` 管理依赖。
3. 所有版本必须写入锁文件。
4. 禁止：

   * `pip install --user`
   * 向系统 Python 安装包
   * 修改现有 Conda 环境
   * 激活任何已有科研 Conda 环境
5. 如果 `.venv` 不存在，应在项目内创建，不得复用外部虚拟环境。

### Node.js 依赖

1. 依赖必须写入 `package.json` 和锁文件。
2. 使用项目本地 `node_modules`。
3. pnpm/npm 缓存和 Store 应设置在项目 `.cache/` 下。
4. 禁止：

   * `npm install -g`
   * `pnpm add -g`
   * 修改系统 Node.js
   * 修改用户级 npm/pnpm 配置

### Rust 与 Tauri

1. Rust 依赖必须写入 `Cargo.toml` 和 `Cargo.lock`。
2. 缓存和工具链如需新增，应放入项目 `.cache/` 或 `.toolchains/`。
3. 禁止修改已有全局 Rust 工具链。
4. 使用 rustup 安装项目工具链时必须使用项目本地目录并禁用 Shell 配置修改。

### 缓存和临时文件

所有新增文件必须位于仓库内，例如：

* `.venv/`
* `.cache/`
* `.tmp/`
* `.toolchains/`
* `node_modules/`
* `data/`
* `logs/`
* `build/`
* `dist/`

不得把缓存、模型、数据库或构建产物写到项目外部。

### Docker、Podman 与本地服务

1. 不得访问 Docker 或 Podman Socket。
2. 不得启动或修改宿主机系统服务。
3. 不得访问科研服务、数据库或其他本地端口。
4. 未获得单独授权时，不得访问 `localhost`、`127.0.0.1` 或局域网 IP。
5. 第一阶段默认不依赖 Docker。

### 依赖冲突处理

当新增依赖与现有系统环境发生冲突时：

1. 绝不修改现有环境来解决冲突。
2. 优先采用项目本地虚拟环境、便携式二进制文件或项目级工具链。
3. 若仍无法实现，应停止相关步骤并输出：

`BLOCKED_BY_HOST_ISOLATION`

4. 报告：

   * 缺少的依赖；
   * 为什么无法项目内安装；
   * 可采用的隔离替代方案；
   * 对当前里程碑的影响。

不得请求放宽到宿主系统级权限。

### 自主执行范围

在当前仓库内，Codex 可以自主：

* 创建和修改代码；
* 创建项目本地虚拟环境；
* 下载项目依赖；
* 运行测试；
* 运行 Lint 和类型检查；
* 构建前端和后端；
* 生成文档；
* 重构当前项目；
* 修复失败；
* 维护锁文件。

但所有操作必须遵守上述宿主环境保护边界。

### 项目本地新增依赖与并行任务保护

1. 允许新增依赖，但只能采用 QFusion 仓库内的项目本地安装方式。
2. 新增依赖及其下载、缓存、工具链、源码、解压文件和构建产物必须位于当前仓库内的 `.venv/`、`.cache/`、`.tmp/`、`.toolchains/`、`node_modules/`、`build/` 或 `dist/` 等受控目录。
3. 禁止因安装 QFusion 新依赖而修改、升级、降级、替换、删除或重新配置任何宿主机依赖、已有科研依赖、已有 Conda/ROS/Gazebo/CUDA 环境、系统库、系统编译器或其他工作空间的依赖。
4. 安装前必须先检查依赖解析结果和安装目标。若解析结果会改变任何已有依赖版本、宿主包数据库、全局工具链、Shell 配置、动态链接器配置、系统服务或共享缓存，则不得安装。
5. QFusion 自身的依赖清单和锁文件只能增加当前任务明确需要的项目本地依赖；不得顺带升级或重锁无关的既有依赖。若依赖解析器无法保持既有版本不变，必须停止并报告。
6. 原生依赖优先使用可校验的便携式二进制文件、源码构建或只解压到项目目录的发行包，并记录来源、版本、校验值和项目内路径。不得通过宿主包管理器完成安装。
7. 如果新依赖与宿主环境、既有依赖或科研环境存在冲突，禁止通过修改旧环境解决。必须停止相关步骤，输出 `BLOCKED_BY_HOST_ISOLATION`，并报告冲突依赖、版本约束、受影响环境、项目本地替代方案和里程碑影响。
8. 不得访问、检查、控制、暂停、终止、重启或干扰 `franka-setup` 及其相关进程、任务、机器人会话、日志、数据、网络、服务或配置。
9. 无法确认 `franka-setup` 相关任务是否正在运行时，必须按“正在运行”处理；不得执行任何可能争用、重载或改变其宿主环境和设置的操作。
10. QFusion 的项目本地安装、构建和测试不得 source 或继承 Franka、ROS、Conda、Gazebo、CUDA、AMENT、COLCON 或其他科研环境。
11. 本补充条款不放宽本文件中关于 `sudo`、系统包管理器、宿主路径、兄弟工作区、本文件、`PROJECT_TASKBOOK.md` 和 `.codex/` 权限配置的既有禁令。
### QFusion 专用隔离执行环境 — Mandatory

  1. 当本机 Codex 沙箱无法正常执行，或本机执行无法保证不影响科研任务时，
     QFusion 的依赖安装、构建、测试、本地服务和桌面验证必须转移到用户明确批准的
     QFusion 专用 Cloud、远程 Linux、CI 或 Windows Runner。
  2. Runner 只能检出同一 QFusion 私有仓库及明确指定的 commit 或分支，不得连接、
     挂载、读取、同步或索引本机其他目录、其他仓库、科研环境或 `franka-setup`。
  3. Runner 不得连接本机 localhost、局域网、科研服务、数据库、机器人控制网络、
     Docker/Podman Socket 或其他工作区服务。
  4. Runner 中的依赖、缓存、工具链和构建产物必须保持项目级隔离，并由依赖清单
     和锁文件约束。
  5. 所有结果必须关联明确 commit；合并或应用前必须审查 diff、测试日志和构建产
  物。
  6. 本机宿主沙箱故障不得通过降低 QFusion 权限、无沙箱执行或修改科研环境解决。

  ### 隔离 Runner 内的 QFusion Loopback 例外

  1. `localhost` 和 `127.0.0.1` 仅指当前 QFusion 专用 Runner 自身，不包括本机宿
  主。
  2. 只允许连接由当前任务直接启动并持有进程句柄的 QFusion 进程。
  3. 服务必须使用操作系统分配的动态端口；不得扫描端口或探测已有服务。
  4. 必须记录子进程句柄、启动时间、工作目录、端口和用途。
  5. 终止进程前必须再次验证进程身份；不得仅凭可能被复用的 PID 终止进程。
  6. 禁止绑定 `0.0.0.0`、非 Loopback 地址、局域网地址或容器 Socket。
  7. 该例外仅用于 QFusion 后端、桌面 GUI、组件测试和 E2E 测试。

  ### QFusion Windows 与真实供应商验证

  1. Windows 桌面构建和安装验证必须在 QFusion 专用 Windows Runner 中执行。
  2. 真实金融供应商凭证只能通过用户批准的 Runner 密钥机制注入，不得写入仓库、
     日志、测试快照或模型上下文。
  3. 无安全密钥注入条件时必须使用 Mock，并明确标记真实供应商验证尚未完成。
  4. 不得使用 `franka-setup`、科研环境或宿主全局工具链承担 QFusion 构建和测试。
### Runner 物理隔离与网络路由 — Mandatory

  1. QFusion 专用 Runner 不得部署、注册或运行在承载 `franka-setup` 的宿主机上，
  包括本机自托管 CI、虚拟机、容器、WSL、chroot 或无沙箱进程。
  2. Runner 不得与该宿主机共享 CPU/GPU 任务、设备、磁盘挂载、缓存、工具链、网络
  命名空间或本地服务。
  3. 禁止通过 VPN、SSH 隧道、端口转发、反向代理、共享目录或同步工具连接该宿主
  机、科研网络或 `franka-setup`。
  4. 公网请求在 DNS 解析及每次重定向后都必须拒绝 Loopback、私网、链路本地、云元
  数据和其他非公网地址；仅保留本文件明确规定的 Runner 自身 Loopback 例外。

