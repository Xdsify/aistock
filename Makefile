.PHONY: help up down build logs clean ps db-reset test

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## 启动所有服务
	docker compose up -d

down: ## 停止所有服务
	docker compose down

build: ## 构建所有镜像
	docker compose build

logs: ## 查看所有日志
	docker compose logs -f

logs-%: ## 查看指定服务日志 (如: make logs-data-service)
	docker compose logs -f $*

ps: ## 查看运行状态
	docker compose ps

clean: ## 清理所有容器和数据
	docker compose down -v
	rm -rf pgdata redisdata

db-reset: ## 重置数据库
	docker compose down postgres
	docker compose up -d postgres
	@echo "等待PostgreSQL启动..."
	@sleep 5
	docker compose exec postgres psql -U aistock -d aistock -c "SELECT 1"

test: ## 运行所有测试
	@echo "运行数据服务测试..."
	cd services/data-service && pytest tests/ -v
	@echo "运行AI服务测试..."
	cd services/ai-service && pytest tests/ -v
	@echo "运行策略引擎测试..."
	cd services/strategy-engine && pytest tests/ -v
	@echo "运行风控测试..."
	cd services/risk-manager && pytest tests/ -v
	@echo "运行Go测试..."
	cd services/execution-engine && go test ./...
	cd services/api-gateway && go test ./...

dev: ## 开发模式 (仅启动基础设施)
	docker compose up -d postgres redis
	@echo "数据库: localhost:5432"
	@echo "Redis: localhost:6379"
	@echo "然后手动启动各服务: cd services/<name> && uvicorn src.main:app --reload"

frontend: ## 启动前端开发服务器
	cd frontend && npm run dev

init: ## 首次安装
	cp -n .env.example .env || true
	@echo "请编辑 .env 填入API密钥和券商账号"
	docker compose build
	docker compose up -d postgres redis
	@echo "等待数据库就绪..."
	@sleep 10
	@echo "初始化完成! 运行 'make up' 启动全部服务"
