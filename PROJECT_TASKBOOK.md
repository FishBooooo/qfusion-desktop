# QFusion Desktop

<!-- Canonical project taskbook; filename normalized to match AGENTS.md. -->

## 美股与港股科技板块“3+1”多视角本地交易决策平台

### Codex 项目总任务书

---

# 0. 项目定义

## 0.1 项目暂定名称

**QFusion Desktop**

项目名称允许后续修改，但内部代码命名、数据库命名和包名称在确定后必须保持统一。

## 0.2 项目目标

开发一套主要运行在本地 Windows 电脑上的美股、港股科技板块分析与交易决策平台。

平台必须同时提供以下四套完整视角：

1. **华尔街主观交易员模型**
2. **量化机构模型**
3. **顶级游资模型**
4. **融合决策模型**

前三套模型均为独立、完整的分析与交易决策系统。每一套模型都必须能够独立读取：

* 行情
* 成交量
* 基本面
* 财报
* 宏观数据
* 新闻
* 公司公告
* 市场情绪
* 期权
* 资金流
* 空头数据
* 盘口
* 板块和主题
* 账户风险数据

每一套独立模型都必须独立输出：

* 市场判断
* 股票或板块分析
* 多空方向
* 适用周期
* 入场触发
* 止损条件
* 时间止损
* 加仓与减仓条件
* 目标位
* 仓位与账户风险建议
* 禁止交易条件
* 数据不足与不确定性

融合决策模型接收前三套模型的结构化结果，结合：

* 当前市场环境
* 三套模型的历史可靠度
* 模型分歧
* 数据质量
* 账户持仓
* 交易成本
* 全局风险约束

形成一套新的综合分析与交易方案。

## 0.3 核心原则

项目必须遵循：

```text
三套模型独立运行
+
共享同一个时间点的数据快照
+
融合模型只在独立模型完成后运行
+
风险引擎拥有最终否决权
```

不允许把项目实现为四个简单提示词。

所谓“模型”必须包含：

```text
确定性数据处理
+
规则与指标系统
+
统计或机器学习模型
+
事件和文本提取
+
风险控制
+
可选的LLM解释层
```

---

# 1. Codex 的工作身份

Codex 在本项目中同时承担以下角色。

## 1.1 资深软件架构师

负责：

* 总体架构
* 模块边界
* 数据契约
* 进程通信
* Windows 部署
* 数据版本管理
* 可扩展性
* 故障恢复

## 1.2 资深 Python 后端开发者

负责：

* FastAPI 本地服务
* 数据适配器
* 数据清洗
* 数据库存储
* 定时任务
* 模型服务
* 回测框架
* 风险引擎
* 日志和审计

## 1.3 资深前端与桌面端开发者

负责：

* Tauri 桌面外壳
* React + TypeScript 前端
* 金融仪表板
* K线、成交量和因子图表
* 四模型对比页面
* 数据新鲜度和风险提示
* 深色与浅色主题
* Windows 安装与升级体验

## 1.4 华尔街主观交易员与研究员

在设计华尔街模型时，必须从以下角度审查：

* 市场定价是否存在预期差
* 宏观环境是否支持交易
* 公司基本面和盈利质量
* 管理层指引
* 分析师一致预期
* 估值和隐含预期
* 产业链和竞争格局
* 事件催化
* 情景概率
* 逻辑失效条件

## 1.5 量化机构研究员

在设计量化模型时，必须检查：

* Point-in-Time 数据
* 前视偏差
* 生存偏差
* 标签泄漏
* 数据修订
* 样本外测试
* 滚动回测
* 交易成本
* 滑点
* 市场冲击
* 模型漂移
* 因子相关性
* 组合风险

## 1.6 顶级游资式短线交易员

在设计游资模型时，必须考虑：

* 主线
* 龙头
* 次龙头
* 补涨
* 催化
* 资金聚集
* 情绪周期
* 分歧与回流
* 相对成交量
* VWAP
* 锚定 VWAP
* 开盘区间
* 假突破
* 退潮
* 时间止损
* 流动性

“游资式”仅指合法的事件驱动、趋势、动量和情绪交易方法，禁止设计或实现：

* 虚假消息传播
* 对倒
* 虚假挂单
* 拉抬价格
* 操纵收盘价
* 诱导他人交易
* 利用未公开重大信息

## 1.7 QA、DevOps 与安全工程师

负责：

* 自动化测试
* Windows 打包测试
* 数据一致性测试
* API 限流测试
* 断网和断线恢复
* 密钥安全
* 本地端口安全
* 数据备份
* 日志脱敏
* CI/CD

---

# 2. 不可违反的硬性要求

## 2.1 本地优先

核心计算、数据存储、指标生成、回测和模型评分必须在用户本地完成。

在没有 GPT API、没有本地 LLM、甚至暂时没有网络时，应用仍应能够：

* 启动
* 查看历史缓存数据
* 查看此前生成的四模型报告
* 运行纯数值指标
* 运行回测
* 查看交易日志
* 导出报告

## 2.2 Linux 开发，Windows 成品部署

开发环境以 Linux 为主。

最终必须交付：

* Windows 10/11 可安装版本
* `setup.exe` 或 `.msi`
* 无需用户自行安装 Python
* 无需用户自行安装 Node.js
* 无需用户手动启动后端
* 安装后可从开始菜单启动
* 可选择是否开机自动启动
* 可从界面更新 API 密钥和配置
* 可完整卸载
* 不删除用户数据，除非用户明确选择

## 2.3 默认不依赖 Docker

默认本地版必须能在没有 Docker Desktop 的 Windows 环境运行。

同时可以提供：

```text
Local Lite 模式：
SQLite + DuckDB + Parquet

Full Research 模式：
PostgreSQL + TimescaleDB + Docker Compose
```

第一阶段优先完成 Local Lite。

## 2.4 极低 GPT Token 消耗

平台核心功能不能依赖每次打开页面都调用 GPT。

必须实现：

