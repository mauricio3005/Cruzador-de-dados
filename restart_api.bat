@echo off
echo Parando processo na porta 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Matando PID %%a
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo Iniciando API...
cd /d "%~dp0"
uvicorn api.main:app --reload --port 8000
c