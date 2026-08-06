# AIStock 使用教程

AI全自动炒股系统（A股半自动化量化交易）使用指南。更新于 2026-08-05。

## 一、系统是什么

```
React前端(3000) ←→ Go API网关(8080 REST + 8081 WebSocket) ←→ Redis Pub/Sub ←→ 微服务
```
- **数据服务** 采集 A股行情 (AKShare，K线 eastmoney 失败自动回退 sina)
- **策略引擎** 跑技术策略生成信号，AI 增强，风控过滤；支持新建自定义策略
- **AI 服务** 调 DeepSeek 做情绪/形态/信号审核
- **执行引擎** 订阅信号，模拟下单，T+1 持仓追踪，权益/成交记账
- **风控管理** 事前/事中/事后风控、熔断
- **前端** 仪表盘/信号/持仓/手动交易/策略/AI选股/涨停分析/个股详情/风控/设置

> ⚠️ 当前为**模拟交易**模式（broker-bridge 未接真实券商），初始模拟资金 50 万。

---

## 二、启动系统

### 方式 A：Docker 一键启动（推荐）

**双击 `start.bat`**：自动拉起 Docker Desktop → 启动全部服务 → 等待就绪 → 自动打开前端 `http://localhost:3000`。
首次运行需拉取镜像，可能要等几分钟。

命令行手动启动（等价于 start.bat 做的）：

```bash
# 1. 配置环境变量
copy .env.example .env
#    编辑 .env：DEEPSEEK_API_KEY、JWT_SECRET、ADMIN_PASSWORD 等

# 2. 启动全部业务服务
docker compose up -d postgres redis data-service strategy-engine ai-service risk-manager execution-engine broker-bridge api-gateway frontend

# 3. 可选：监控栈 (Prometheus/Grafana/exporter)
docker compose up -d prometheus grafana postgres-exporter redis-exporter

# 停止
docker compose down          # 保留数据
docker compose down -v       # 连数据一起清掉
```

### 方式 B：开发模式（Windows，本地热重载）
> ⚠️ 需要本机安装 Go 1.22+（API 网关是 Go 服务），且需把网关代理地址改成 localhost。
> 旧脚本保留在 `start.bat.local`，供参考。

日常使用请直接双击 `start.bat`（方式 A）。

### 登录
打开 `http://localhost:3000` → 账号 **admin** / 密码 **admin123**（生产务必改 `ADMIN_PASSWORD`）。

---

## 三、配置 (.env)

| 变量 | 说明 | 默认 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 密钥，不配则 AI 用模拟回退 | - |
| `DEEPSEEK_BASE_URL` | DeepSeek 接口地址 | https://api.deepseek.com |
| `DB_PASSWORD` / `JWT_SECRET` | 数据库密码 / JWT 签名密钥 | 请修改 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 登录账号 | admin / admin123 |
| `ENFORCE_TRADING_HOURS` | true=闭市拒绝下单；false=随时可下单(便于测试) | true |
| `TUSHARE_TOKEN` | Tushare 备用数据源 token（可选） | - |
| `BROKER_ACCOUNT/PASSWORD` | 券商账号（模拟模式用不到） | - |
| 风控参数 `MAX_SINGLE_STOCK_PCT` 等 | 也可在「设置」页改（写 Redis 运行期生效） | 见 .env.example |

> API 密钥、券商账号等通过 `.env` 配置，改后需重启对应服务。设置页只提供运行期可调的风控/AI 参数。

---

## 四、前端页面

### 仪表盘
总资产 / 累计盈亏 / 可用资金 / 持仓市值 + **真实权益曲线**（执行引擎记账）+ 市场情绪 + 实时行情条 + 最近信号。
右上角「紧急停止」一键熔断所有交易。

### 手动交易
输入股票代码（自动带出名称/实时价）→ 选买入/卖出 → 价格/数量 → 下单（模拟成交）。
- 数量填 0 = 按仓位比例自动算
- **闭市会被拒绝**（受 `ENFORCE_TRADING_HOURS` 控制），非交易时段有提示横幅

### 持仓管理
持仓列表（含股票名称、T+1 锁定）、可直接卖出。
- 现价：有实时行情显示实时价；行情不可用时标注「以买入价计」
- 点股票名 → 跳个股详情页

### 信号面板
策略生成的信号（带 AI 置信度/强度），可「批准」（下单）或「拒绝」（写入抑制，策略不再重发）。
- 刷新页面会拉取历史，信号不丢

### 策略管理
- 内置 4 策略（双均线/RSI/放量突破/布林带）+ 用户自定义策略（带「自定义」徽标）
- 启动/暂停 → 真正激活（后台循环加载）
- **新建策略** → 弹窗写 `on_bar` 代码（Python），立即生效可回测/激活
- 回测 → 对指定股票跑历史数据（收益率/胜率/盈亏比/回撤）
- 测试信号 → 单根K线快速触发

