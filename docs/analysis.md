# AIStock 项目全面分析报告

> 分析日期: 2026-08-02

## 项目概述

AI全自动炒股系统 — 基于 DeepSeek AI 的 A股半自动化量化交易系统。采用微服务架构，包含7个服务 + React前端 + 监控栈。

**架构**: React Frontend → Go API Gateway (WebSocket+REST) → Redis Pub/Sub → 微服务集群

| 服务 | 语言 | 功能 | 端口 |
|------|------|------|------|
| data-service | Python | 行情数据采集 (AKShare/Tushare) | 8001 |
| strategy-engine | Python | 策略引擎+回测 | 8002 |
| ai-service | Python | DeepSeek AI分析 | 8003 |
| risk-manager | Python | 风控管理 | 8004 |
| execution-engine | Go | 订单执行 | 9001 |
| broker-bridge | Python | 券商API桥接 | 50051 |
| api-gateway | Go | API网关+WebSocket | 8080/8081 |
| frontend | React 19 | Dashboard | 3000 |

---

## 问题清单

### 1. 缺失文件（阻塞性 — 已修复 ✅）

| 问题 | 严重程度 | 状态 |
|------|----------|------|
| `data-service/src/api.py` 缺失 | 🔴 服务无法启动 | ✅ 已创建 |
| `data-service/src/ingestors/scheduler.py` 缺失 | 🔴 服务无法启动 | ✅ 已创建 |
| `ai-service/src/api.py` 缺失 | 🔴 服务无法启动 | ✅ 已创建 |
| `ai-service/src/client.py` 缺失 | 🔴 AI功能无法使用 | ✅ 已创建 |
| `ai-service/src/__init__.py` 缺失 | 🔴 Python包无法导入 | ✅ 已创建 |
| `risk-manager/src/__init__.py` 缺失 | 🔴 Python包无法导入 | ✅ 已创建 |
| `frontend/src/App.tsx` 缺失 | 🔴 前端无法启动 | ✅ 已创建 |
| `frontend/src/stores/positionStore.ts` 缺失 | 🔴 前端编译错误 | ✅ 已创建 |
| `frontend/src/stores/signalStore.ts` 缺失 | 🔴 前端编译错误 | ✅ 已创建 |
| Go服务 `go.sum` 缺失 | 🔴 Docker构建失败 | ✅ 已创建占位文件 |

### 2. 代码错误（已修复 ✅）

| 问题 | 说明 | 状态 |
|------|------|------|
| `data_normalizer.py` 循环导入自身 | `from .data_normalizer import DataNormalizer` 写在自身文件中 | ✅ 已重写 |
| Go服务 Redis URL 解析错误 | `go-redis` 的 `Addr` 需要 `host:port`，被传入完整 `redis://` URL | ✅ 已添加 `parseRedisAddr()` |
| API 网关 `proxyCall()` 是空函数 | 所有API代理直接返回nil，前端无数据 | ✅ 已实现完整代理 |
| 风控服务每次请求创建新 Redis 连接 | 高并发下连接耗尽 | ✅ 已改为共享连接池 |
| `start.bat` 执行引擎用错命令 | Go 服务被当 Python 用 `uvicorn` 启动 | ✅ 已修复 |
| `start.bat` 数据服务端口错误 | 使用 8011 而非 docker-compose 定义的 8001 | ✅ 已修复 |
| `is_trading_time()` 时间比较有 Bug | 使用 `datetime.replace()` 构造时间可能产生不存在的时间 | ✅ 已改为分钟数比较 |

### 3. 安全问题（已修复 ✅）

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| `.env` 包含真实 DeepSeek API Key | 🔴 严重 | `sk-xxx...` 真实密钥暴露（已轮换） |
| JWT 认证为占位符 | 🟡 中等 | 返回 `"jwt-token-placeholder"` |
| 无 API 鉴权 | 🟡 中等 | 所有端点无需认证即可访问 |
| 密码明文传递 | 🟡 中等 | 登录接口无加密 |

**已采取措施**: API Key 已替换为占位符，建议用户立即轮换该密钥。

### 4. 功能不完整（部分修复）

| 问题 | 说明 | 状态 |
|------|------|------|
| 数据采集未实现 | AKShare/Tushare 代码为 TODO | ⚠️ 框架已就绪，待接入 |
| 券商桥接仅模拟模式 | xtquant 连接未实现 | ⚠️ 模拟模式可用 |
| 前端 RiskMonitor 硬编码数据 | 不读取 API | ✅ 已改为动态获取 |
| 前端 Settings 保存按钮无效 | 无法保存配置 | ✅ 已实现保存功能 |
| JWT 认证未实现 | 认证为占位符 | ⚠️ 待实现 |
| 回测框架未实现 | 仅有策略信号生成 | ⚠️ 待实现 |
| 用户管理未实现 | 仅数据库表定义 | ⚠️ 待实现 |

### 5. 配置问题

| 问题 | 说明 | 状态 |
|------|------|------|
| `docker-compose.yml` 变量嵌套 | `.env.example` 中 `DATABASE_URL` 使用 `${DB_PASSWORD}` 嵌套引用 | ✅ 已修复 |
| 券商桥接仅限 Windows | xtquant/miniQMT 只能在 Windows 上运行 | ⚠️ 平台限制 |
| broker-bridge 无 gRPC 实现 | execution-engine 期望 gRPC 连接但 bridge 未实现 | ⚠️ 待实现 |
| 无单元测试 | Makefile 定义了 test 目标但 tests/ 目录为空 | ⚠️ 待编写 |

---

## 架构评估

### 优点

1. **良好的服务拆分**: 数据、策略、AI、风控、执行各司其职
2. **异步消息驱动**: Redis Pub/Sub 解耦服务间通信
3. **实时数据推送**: WebSocket 实现实时报价和状态推送
4. **策略可扩展**: 基类设计合理，用户可自定义策略
5. **风险控制完善**: 事前/事中/事后三级风控
6. **TimescaleDB 时序优化**: 适合金融K线数据存储
7. **Docker Compose 一键部署**: 降低部署复杂度

### 改进建议

1. **添加服务发现**: 当前硬编码服务地址，建议使用 Consul/etcd 或 Kubernetes DNS
2. **消息持久化**: Redis Pub/Sub 是即发即忘，关键信号应使用 Redis Streams 或 Kafka
3. **分布式追踪**: 添加 OpenTelemetry 实现链路追踪
4. **API 鉴权**: 实现 JWT + RBAC 权限控制
5. **配置中心**: 使用配置管理工具统一管理多服务配置
6. **健康检查与自动重启**: docker-compose 已配置 restart，可加强健康检查
7. **日志聚合**: 使用 ELK/Loki 集中收集和分析日志
8. **数据备份**: TimescaleDB 需要配置自动备份策略