* 内容哈希去重
* 报告缓存
* 分析快照缓存
* 提示词版本缓存
* 结构化事实缓存
* 增量新闻分析
* 增量财报分析
* 夜间批处理
* 每日 Token 上限
* 每月费用上限
* 云模型关闭模式
* 本地模型模式
* 混合模型模式

## 2.5 模型独立

华尔街、量化和游资模型运行时：

```text
不得看到其他独立模型的结论
不得看到其他独立模型的置信度
不得看到其他独立模型的交易建议
```

它们只能共享同一个原始数据快照。

只有融合模型可以读取三套模型的结构化输出。

## 2.6 可追溯和可复现

每一个结论必须能够追溯到：

* 哪个数据快照
* 哪个数据源
* 数据截止时间
* 哪个模型版本
* 哪个提示词版本
* 哪个特征集版本
* 哪个参数版本
* 哪些证据
* 是否存在缺失数据

## 2.7 风险优先

系统允许输出：

```text
NO_TRADE
WATCH_ONLY
PAPER_ONLY
```

系统没有义务每天给出交易。

系统禁止使用：

* 保证上涨
* 必涨
* 无风险
* 稳赚
* 满仓
* 梭哈

等确定性措辞。

## 2.8 初期禁止自动实盘

MVP 和第一阶段正式版本仅允许：

* 研究
* 模拟交易
* 订单预览
* 人工确认

不得允许 LLM 直接向券商提交实盘订单。

实盘接入必须在后续独立阶段完成，并满足：

```text
模型建议
→ 风险检查
→ 订单预览
→ 人工确认
→ 券商前置检查
→ 提交订单
```

---

# 3. 产品范围

## 3.1 第一阶段支持市场

* 美股
* 港股

## 3.2 第一阶段支持资产

* 普通股票
* ADR
* ETF
* 行业 ETF
* 科技主题板块
* 自定义股票篮子

期权第一阶段主要用于：

* 隐含波动率
* 期权链
* Put/Call
* 未平仓量
* 预期波动
* 偏斜
* 期限结构
* 关键行权价

第一阶段不要求实现期权自动下单。

## 3.3 第一阶段支持周期

* 日内
* 1～5 个交易日
* 5～20 个交易日
* 1～3 个月

## 3.4 第一阶段不做

* 微秒级高频交易
* 全市场 Level 2 历史回放
* 自动化实盘交易
* 多用户云平台
* 手机 App
* 社交跟单
* 自动复制他人仓位
* 面向公众的数据转售
* 对外提供投顾服务

---

# 4. 总体架构

```text
┌───────────────────────────────────────────┐
│             Tauri Desktop App             │
│      React + TypeScript + GUI + Charts    │
└──────────────────────┬────────────────────┘
                       │ Local authenticated API
                       ▼
┌───────────────────────────────────────────┐
│           Python FastAPI Sidecar          │
│                                           │
│  API Gateway                              │
│  Scheduler                                │
│  Data Sync                                │
│  Snapshot Service                         │
│  Model Orchestrator                       │
│  Backtest Service                         │
│  Risk Engine                              │
│  Report Generator                         │
└──────────────┬───────────────┬────────────┘
               │               │
               ▼               ▼
┌────────────────────┐   ┌──────────────────────┐
│ SQLite             │   │ DuckDB + Parquet     │
│                    │   │                      │
│ Settings           │   │ OHLCV                │
│ Watchlists         │   │ Features             │
│ Model runs         │   │ Predictions          │
│ Audit              │   │ Backtests            │
│ Reports            │   │ Options snapshots    │
└────────────────────┘   └──────────────────────┘
               │
               ▼
┌───────────────────────────────────────────┐
│ Local Raw Store                           │
│ JSON / CSV / HTML / PDF / Filing / News   │
└───────────────────────────────────────────┘
```

模型层：

```text
                Shared Snapshot
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 WallStreet Engine  Quant Engine  HotMoney Engine
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                Fusion Packet Builder
                       ▼
                Fusion Decision Engine
                       ▼
                 Global Risk Engine
                       ▼
                   Final Report
```

---

# 5. 技术选型

## 5.1 桌面端

```text
Tauri 2
React
TypeScript
Vite
Ant Design
Apache ECharts
TanStack Query
Zustand
```

要求：

* 不采用 Electron 作为默认最终方案
* Streamlit 只允许用于非常早期原型，不作为最终 GUI
* 前端不得直接读取数据供应商 API Key
* 所有外部数据访问必须经过本地后端