### AI 选股
DeepSeek 扫全市场选股 + 市场判断 + 操作策略；每只结果有「买入」按钮（一键下单）。

### 涨停分析
类似同花顺：按日期列出**全部涨停 / 首板 / 连板**，显示连板数、封板资金、首次封板时间、炸板次数、所属行业。
行情不可用时显示示例数据（黄色标注）。点股票名 → 个股详情。

### 个股详情
在**任何页面点股票名/代码**都会跳到 `/stock/代码`：
- K线蜡烛图（日K/周K/月K）+ 成交量
- 区间统计（涨跌幅/最高/最低/成交量/收盘）
- 现价（实时行情不可用时显示最新收盘价）

### 风控监控
熔断状态、日亏损/仓位/回撤指标，可重置熔断。

### 系统设置
保存风控/AI 参数（写 Redis，运行期生效，无需重启）。

---

## 五、端口一览

| 端口 | 服务 |
|------|------|
| 3000 | 前端 |
| 8080 / 8081 | API 网关 REST / WebSocket |
| 8001 | 数据服务 |
| 8002 | 策略引擎 |
| 8003 | AI 服务 |
| 8004 | 风控管理 |
| 9001 | 执行引擎 |
| 9090 / 3001 | Prometheus / Grafana |
| 5432 / 6379 | PostgreSQL / Redis |

各服务健康检查 `http://localhost:<端口>/health`，监控指标 `/metrics`。

---

## 六、完整交易链路

1. **行情**：数据服务采集（AKShare）→ 写 Redis → 发布 `market:quote`/`market:sentiment`。验证：
   ```bash
   curl http://localhost:8080/api/data/market/sentiment
   ```
2. **策略**：激活策略 → 后台循环喂K线 → 生成信号 → AI增强 → 风控 → 发布 `signal:new`
3. **执行**：信号面板批准（或 `requires_confirmation=false` 自动执行）→ 执行引擎模拟下单 → 持仓更新
4. **统计**：权益曲线、胜率/盈亏比由执行引擎记账，仪表盘展示

> ⚠️ 行情依赖 AKShare 网络（eastmoney / sina）。当前机器到部分 eastmoney 接口仍被断，K线会自动回退 sina 源。

---

## 七、数据源说明

- **主源 AKShare**：实时行情/情绪/涨停池用 eastmoney 接口
- **K线回退 sina**：eastmoney K线接口不可达时自动用 `stock_zh_a_daily`（sina），首次拉取较慢但会缓存 6 小时
- **Tushare**：可选备用，`.env` 填 `TUSHARE_TOKEN` 即可，不填不影响

---

## 八、自定义策略（新建策略）

1. 策略管理 →「新建策略」
2. 填策略名（英文/下划线）、描述
3. 写 `on_bar` 函数体（Python），可用：
   - `self.bars`：历史K线列表
   - `self.am.sma/ema/rsi/macd/bollinger_bands/vol_ratio`：指标
   - `self.pos`：当前持仓状态（0=空仓）
   - `bar.open/high/low/close/volume`：当前K线
   - 返回 `self.generate_signal(Action.BUY/SELL, bar, 强度, 理由)` 或 `None`
4. 点「插入示例」参考模板，创建后立即出现在列表，可激活/回测
5. 已创建的策略持久化在 `strategies/<名字>.py`，重启不丢

完整模板见 `strategies/example_ma_cross.py`。

---

## 九、故障排查

| 现象 | 处理 |
|------|------|
| 双击 start.bat 没反应/报错 | 确认 Docker Desktop 已安装并启动；start.bat 是 Docker 一键启动，不再依赖本机 Go/Python |
| 前端打不开 / 登录不了 | `docker compose ps` 看 frontend/gateway 是否 Up；确认账号密码 |
| 页面数据空 | 多数是**行情网络不通**（AKShare）；`docker logs aistock-data` 看采集日志 |
| K线加载慢 | 首次约 6 秒（sina 源），之后秒开（Redis 缓存）；长时间不加载看 `docker logs aistock-data` |
| 闭市还能下单 | `.env` 里 `ENFORCE_TRADING_HOURS` 是否被设成 false |
| 保存设置没反应 | 确认网关在 8080；设置页只保存风控/AI参数 |
| Docker 拉镜像失败 | 国内网络用 `docker.m.daocloud.io` 直拉后 `docker tag` 本地化，或配 registry-mirror |
| 想重置一切 | `docker compose down -v`（注意会清掉模拟账户数据） |

---

## 十、已知限制

- **模拟交易**：未接真实券商，broker-bridge 为模拟模式
- **实时行情不稳定**：当前网络到部分 eastmoney 接口被断，实时价/情绪可能为空，K线靠 sina 兜底
- **JWT 单管理员**：登录账号由 `ADMIN_USERNAME/PASSWORD` 环境变量控制，无多用户体系
- **权益曲线**：需要模拟账户有成交后才有点
- **策略代码**：新建策略执行用户提供的 Python 代码，仅适合本机/可信使用
