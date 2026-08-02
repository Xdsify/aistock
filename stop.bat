@echo off
echo ========================================
echo   Killing all AI Trading processes...
echo ========================================

echo Killing uvicorn processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8011 :8002 :8003 :8004 :9001 :3000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)

echo Killing node processes (frontend)...
taskkill /F /IM node.exe 2>nul

echo.
echo ========================================
echo   Done. All processes killed.
echo ========================================
pause