## 5.2 后端

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
httpx
websockets
Polars
Pandas
NumPy
scikit-learn
statsmodels
LightGBM 或 XGBoost
DuckDB
PyArrow
APScheduler
```

依赖管理：

```text
uv
pyproject.toml
```

## 5.3 本地存储

### 元数据和应用状态

SQLite：

* 用户配置
* 观察池
* 数据源配置
* 模型运行记录
* 报告索引
* 风险配置
* 交易计划
* 模拟订单
* 审计日志

### 大型分析数据

DuckDB + Parquet：

* 日线
* 分钟线
* 期权快照
* 因子
* 标签
* 模型预测
* 回测结果
* 板块宽度
* 资金流快照

### 原始文件

本地文件系统：

* SEC JSON
* SEC XBRL
* HKEX 公告
* 财报 PDF
* 新闻原文
* API 原始响应
* 公司 IR 文件

## 5.4 高级存储模式

后续支持：

```text
PostgreSQL
TimescaleDB
Docker Compose
```

业务代码必须通过 Repository Interface 访问数据，不允许把 DuckDB 或 PostgreSQL SQL 写死在业务逻辑中。

## 5.5 后端打包

Python 后端最终编译为 Windows 可执行文件：

* 优先评估 Nuitka standalone
* PyInstaller 作为备选
* 由 Tauri 作为 Sidecar 启动
* 用户无需安装 Python

## 5.6 测试工具

Python：

```text
pytest
pytest-asyncio
pytest-cov
Hypothesis
Ruff
mypy 或 pyright
```

前端：

```text
Vitest
React Testing Library
Playwright
ESLint
Prettier
```

Rust/Tauri：

```text
cargo fmt
cargo clippy
cargo test
```

---

# 6. 推荐仓库目录

```text
qfusion-desktop/
├── AGENTS.md
├── PROJECT_TASKBOOK.md
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .env.example
├── .gitignore
├── pyproject.toml
├── pnpm-workspace.yaml
├── Makefile
├── justfile
│
├── apps/
│   └── desktop/
│       ├── src/
│       ├── src-tauri/
│       ├── public/
│       ├── package.json
│       └── vite.config.ts
│
├── services/
│   └── backend/
│       ├── qfusion/
│       │   ├── api/
│       │   ├── config/
│       │   ├── domain/
│       │   ├── providers/
│       │   ├── ingestion/
│       │   ├── storage/
│       │   ├── snapshots/
│       │   ├── features/
│       │   ├── models/
│       │   │   ├── wallstreet/
│       │   │   ├── quant/
│       │   │   ├── hotmoney/
│       │   │   └── fusion/
│       │   ├── risk/
│       │   ├── backtest/
│       │   ├── llm/
│       │   ├── reports/
│       │   ├── scheduler/
│       │   ├── security/
│       │   └── main.py
│       └── tests/
│
├── packages/
│   ├── contracts/
│   ├── generated-client/
│   └── ui-components/
│
├── prompts/
│   ├── wallstreet/
│   ├── hotmoney/
│   ├── fusion/
│   └── extraction/
│
├── schemas/
│   ├── analysis_request.schema.json
│   ├── model_result.schema.json
│   ├── fusion_packet.schema.json
│   └── trade_plan.schema.json
│
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── model-design.md
│   ├── gui-spec.md
│   ├── deployment-windows.md
│   ├── security.md
│   ├── api-providers.md
│   ├── token-budget.md
│   ├── testing.md
│   ├── roadmap.md
│   ├── decision-log.md
│   └── adr/
│
├── scripts/
│   ├── bootstrap_linux.sh
│   ├── bootstrap_windows.ps1
│   ├── build_backend.py
│   ├── build_windows.ps1
│   ├── backup.py
│   └── restore.py
│
├── fixtures/
│   ├── market_data/
│   ├── filings/
│   ├── news/
│   └── options/
│
└── .github/
    └── workflows/
        ├── ci.yml
        └── windows-release.yml
```

---

# 7. 数据源适配层

## 7.1 数据源规划

首批适配器：

```text
OpenFIGI
SEC EDGAR
Tradier
Moomoo/Futu
Longbridge
Tiingo
Massive
FRED/ALFRED
HKMA
GDELT
Marketaux
FINRA
OCC
HKEX/HKEXnews
```

所有供应商必须通过统一 Adapter 接口访问。

禁止在模型代码、GUI 或路由处理器中直接调用供应商 SDK。

## 7.2 Provider Capability

每个适配器必须声明：

```text
provider_name
provider_version
supported_markets
supported_asset_types
supported_intervals
supports_realtime
supports_premarket
supports_afterhours
supports_options
supports_fundamentals
supports_news
supports_filings
supports_streaming
rate_limit
historical_start
venue_scope
quality_level
license_scope
```

## 7.3 核心接口

```python
class InstrumentProvider:
    async def search_instruments(...)
    async def get_instrument(...)
    async def get_symbol_history(...)

class MarketDataProvider:
    async def get_bars(...)
    async def get_quotes(...)
    async def get_trades(...)
    async def stream_quotes(...)

class FundamentalProvider:
    async def get_financials(...)
    async def get_estimates(...)
    async def get_corporate_actions(...)

class NewsProvider:
    async def get_news(...)
    async def get_filings(...)
    async def get_events(...)

class OptionsProvider:
    async def get_option_chain(...)
    async def get_option_snapshot(...)

class FlowProvider:
    async def get_short_interest(...)
    async def get_short_volume(...)
    async def get_southbound_flow(...)
```

## 7.4 数据源仲裁

真值源按字段决定，而不是设置一个万能优先级。

示例：

```text
美股公告：SEC
港股公告：HKEXnews
美股当前报价：券商或合并行情
港股当前报价：已验证实时权限的港股行情源
美国宏观：FRED/BLS/BEA/Treasury
香港宏观：HKMA
订单和成交：实际执行券商
期权总量：OCC
Short Interest：FINRA
```

## 7.5 数据质量字段

所有事实数据必须带有：

```text
source
source_record_id
source_quality_level
venue_scope
license_scope

event_time
published_at
available_at
received_at
ingested_at

revision_id
effective_from
effective_to

quality_flag
raw_payload_hash
is_adjusted
adjustment_type
```

回测只能使用：

```text
available_at <= decision_time
```

---

# 8. 本地数据目录

Windows 默认目录：

```text
%LOCALAPPDATA%\QFusion\
```

内部结构：

```text
QFusion/
├── config/
├── database/
│   ├── app.sqlite3
│   └── warehouse.duckdb
├── parquet/
├── raw/
│   ├── filings/
│   ├── news/
│   ├── market/
│   └── options/
├── models/
├── cache/
├── reports/
├── exports/
├── logs/
└── backups/
```

不得把用户数据写入应用安装目录。

## 8.1 Parquet 分区

示例：

```text
parquet/
  bars/
    market=US/
      interval=1d/
        symbol=NVDA/
          year=2026/
            month=07/
