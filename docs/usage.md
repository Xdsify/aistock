# AIStock 使用教程

AI全自动炒股系统（A股半自动化量化交易）使用指南。

## 一、系统是什么

```
React前端 ←→ Go API网关(8080 REST + 8081 WebSocket) ←→ Redis Pub/Sub ←→ 微服务
```
- **数据服务** 采集 A股行情 (AKShare)
- **策略引擎** 跑技术策略生成信号，AI 增强，风控过滤
- **AI 服务** 调 DeepSeek 做情绪/形态/信号审核
- **执行引擎** 订阅信号，模拟/实盘下单，T+1 持仓追踪
- **风控管理** 事前/事中/事后风控、熔断
- **前端** 仪表盘/信号/持仓/策略/AI选股/风控/设置

> ⚠️ 当前为**模拟交易**模式（broker-bridge 未接真实券商），仅作学习研究。

---

## 二、启动系统

### 方式 A：Docker 部署（推荐，一次拉起全部）

```bash
# 1. 首次：配置环境变量
copy .env.example .env
#    编辑 .env：DEEPSEEK_API_KEY、JWT_SECRET 等

# 2. 启动
docker compose up -d postgres redis data-service strategy-engine ai-service risk-manager execution-engine broker-bridge api-gateway frontend

# 3. 可选：监控栈（需网络能拉取 prometheus/grafana 镜像）
docker compose up -d prometheus grafana postgres-exporter redis-exporter

# 停止
docker compose down        # 保留数据
docker compose down -v     # 连数据一起清掉
```

### 方式 B：开发模式（本地进程，改代码热重载）

Windows 双击 `start.bat`（会开多个 cmd 窗口分别跑各服务），或 `make dev` + 手动起服务。

> 开发模式用 Vite 代理直连各服务，**绕过网关鉴权**；Docker 模式统一走网关。

---

## 三、配置 (.env)

| 变量 | 说明 | 默认 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 密钥，不配则 AI 用模拟回退 | - |
| `DEEPSEEK_BASE_URL` | DeepSeek 接口地址 | https://api.deepseek.com |
| `DB_PASSWORD` / `JWT_SECRET` | 数据库密码 / JWT 签名密钥 | 请修改 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 登录账号 | admin / admin123 |
| `TUSHARE_TOKEN` | 备用数据源 token（可选） | - |
| `BROKER_ACCOUNT/PASSWORD` | 券商账号（模拟模式用不到） | - |
| 风控参数 `MAX_SINGLE_STOCK_PCT` 等 | 也可在「设置」页改（存 Redis） | 见 .env.example |

---

## 四、前端使用（http://localhost:3000）

登录：`admin` / `admin123`（生产务必改 `ADMIN_PASSWORD`）。

### 仪表盘
总资产 / 累计盈亏 / 可用资金 / 持仓市值 + 权益曲线 + 市场情绪 + 最近信号。
右上角「紧急停止」一键熔断所有交易。

### 信号面板
展示策略生成的信号，带 AI 置信度和强度。需要人工确认的信号可「批准」→ 执行引擎下单。
> 信号来自策略管道，需**行情数据在流动**才会有（见第六节）。

### 持仓管理
实时持仓、T+1 锁定标记，可直接「卖出」。

### 策略管理
- 内置 4 个策略：双均线 / RSI / 放量突破 / 布林带
- 「启动/暂停」真正激活策略（存 Redis，后台循环加载）
- 「回测」对指定股票跑历史数据，看收益率/胜率/盈亏比/回撤
- 「测试信号」用单根 K 线快速触发信号（不需要行情网络）

### AI 选股
一键让 DeepSeek 扫全市场选 5 只股票 + 市场判断 + 操作策略。
（需 DeepSeek key 且网络可达；否则返回模拟结果）

### 风控监控
熔断状态、日亏损/仓位/回撤指标，可重置熔断。

### 系统设置
保存风控/AI 参数到 Redis（运行期生效，无需重启）。

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

各服务健康检查：`http://localhost:<端口>/health`，指标：`/metrics`。

---

## 六、完整交易链路（怎么看到真正的信号）

1. **行情在流动**：数据服务盘中轮询 AKShare → 写 Redis → 发布 `market:quote`。可用下面命令验证：
   ```bash
   curl http://localhost:8080/api/data/market/sentiment   # 返回 sentiment 非空
   ```
2. **激活策略**：策略管理页点「启动」，或调 `POST /api/strategy/activate`。
3. **生成信号**：策略循环读到日线 → 触发信号 → AI 增强 → 风控 → 发布 `signal:new`。
4. **执行**：需要人工确认的信号在「信号面板」批准 → 执行引擎模拟下单 → 持仓更新。

> ⚠️ **行情依赖 AKShare 访问 eastmoney 的网络**。若当前机器到 eastmoney 被断（如系统代理未开），市场情绪/信号会一直空。修好网络或代理即可自动恢复。可以先用「策略管理 → 测试信号」和「回测」离线体验策略逻辑。

---

## 七、故障排查

| 现象 | 处理 |
|------|------|
| 前端打不开 | `docker compose ps` 看 frontend/gateway 是否 Up；等几秒重试 |
| 登录报错/401 | 确认账号密码；后端网关是否在 8080 |
| 页面数据空 | 多数是**行情网络不通**（AKShare）；`docker logs aistock-data` 看采集日志 |
| 保存设置没反应 | 确认网关在 8080（dev 模式走 Vite 代理到网关） |
| Docker 拉镜像失败 | 国内网络建议用 `docker.m.daocloud.io` 直拉后 `docker tag` 本地化；或配 registry-mirror |
| 想重置一切 | `docker compose down -v && rm -rf pgdata redisdata` |

---

## 八、添加自己的策略

1. 复制模板：`strategies/example_ma_cross.py`。
2. 实现 `on_bar()`：在 `self.bars` 里用 `self.am.sma/ema/rsi/macd...` 算指标，满足条件返回 `self.generate_signal(Action.BUY/SELL, bar, strength, reason)`，否则 `None`。
3. 把策略类注册到 `services/strategy-engine/src/strategies/examples.py` 的 `BUILTIN_STRATEGIES`。
4. 重启 strategy-engine（Docker：`docker compose restart strategy-engine`），前端「策略管理」即可见、可激活、可回测。
