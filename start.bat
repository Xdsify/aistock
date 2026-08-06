@echo off
setlocal
cd /d F:\aistock

echo ========================================
echo   AI Stock Trading - Docker Start
echo   (需要 Docker Desktop)
echo ========================================

REM --- 1. 确保 Docker Desktop 已启动 ---
tasklist /fi "imagename eq Docker Desktop.exe" 2>nul | find /i "Docker Desktop.exe" >nul
if errorlevel 1 (
    echo Docker Desktop 未运行, 正在启动...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
)

echo.
echo 等待 Docker 引擎就绪...
set tries=0
:waitloop
docker info >nul 2>&1
if not errorlevel 1 goto daemon_ok
set /a tries+=1
if %tries% geq 60 (
    echo.
    echo [错误] Docker 60 秒内未就绪, 请手动打开 Docker Desktop 后再试。
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:daemon_ok
echo Docker 引擎已就绪。
echo.

REM --- 2. 启动全部业务服务 ---
echo 启动业务服务 (首次运行需拉取镜像, 可能较慢)...
docker compose up -d postgres redis data-service strategy-engine ai-service risk-manager execution-engine broker-bridge api-gateway frontend

echo.
echo 启动监控栈 (Prometheus/Grafana, 可选)...
docker compose up -d prometheus grafana postgres-exporter redis-exporter
if errorlevel 1 echo [提示] 监控栈镜像拉取失败, 不影响业务服务, 可稍后重试: docker compose up -d prometheus grafana

REM --- 3. 等待前端就绪 ---
echo.
echo 等待服务就绪...
set tries=0
:healthloop
set /a tries+=1
if %tries% geq 90 (
    echo.
    echo [警告] 90 秒内前端未就绪, 请检查: docker compose ps
    goto done
)
curl -s -o nul -m 2 http://localhost:3000 >nul 2>&1
if not errorlevel 1 goto health_ok
timeout /t 2 /nobreak >nul
goto healthloop

:health_ok
echo 前端已就绪。

:done
echo.
echo ========================================
echo   访问地址:
echo     Frontend : http://localhost:3000
echo     登录账号 : admin / admin123
echo     Gateway  : http://localhost:8080
echo     Grafana  : http://localhost:3001
echo     API文档  : http://localhost:8001/docs
echo.
echo   停止服务 : docker compose down       (保留数据)
echo   重置全部 : docker compose down -v    (清空数据)
echo   查看状态 : docker compose ps
echo ========================================
echo.
start http://localhost:3000
pause