```

## 8.2 单写入器原则

DuckDB 和 Parquet 的更新必须通过单独的写入队列进行。

禁止多个后台任务同时写同一个 DuckDB 文件。

读取任务可以并发。

---

# 9. 数据更新模式

## 9.1 默认每日模式

用户平时只需启动应用，系统自动执行增量更新。

任务包括：

* 更新交易日历
* 更新观察池行情
* 更新日线
* 更新公司行为
* 检查新财报
* 检查新公告
* 检查新新闻
* 更新基本面
* 更新分析师预期快照
* 更新期权日终快照
* 计算因子
* 运行三套独立模型
* 运行融合模型
* 生成缓存报告

不得每次重新下载全部历史。

## 9.2 按需盘中模式

用户主动开启后：

* 只订阅当前页面和观察池
* 只拉取必要的分钟行情
* 只更新被选择股票或板块
* 关闭页面后自动释放订阅
* 记录供应商配额使用量

## 9.3 断网降级

断网时：

* 应用正常启动
* 显示最后更新时间
* 显示 STALE_DATA
* 禁止生成新的实时交易许可
* 允许读取缓存报告
* 允许运行历史回测

---

# 10. 统一分析快照

每一次分析必须先生成 `AnalysisSnapshot`。

结构至少包括：

```text
snapshot_id
target_type
target_id
market
requested_horizon
decision_time
market_timezone
created_at

price_as_of
fundamental_as_of
news_as_of
options_as_of
macro_as_of
flow_as_of

provider_versions
dataset_versions
missing_data
stale_data
quality_score
```

四套模型必须使用同一个 `snapshot_id`。

---

# 11. 华尔街主观交易员模型

## 11.1 定位

使用全部可用数据，寻找：

```text
市场定价
与
未来基本面现实
之间的差异
```

## 11.2 内部子模块

```text
MacroRegimeAnalyzer
IndustryCycleAnalyzer
CompanyQualityAnalyzer
EarningsAnalyzer
ManagementToneAnalyzer
EstimateRevisionAnalyzer
ValuationAnalyzer
ExpectationGapAnalyzer
EventCatalystAnalyzer
OptionsExpectationAnalyzer
PriceConfirmationAnalyzer
ScenarioEngine
WallStreetTradePlanner
WallStreetRiskController
```

## 11.3 必须分析

* 宏观和利率环境
* 行业周期
* 公司盈利质量
* 财务健康
* 自由现金流
* 资本开支
* 股票薪酬和稀释
* 管理层指引
* 分析师预测修正
* 估值
* Reverse DCF 或隐含预期
* 同行业比较
* 供应链
* 竞争格局
* 新闻和事件
* 期权隐含波动
* 价格和成交量确认

## 11.4 输出

```text
strategic_direction
tactical_direction
intraday_view
five_day_view
twenty_day_view
three_month_view

market_expectation
expectation_gap
valuation_state
catalysts
bull_case
base_case
bear_case
invalidation_conditions

entry_conditions
stop_conditions
time_stop
targets
position_risk
no_trade_conditions
confidence
evidence
```

## 11.5 第一版实现

V0 不追求复杂 AI。

第一版采用：

```text
确定性财务指标
+
事件和公告抽取
+
估值规则
+
情景树
+
可选LLM自然语言解释
```

---

# 12. 量化机构模型

## 12.1 定位

使用全部数据计算：

```text
扣除交易成本和风险后的统计优势
```

## 12.2 子模块

```text
UniverseFilter
FeaturePipeline
LabelPipeline
RegimeClassifier
FactorModel
ReturnPredictor
ProbabilityCalibrator
TransactionCostModel
PortfolioOptimizer
QuantTradePlanner
ModelDriftMonitor
```

## 12.3 因子组

### 价格和动量

```text
momentum_5d
momentum_20d
momentum_60d
relative_strength
gap_return
distance_to_high
mean_reversion
realized_volatility
```

### 基本面

```text
revenue_growth
eps_growth
gross_margin_change
operating_margin_change
fcf_yield
roe
roic
accruals
share_dilution
earnings_quality
```

### 预期

```text
earnings_surprise
estimate_revision
revision_breadth
analyst_dispersion
guidance_change
```

### 新闻与事件

```text
news_sentiment
news_novelty
news_velocity
filing_tone_change
event_importance
```

### 资金和流动性

```text
relative_volume
turnover
spread_bps
short_interest
short_volume
southbound_flow
option_volume
```

### 期权

```text
implied_volatility
iv_percentile
iv_minus_realized
skew
term_structure
put_call_ratio
expected_move
```

## 12.4 第一版模型

依次实现：

1. 横截面因子评分
2. 逻辑回归或线性模型
3. 简单集成
4. LightGBM/XGBoost
5. 市场状态条件模型

复杂模型不能先于基线模型。

## 12.5 验证

必须实现：

* Walk-forward
* 样本外测试
* 时间序列切分
* 交易成本
* 滑点
* 退市样本
* 公司行为
* Point-in-Time
* 模型校准
* 因子贡献
* 信号衰减

## 12.6 输出

```text
expected_return_1d
expected_return_5d
expected_return_20d

up_probability
down_probability
prediction_interval
confidence_raw
confidence_calibrated

positive_factors
negative_factors
factor_contributions

expected_cost
net_expected_edge
suggested_risk
suggested_weight

entry_conditions
rebalance_conditions
exit_conditions
time_stop
model_risks
similar_sample_count
data_quality
```

量化输出不得只有一个“综合评分”。

---

# 13. 顶级游资模型

## 13.1 定位

使用全部数据判断：

```text
边际资金正在向哪里集中
以及
资金强化何时开始、何时衰退
```

## 13.2 子模块

```text
MarketSentimentAnalyzer
CatalystDetector
ThemeGraph
ThemeStrengthEngine
LeaderRanker
RelativeVolumeEngine
IntradayStructureEngine
OptionsCrowdingEngine
EmotionStateMachine
HotMoneyTradePlanner
HotMoneyRiskController
```

## 13.3 主题和板块指标

```text
theme_return_1d
theme_return_5d
theme_return_20d
theme_relative_strength
theme_advancing_ratio
theme_new_high_ratio
theme_relative_volume
theme_turnover_growth
theme_news_velocity
theme_news_novelty
theme_age
```

## 13.4 龙头评分

至少包括：

```text
relative_strength
relative_volume
turnover_rank
first_response_time
gap_hold_ratio
vwap_hold_ratio
distance_to_high
catalyst_relevance
sector_leadership
liquidity
options_activity
```

## 13.5 情绪状态机

```text
DORMANT
IGNITION
SPREAD
DIVERGENCE
REFLOW
ACCELERATION
CLIMAX
DISTRIBUTION
RETREAT
```

每一个状态必须有明确、可回测的进入和退出规则。

不得仅让 LLM 根据文字主观判断情绪阶段。

## 13.6 盘中指标

* 盘前涨幅
* 盘前成交量
* 开盘缺口
* 开盘 15/30 分钟区间
* VWAP
* 锚定 VWAP
* 相对成交量
* 大额成交
* 主动买卖
* 日内高低点
* 假突破
* 港股午盘前后强弱
* 龙头和跟风股同步性

## 13.7 输出

```text
market_sentiment
leading_themes
theme_rank
theme_state
leader
secondary_leader
followers

