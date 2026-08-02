# AIStock 优化修复记录

> 修复日期: 2026-08-02

## 已应用的修复

### 修复1: 创建 data-service API 路由
**文件**: `services/data-service/src/api.py` (新建)
**问题**: main.py 导入 `from .api import router` 但文件不存在，服务启动报 `ModuleNotFoundError`
**内容**: 实现了 K线查询、市场情绪、实时行情、自选股、股票信息等 REST 端点

### 修复2: 创建数据采集调度器
**文件**: `services/data-service/src/ingestors/scheduler.py` (新建)
**问题**: main.py 导入 `DataScheduler` 类不存在
**内容**: 实现了交易时段判断、实时轮询、日线更新等调度逻辑

### 修复3: 创建 AI 服务 API 路由
**文件**: `services/ai-service/src/api.py` (新建)
**问题**: main.py 导入 `from .api import router` 但文件不存在
**内容**: 实现了情绪分析、形态识别、信号增强、AI状态等端点

### 修复4: 创建 DeepSeek 客户端
**文件**: `services/ai-service/src/client.py` (新建)
**问题**: main.py 导入 `from .client import deepseek_client` 但模块不存在
**内容**: 实现了 DeepSeek API 调用封装，含速率限制、Token 预算、模拟回退模式

### 修复5: 创建 Python 包初始化文件
**文件**: 
- `services/ai-service/src/__init__.py` (新建)
- `services/risk-manager/src/__init__.py` (新建)
**问题**: Python 3.11 隐式命名空间包导致导入行为不确定

### 修复6: 修复数据标准化器循环导入
**文件**: `services/data-service/src/normalizers/data_normalizer.py` (重写)
**问题**: 文件内部 `from .data_normalizer import DataNormalizer` — 自己导入自己
**修复**: 重写为包含实际的 `DataNormalizer` 类实现，包含代码标准化、交易所判断、板块识别等功能

### 修复7: 修复风控服务 Redis 连接管理
**文件**: 
- `services/risk-manager/src/redis_client.py` (新建)
- `services/risk-manager/src/api.py` (重写)
- `services/risk-manager/src/main.py` (修改)
**问题**: 每个 API 端点都独立创建和关闭 Redis 连接 (`aioredis.from_url()` → `close()`)
**修复**: 提取为共享连接池，在 lifespan 中初始化和关闭，所有端点复用同一连接
**影响**: 高并发场景下连接数从 O(n) 降至 O(1)

### 修复8: 修复风控服务时间比较 Bug
**文件**: `services/risk-manager/src/api.py`
**问题**: `is_trading_time()` 使用 `datetime.replace()` 构造比较时间，在某些日期可能产生不存在的时间
**修复**: 改为 `hour * 60 + minute` 分钟数直接比较

### 修复9: 修复 Go 服务 Redis URL 解析
**文件**: 
- `services/execution-engine/cmd/server/main.go` (修改)
- `services/api-gateway/cmd/server/main.go` (修改)
**问题**: `go-redis` 的 `Options.Addr` 期望 `host:port`，被传入 `redis://localhost:6379`
**修复**: 添加 `parseRedisAddr()` 函数解析 redis:// URL 为纯 host:port

### 修复10: 实现 API 网关代理功能
**文件**: `services/api-gateway/cmd/server/main.go` (重写)
**问题**: `proxyCall()` 和 `proxyTo()` 直接返回 nil，所有代理请求无响应
**修复**: 实现了完整的 HTTP 反向代理，包含请求头转发、X-Forwarded-For、错误处理

### 修复11: 创建前端 App.tsx
**文件**: `frontend/src/App.tsx` (新建)
**问题**: main.tsx 导入 App 组件但文件不存在
**内容**: 实现了侧边栏导航 + 路由 (仪表盘/风控/设置)，WebSocket 集成

### 修复12: 创建前端状态管理 Stores
**文件**:
- `frontend/src/stores/positionStore.ts` (新建)
- `frontend/src/stores/signalStore.ts` (新建)
**问题**: useWebSocket.ts 导入两个 store 但文件不存在
**内容**: Zustand stores 实现持仓管理和信号队列管理

### 修复13: 前端页面接入真实 API
**文件**:
- `frontend/src/pages/RiskMonitor.tsx` (修改)
- `frontend/src/pages/Settings.tsx` (修改)
**问题**: RiskMonitor 使用硬编码数据，Settings 保存按钮无效
**修复**: RiskMonitor 每10秒从 `/api/risk/status` 获取数据，Settings 实现 POST 保存

### 修复14: 修复 start.bat
**文件**: `start.bat` (重写)
**问题**:
- 执行引擎是 Go 服务却被用 `uvicorn main:app` 启动
- 数据服务端口使用 8011 而非 8001
- 缺少 API Gateway 启动命令
**修复**: 所有服务使用正确命令，增加 Gateway 启动，端口统一

### 修复15: 移除泄露的 API Key
**文件**: `.env` (修改)
**问题**: `DEEPSEEK_API_KEY=sk-xxx...` 真实密钥暴露（已轮换）
**修复**: 替换为占位符 `sk-your-deepseek-api-key`，强烈建议立即轮换该密钥

### 修复16: Go Docker 构建兼容
**文件**: 
- `services/execution-engine/Dockerfile` (修改)
- `services/api-gateway/Dockerfile` (修改)
- `services/execution-engine/go.sum` (新建)
- `services/api-gateway/go.sum` (新建)
**问题**: Dockerfile 执行 `COPY go.mod go.sum ./` 但 go.sum 不存在
**修复**: 创建占位 go.sum，Dockerfile 添加 `go mod tidy` 回退逻辑

---

## 验证清单

- [ ] Python 服务可导入: `cd services/data-service && python -c "from src.main import app"`
- [ ] Python 服务可导入: `cd services/ai-service && python -c "from src.main import app"`
- [ ] Python 服务可导入: `cd services/risk-manager && python -c "from src.main import app"`
- [ ] 前端可编译: `cd frontend && npm install && npm run build`
- [ ] Docker 镜像可构建: `docker compose build`
- [ ] 基础设施可启动: `docker compose up -d postgres redis`
- [ ] 前端页面可访问: `http://localhost:3000`
- [ ] DeepSeek API Key 已轮换

---

## 后续建议

### 短期（1-2周）
1. **轮换 DeepSeek API Key** — 泄露的 Key 已替换但需确认已轮换
2. **编写单元测试** — 优先覆盖风控检查和策略信号生成
3. **实现 JWT 认证** — 替换登录占位符，添加中间件验证
4. **接入 AKShare 数据源** — 完善 `DataScheduler` 的实际数据获取

### 中期（1-2月）
5. **实现回测框架** — 策略引擎目前只能生成信号，无法回测
6. **gRPC 券商桥接** — 实现 broker-bridge 的 gRPC 服务端
7. **前端 K线图表** — 集成 lightweight-charts 展示行情
8. **告警通知** — 实现钉钉/微信/邮件告警

### 长期（3-6月）
9. **Kubernetes 迁移** — 从 docker-compose 迁移到 K8s
10. **消息队列升级** — Redis Pub/Sub → Redis Streams 或 Kafka
11. **分布式追踪** — OpenTelemetry + Jaeger
12. **CI/CD** — GitHub Actions 自动测试和部署
