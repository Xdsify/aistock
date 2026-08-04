# AI全自动炒股系统

基于 **DeepSeek AI** 的 A股半自动化量化交易系统。

## 架构

```
React前端 ←→ Go API网关(WebSocket+REST) ←→ Redis Pub/Sub ←→ 微服务集群
                                                     ↓
    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    │ 数据服务  │ 策略引擎  │ AI服务   │ 执行引擎  │ 风控管理  │
    │(Python)  │(Python)  │(Python)  │(Go)     │(Python)  │
    │AKShare   │vnpy/     │DeepSeek  │订单状态机 │熔断/止损  │
    │Tushare   │自研      │API       │T+1追踪   │仓位限制  │
    └──────────┴──────────┴──────────┴──────────┴──────────┘
                           ↓
                   ┌──────────────┐
                   │ 券商桥(Python) │
                   │ xtquant/gRPC  │
                   └──────┬───────┘
                          ↓
                   ┌──────────────┐
                   │ 华泰miniQMT   │
                   │ (Windows)    │
                   └──────────────┘
```

## 快速开始

> 📖 完整使用教程见 [docs/usage.md](docs/usage.md)（含启动方式、前端各页面说明、故障排查、如何添加策略）

```bash
# 1. 配置环境
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key 和券商信息

# 2. 启动基础设施
make dev

# 3. 启动全部服务
make up

# 4. 访问前端
open http://localhost:3000
```

## 核心功能

- 📊 **行情数据**: AKShare全A股实时行情 + 历史K线
- 🧠 **AI决策**: DeepSeek驱动的情绪分析、形态识别、新闻解读
- 📈 **策略引擎**: 多重技术分析策略，含回测框架
- 🛡️ **风控管理**: T+1锁定、仓位限制、多级熔断
- 🖥️ **实时Dashboard**: 盈亏监控、信号面板、策略管理
- ⚡ **WebSocket推送**: 实时报价、订单状态、风险告警
- 🏦 **券商对接**: 华泰xtquant/miniQMT (模拟交易模式可用)

## 技术栈

| 层 | 技术 |
|----|------|
| 策略/AI | Python + DeepSeek API |
| 实时执行 | Go + goroutines |
| 前端 | React 19 + TypeScript + Tailwind |
| 数据库 | TimescaleDB (PostgreSQL) |
| 缓存/消息 | Redis |
| 部署 | Docker Compose |
| 监控 | Prometheus + Grafana |

## 项目结构

```
aistock/
├── services/           # 微服务
│   ├── data-service/   # 行情数据采集
│   ├── strategy-engine/# 策略引擎+回测
│   ├── ai-service/     # DeepSeek AI分析
│   ├── execution-engine/ # Go订单执行
│   ├── broker-bridge/  # 券商API桥接
│   ├── risk-manager/   # 风控管理
│   └── api-gateway/    # API网关+WebSocket
├── frontend/           # React前端Dashboard
├── strategies/         # 用户自定义策略
├── migrations/         # 数据库迁移文件
├── monitoring/         # Prometheus+Grafana
└── docker-compose.yml  # 容器编排
```

## 免责声明

⚠️ **该系统仅供学习和研究使用。**
- 股票交易有风险，AI决策可能产生错误判断
- 历史回测表现不代表未来收益
- 使用本系统产生的任何盈亏由用户自行承担
- 请遵守相关法律法规，特别是程序化交易报备要求