leader_score
theme_persistence
crowding_level

allow_chasing
allow_pullback_entry
entry_trigger
add_trigger
reduce_trigger
price_stop
time_stop
retreat_signals
maximum_holding_period
overnight_risk
position_risk
confidence
```

---

# 14. 三套独立模型的公共输出

三套模型都必须输出相同的公共核心结构。

```json
{
  "run_id": "uuid",
  "model_type": "wallstreet|quant|hotmoney",
  "model_version": "string",
  "snapshot_id": "uuid",
  "target": {
    "type": "stock|sector|basket",
    "id": "string",
    "market": "US|HK"
  },
  "views": {
    "intraday": {
      "direction_score": 0,
      "confidence_raw": 0.0,
      "confidence_calibrated": 0.0
    },
    "five_day": {},
    "twenty_day": {},
    "three_month": {}
  },
  "action": "NO_TRADE|WATCH|PREPARE|TRIAL|ADD|HOLD|REDUCE|EXIT",
  "trade_plan": {},
  "risk": {},
  "evidence": [],
  "data_quality": {},
  "known_blind_spots": []
}
```

`direction_score` 范围：

```text
-100：强烈偏空
0：中性
+100：强烈偏多
```

置信度必须区分：

```text
confidence_raw
confidence_calibrated
```

融合模型优先使用校准后的置信度。

---

# 15. 融合决策模型

## 15.1 输入

融合模型接收：

1. 公共数据快照摘要
2. 华尔街 Fusion Packet
3. 量化 Fusion Packet
4. 游资 Fusion Packet
5. 三套模型历史校准数据
6. 当前账户和持仓
7. 交易成本
8. 全局风险约束

融合模型不读取前三套模型冗长的自由文本报告作为主要输入。

## 15.2 处理流程

```text
validate_packets
→ align_horizons
→ calibrate_confidence
→ detect_agreements
→ detect_disagreements
→ classify_regime
→ calculate_dynamic_weights
→ build_fusion_scenarios
→ generate_trade_plan
→ global_risk_check
```

## 15.3 必须分周期输出

融合模型不得强行生成一个单一方向。

必须分别输出：

```text
战略层：20日到3个月
战术层：1到10日
执行层：日内入场和退出
风险层：仓位、最大亏损、禁止交易条件
```

## 15.4 初期融合方式

V0：

* 规则门控
* 人工定义市场状态权重
* 分歧惩罚
* 数据质量惩罚
* 成本惩罚

V1：

* 根据三套模型历史表现进行动态校准

V2：

* 训练元模型
* 预测不同场景下哪套模型更可靠

## 15.5 分歧处理

示例：

```text
华尔街看多 + 量化看多 + 游资不确认
→ 基本面和统计支持，但等待资金触发

华尔街看多 + 量化看空 + 游资看多
→ 只允许小仓位、短周期事件交易

华尔街看空 + 量化看多 + 游资看多
→ 战术交易，不得被套后改成长线

三者强烈分歧
→ WATCH_ONLY 或 NO_TRADE
```

## 15.6 输出

```text
strategic_view
tactical_view
execution_view

agreement_points
disagreement_points
dominant_model
model_weights

final_action
entry_conditions
add_conditions
reduce_conditions
exit_conditions
price_stop
time_stop
targets
maximum_account_risk

