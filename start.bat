@echo off
cd /d F:\aistock

echo ========================================
echo   AI Stock Trading - Starting...
echo ========================================

echo.
echo [1/5] Starting PostgreSQL and Redis...
docker compose up -d postgres redis
timeout /t 5 /nobreak >nul

echo [2/5] Starting Python services...
start "DataService" cmd /c "cd /d F:\aistock\services\data-service && uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload"
start "Strategy" cmd /c "cd /d F:\aistock\services\strategy-engine && set AI_SERVICE_URL=http://localhost:8003/api/ai && set RISK_SERVICE_URL=http://localhost:8004/api/risk && uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload"
start "AIService" cmd /c "cd /d F:\aistock\services\ai-service && set DEEPSEEK_API_KEY=%DEEPSEEK_API_KEY% && set DEEPSEEK_BASE_URL=https://api.deepseek.com && set REDIS_URL=redis://localhost:6379 && set DATABASE_URL=postgresql://aistock:aistock@localhost:5432/aistock && uvicorn src.main:app --host 0.0.0.0 --port 8003 --reload"
start "RiskManager" cmd /c "cd /d F:\aistock\services\risk-manager && uvicorn src.main:app --host 0.0.0.0 --port 8004 --reload"

echo [3/5] Starting execution engine...
start "ExecutionEngine" cmd /c "cd /d F:\aistock\services\execution-engine && python main.py"

echo [4/5] Starting API gateway...
start "APIGateway" cmd /c "cd /d F:\aistock\services\api-gateway && go run cmd/server/main.go"

echo [5/5] Starting frontend...
start "Frontend" cmd /c "cd /d F:\aistock\frontend && npx vite --host 0.0.0.0 --port 3000"

timeout /t 8 /nobreak >nul

echo.
echo ========================================
echo   Frontend:  http://localhost:3000
echo   Gateway:   http://localhost:8080
echo   Data API:  http://localhost:8001/docs
echo   Strategy:  http://localhost:8002/docs
echo   AI Service: http://localhost:8003/docs
echo   Risk:      http://localhost:8004/docs
echo   Execution: http://localhost:9001
echo ========================================
echo   Close all cmd windows to stop
echo ========================================

start http://localhost:3000