risk_permission
data_quality
evidence
```

---

# 16. 全局风险引擎

全局风险引擎独立于四套模型。

不得使用自由文本 LLM 作为最终风险判断器。

## 16.1 检查内容

* 数据是否过期
* 行情是否延迟
* 数据源是否冲突
* 是否停牌
* 买卖价差
* 流动性
* 重大财报或事件
* 单股暴露
* 板块暴露
* 科技股总暴露
* 账户回撤
* 当日亏损
* 本周亏损
* 持仓相关性
* 期权最大损失
* 借券状态
* 交易成本
* 港股税费
* API 数据质量
* 模型是否漂移

## 16.2 输出状态

```text
APPROVED
APPROVED_WITH_REDUCED_SIZE
WATCH_ONLY
PAPER_TRADE_ONLY
REJECTED
```

任何模型都不能绕过风险引擎。

---

# 17. GPT 与本地模型架构

## 17.1 模式

系统必须支持：

```text
LLM_MODE=off
LLM_MODE=local
LLM_MODE=hybrid
LLM_MODE=cloud
```

### off

* 不调用任何 LLM
* 使用规则、统计模型和模板报告

### local

* 使用本地模型处理新闻分类、摘要和解释
* 不向外部发送文本

### hybrid

* 常规任务本地完成
* 复杂公告、财报差异和融合解释才调用 GPT

### cloud

* 允许 GPT 完成更多文本分析
* 仍不允许 GPT 进行数值计算和风险许可

## 17.2 GPT 允许承担

* 公告事件分类
* 财报电话会措辞变化
* 新闻去重辅助
* 事件影响链提取
* 证据摘要
* 华尔街情景解释
* 游资催化解释
* 融合分歧解释
* 用户可读报告生成

## 17.3 GPT 禁止承担

* 技术指标计算
* 因子计算
* 预测收益计算
* 交易成本计算
* 仓位计算
* 风险上限判断
* 数据时间判断
* 回测结果计算
* 实盘下单

## 17.4 Token 优化规则

必须实现以下机制：

### 内容哈希

```text
sha256(
  source_document
  + extraction_prompt_version
  + model_version
)
```

哈希未变化时，不重复调用。

### 增量处理

只向模型发送：

* 新增公告
* 新增新闻
* 与上次不同的财报段落
* 管理层措辞变化
* 结构化数据的变化摘要

禁止每天重复发送完整年报。

### 稳定提示词前缀

* 系统指令固定
* JSON Schema 固定
* 角色定义固定
* 变化数据放在提示词末尾

### 结构化输出

所有运行时 GPT 调用必须返回 JSON Schema。

不得依靠正则表达式从自由文本中猜测关键字段。

### 夜间批处理

非实时任务优先夜间批量处理：

* 新公告提取
* 新闻分类
* 财报段落摘要
* 观察池日报

### 输出限制

每次调用设置：

* 最大输出长度
* 任务级 Token 预算
* 超限停止
* 超限日志

## 17.5 工程目标

目标而非绝对承诺：

```text
查看缓存报告：0 次云模型调用
查看缓存图表：0 次云模型调用
运行量化模型：0 次云模型调用
运行游资数值状态机：0 次云模型调用
日常无新公告时：接近 0 次云模型调用
有新公告时：仅处理新增内容
综合自然语言报告：按需调用
```

GUI 必须显示：

* 今日输入 Token
* 今日输出 Token
* 今日费用估算
* 本月费用估算
* 缓存命中率
* 本地模型调用次数
* 云模型调用次数

---

# 18. GUI 设计规范

## 18.1 设计目标

界面应做到：

* 简洁
* 现代
* 信息密度高但不拥挤
* 重点明显
* 可快速理解
* 深色和浅色主题
* 中文为默认语言
* 英文字段作为内部术语保留
* 不仅依靠颜色表达风险

## 18.2 页面结构

### 首页 Dashboard

展示：

* 美股市场状态
* 港股市场状态
* 主要科技板块强弱
* 当前主线
* 风险状态
* 今日重要事件
* 观察池异动
* 数据更新状态
* Token 和 API 使用情况

### 股票分析工作台

顶部：

```text
股票搜索
市场
时间周期
数据截止时间
刷新按钮
```

标签页：

```text
华尔街视角
量化机构视角
游资视角
综合视角
横向对比
证据与数据
```

### 板块分析工作台

展示：

* 板块趋势
* 板块宽度
* 龙头和次龙头
* 成分股排名
* 基本面周期
* 因子分布
* 情绪周期
* 综合参与策略

### 回测实验室

展示：

* 策略
* 时间范围
* 股票池
* 成本假设
* 收益曲线
* 回撤
* Sharpe
* 胜率
* 换手率
* 信号衰减
* 分市场状态表现
* 模型版本

### 数据中心

展示：

* 数据源状态
* 实时或延迟
* 最新更新时间
* API 配额
* 异常记录
* 数据冲突
* 缺失数据
* 手动同步

### 模型中心

展示：

* 四套模型版本
* 最近运行
* 历史命中率
* 校准曲线
* 模型漂移
* 特征版本
* 提示词版本

### 设置

包括：

* API Key
* 数据源优先级
* LLM 模式
* Token 预算
* 更新计划
* 账户风险参数
* 本地数据目录
* 备份和恢复
* 开机启动
* 日志级别

## 18.3 股票分析顶部摘要

顶部必须有统一行动卡：

```text
当前状态
方向
周期
置信度
风险许可
数据新鲜度
主要触发
主要风险
```

不得让用户翻到页面底部才知道结论。

## 18.4 图表

至少支持：

* K线
* 成交量
* VWAP
* 锚定 VWAP
* 均线
* 财报事件标记
* 新闻事件标记
* 相对强弱
* 因子雷达
* 模型方向对比
* 情景概率
* 预测区间
* 板块宽度
* 情绪状态时间轴
* 回测权益曲线
* 回撤曲线

---

# 19. 本地 API 设计

## 19.1 系统

```text
GET  /api/v1/health
GET  /api/v1/system/status
GET  /api/v1/system/usage
POST /api/v1/system/backup
POST /api/v1/system/restore
```

## 19.2 数据

```text
POST /api/v1/data/sync
GET  /api/v1/data/providers
GET  /api/v1/data/quality
GET  /api/v1/instruments/search
GET  /api/v1/instruments/{id}
```

## 19.3 分析

```text
POST /api/v1/analysis
GET  /api/v1/analysis/{request_id}
GET  /api/v1/analysis/{request_id}/comparison
GET  /api/v1/analysis/{request_id}/evidence
```

请求示例：

```json
{
  "market": "US",
  "target_type": "stock",
  "symbol": "NVDA",
  "perspectives": [
    "wallstreet",
    "quant",
    "hotmoney",
    "fusion"
  ],
  "horizon": "5d",
  "as_of": "latest",
  "refresh_policy": "cache_first",
  "execution_mode": "research"
}
```

## 19.4 回测

```text
POST /api/v1/backtests
GET  /api/v1/backtests/{id}
GET  /api/v1/backtests/{id}/metrics
GET  /api/v1/backtests/{id}/trades
```

## 19.5 模拟交易

```text
POST /api/v1/trades/preview
POST /api/v1/paper-orders
GET  /api/v1/paper-portfolio
GET  /api/v1/paper-orders
```

不得在第一阶段暴露实盘提交接口。

---

# 20. Windows 进程和部署

## 20.1 进程生命周期

启动流程：

```text
用户启动QFusion.exe
→ Tauri生成本次会话令牌
→ Tauri启动Python Sidecar
→ Sidecar选择本地空闲端口
→ Sidecar输出端口和健康状态
→ 前端携带会话令牌连接
→ 加载缓存数据
→ 后台检查增量更新
```

后端必须：

* 仅监听 `127.0.0.1`
* 禁止监听公网
* 使用随机可用端口
* 使用临时会话令牌
* 限制 CORS
* 支持优雅退出
* 支持崩溃后自动重启
* 防止启动多个冲突写入进程

## 20.2 Windows 安装包

必须支持：

* NSIS `setup.exe`
* 后续可增加 MSI
* 当前用户安装
* 无管理员权限安装优先
* 开始菜单快捷方式
* 桌面快捷方式可选
* 自动检测 WebView2
* 显示版本号
* 完整卸载
* 升级时保留数据

## 20.3 Windows 构建

Windows 安装包必须在以下之一生成：

* Windows 实机
* Windows 虚拟机
* GitHub Actions Windows Runner

Linux 可以进行日常开发和测试，但最终 Windows Release 必须经过真实 Windows 构建和烟雾测试。

## 20.4 可选 Full Research 模式

后续可提供：

```text
docker-compose.full.yml
```

包含：

* PostgreSQL
* TimescaleDB
* 可选 MLflow

Windows 用户通过 Docker Desktop/WSL2 启用。

Local Lite 不依赖此模式。

---

# 21. 安全要求

## 21.1 API Key

密钥不得：

* 提交到 Git
* 写入普通日志
* 返回前端
* 写入报告
* 包含在异常堆栈中

优先保存到：

* Windows Credential Manager
* Linux Secret Service
* 系统 Keyring

## 21.2 日志脱敏

必须自动遮蔽：

* API Key
* Bearer Token
* 账户号
* 邮箱
* 用户路径中的敏感部分
* 券商订单认证信息

## 21.3 本地 API

* 只绑定 localhost
* 使用会话认证
* 防止浏览器中其他网站调用
* 不允许任意命令执行
* Sidecar 参数采用白名单
* 导入文件严格校验路径和类型

## 21.4 供应商许可

每个适配器必须在文档中记录：

* 允许个人研究
* 是否允许缓存
* 是否允许长期存储
* 是否允许公开展示
* 是否允许商业用途
* 是否允许再分发

---

# 22. 测试要求

## 22.1 数据适配器

每个适配器必须有：

* Mock 测试
* Contract 测试
* 限流测试
* 超时测试
* 重试测试
* 空响应测试
* 字段变化测试
* 时区测试
* 市场休市测试

## 22.2 财务和行情

必须测试：

* 拆股
* 分红
* 反向拆股
* 股票代码变化
* 退市
* 港股每手股数
* 盘前盘后
* 美股夏令时
* 港股午间休市
* 半日交易
* 财务重述
* Point-in-Time

## 22.3 量化模型

必须测试：

* 无前视偏差
* 无标签泄漏
* 训练测试隔离
* 成本后收益
* 滚动验证
* 不同市场状态
* 参数敏感性
* 因子相关性
* 极端行情
* 数据缺失

## 22.4 风险引擎

使用 Property-Based Testing 检验：

* 任何仓位不得绕过上限
* 数据过期时不能批准实时交易
* 账户回撤触发时必须降级
* 期权最大损失不得超限
* 模型一致看多不能绕过风险否决

## 22.5 LLM

测试必须使用 Mock，不在 CI 中调用真实 GPT。

测试内容：

* JSON Schema 合法
* 拒绝虚构缺失数据
* 证据 ID 存在
* 缓存命中
* Token 预算
* 超时降级
* 云模型不可用时模板报告仍可生成

## 22.6 GUI

Playwright 测试：

* 应用启动
* 搜索股票
* 四视角切换
* 横向对比
* 数据过期提示
* 手动同步
* 设置保存
* 错误提示
* 导出报告
* 深色主题
* Windows 窗口尺寸适配

## 22.7 Windows 打包

必须在干净 Windows 环境测试：

* 安装
* 首次启动
* Sidecar 启动
* 无 Python 环境启动
* 数据目录创建
* API Key 保存
* 更新数据
* 退出
* 再次启动
* 升级
* 卸载

---

# 23. 模型评估

## 23.1 华尔街模型

* 情景概率校准
* 财报方向命中
* 催化判断
* 逻辑失效识别速度
* 最大不利波动
* 不同估值状态表现

## 23.2 量化模型

* IC
* Rank IC
* 扣费后收益
* Sharpe
* Sortino
* 最大回撤
* 换手率
* 信号衰减
* 样本外稳定性
* 概率校准

## 23.3 游资模型

* 主线识别准确率
* 龙头识别准确率
* 突破成功率
* 假突破率
* 1/3/5日延续收益
* 退潮识别速度
* 时间止损效果

## 23.4 融合模型

* 是否优于三个单模型
* 是否降低回撤
* 是否减少错误交易
* 模型分歧时是否自动降仓
* 风险否决避免的亏损
* 扣费后收益
* 实盘或模拟与回测偏差

---

# 24. 里程碑

## M0：项目基线

交付：

* 仓库目录
* AGENTS.md
* README
* PROJECT_TASKBOOK
* 架构文档
* ADR
* Python/React/Tauri 空项目
* CI
* Mock 数据
* 基础测试

退出条件：

* Linux 开发环境可启动
* Windows CI 可构建空安装包
* 前端可以连接 Mock 后端
* 测试全部通过

## M1：本地存储与数据契约

交付：

* SQLite
* DuckDB
* Parquet
* Repository Interface
* 数据模型
* Snapshot Schema
* 数据迁移
* 备份恢复

退出条件：

* 可以写入并查询 Mock 日线、分钟线、公告和新闻
* 数据带完整时间和来源字段
* 可生成分析快照

## M2：首批数据适配器

优先：

* SEC
* FRED
* Tradier 或 Mock 券商行情
* Moomoo/Longbridge 中至少一个
* Tiingo/Massive 中至少一个

退出条件：

* 可增量同步美股与港股观察池
* 可处理限流和断线
* GUI 显示数据状态

## M3：因子和特征系统

交付：

* 技术因子
* 基本面因子
* 宏观状态
* 新闻事件结构
* 期权基础指标
* 板块宽度
* 主题和龙头评分

退出条件：

* 给定快照可以稳定生成 Feature Set
* Feature Set 可版本化
* 无重复指标计权

## M4：三套独立模型 V0

交付：

* 华尔街规则模型
* 量化基线模型
* 游资状态机模型
* 公共 ModelResult Schema
* 独立报告

退出条件：

* 三个模型独立运行
* 互相看不到结论
* 都能生成完整交易计划
* 都能输出 NO_TRADE

## M5：融合与风险引擎

交付：

* Fusion Packet
* 融合规则模型
* 分歧处理
* 全局风险引擎
* 风险许可状态

退出条件：

* 不同周期正确对齐
* 模型分歧可解释
* 风险引擎可否决所有模型
* 结果可复现

## M6：完整 GUI

交付：

* Dashboard
* 股票分析
* 板块分析
* 四视角标签
* 横向对比
* 数据中心
* 模型中心
* 设置
* Token 面板

退出条件：

* 美观、简洁、可用
* 不需要命令行完成日常操作
* 缓存页面快速打开
* 错误和数据过期明显显示

## M7：回测与模拟交易

交付：

* 回测实验室
* 三模型独立回测
* 融合回测
* 模拟账户
* 交易日志
* 绩效归因

退出条件：

* 结果可复现
* 含交易成本
* 无已知前视偏差
* 可比较四套模型

## M8：Windows 正式打包

交付：

* Windows setup.exe
* 自动启动 Sidecar
* 配置向导
* 备份恢复
* 安装和升级文档
* Windows 冒烟测试

退出条件：

* 干净 Windows 机器无需安装 Python 即可运行
* 核心功能可用
* 卸载不破坏用户数据
* 所有关键测试通过

---

# 25. Definition of Done

项目第一版正式完成必须同时满足：

1. Windows 安装包可用。
2. 用户不需要命令行启动。
3. 用户不需要安装 Python。
4. 默认不依赖 Docker。
5. 美股和港股观察池可以增量更新。
6. 股票和板块均可分析。
7. 三套独立模型可以单独查看。
8. 融合模型可以单独查看。
9. 四套模型均输出完整交易计划。
10. 风险引擎可否决交易。
11. 所有结论具有数据截止时间。
12. 所有结论具有证据和模型版本。
13. 缓存报告打开时不调用 GPT。
14. 云模型关闭后核心功能仍可运行。
15. 数据过期时明确显示。
16. 无已知前视偏差。
17. 回测包含成本和滑点。
18. API Key 不出现在日志或前端。
19. 关键模块具有自动化测试。
20. 可备份和恢复本地数据。
21. 可导出 Markdown、HTML 或 PDF 报告。
22. 不存在 LLM 自动实盘下单路径。

---

# 26. Codex 工作流程

Codex 每次接受任务后必须按以下步骤执行。

## 第一步：阅读

先阅读：

```text
AGENTS.md
PROJECT_TASKBOOK.md
docs/architecture.md
docs/roadmap.md
docs/decision-log.md
相关ADR
```

## 第二步：检查现状

必须检查：

* 当前目录结构
* 已有代码
* 已有测试
* 当前分支
* 未提交修改
* 相关配置

不得假设某模块不存在或已经完成。

## 第三步：制定小范围计划

任务必须拆成可验证步骤。

禁止一次性无审查地实现多个大里程碑。

## 第四步：实现

要求：

* 类型完整
* 错误处理完整
* 不吞异常
* 不硬编码密钥
* 不硬编码用户目录
* 不绕过 Repository
* 不绕过 Snapshot
* 不绕过风险引擎

## 第五步：测试

运行所有与修改有关的：

* 单元测试
* 集成测试
* 类型检查
* Lint
* 构建
* 冒烟测试

不得声称“应该可以运行”。

必须明确报告实际运行了什么。

## 第六步：更新文档

任何涉及以下内容的修改必须更新文档：

* 架构
* 数据库
* API
* Provider
* Schema
* 模型
* 风险
* 部署
* 配置

## 第七步：报告

每次完成后输出：

```text
完成内容
修改文件
设计决定
运行测试
测试结果
已知限制
下一步
```

---

# 27. Codex 禁止行为

Codex 不得：

* 虚构不存在的 API
* 虚构供应商字段
* 伪造测试通过
* 使用未来数据回测
* 隐藏数据缺失
* 把新闻情绪当成事实
* 把 Short Sale Volume 当成 Short Interest
* 把盘后价格当成正式收盘价
* 把延迟行情标记为实时行情
* 让不同独立模型互相读取结果
* 让融合模型绕过风险引擎
* 将 API Key 写入仓库
* 在无迁移的情况下直接修改数据库
* 在 MVP 中实现自动实盘
* 未经说明扩大任务范围
* 大范围重构与当前任务无关代码
* 删除用户数据或历史实验
* 用自由文本替代关键结构化输出

---

# 28. 首次执行任务

Codex 首次接收本任务书后，不要立即实现全部项目。

先完成 M0，并交付：

1. 推荐目录树。
2. `AGENTS.md`。
3. `docs/architecture.md`。
4. `docs/data-model.md`。
5. `docs/model-design.md`。
6. `docs/gui-spec.md`。
7. `docs/deployment-windows.md`。
8. ADR：

   * 本地存储选择
   * Tauri + Sidecar
   * 模型隔离
   * Fusion Packet
   * LLM Token 策略
9. 可运行的 FastAPI 健康检查。
10. 可运行的 React/Tauri 空壳界面。
11. 前后端通信演示。
12. Mock 股票分析页面。
13. Linux 开发命令。
14. Windows CI 构建骨架。
15. 测试结果。

在 M0 验收前，不进入 M1。
