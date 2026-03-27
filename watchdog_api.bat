@echo off
cd /d "%~dp0"
echo Iniciando watchdog da API...

:loop
echo [%date% %time%] Liberando porta 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [%date% %time%] Iniciando uvicorn...
uvicorn api.main:app --port 8000
echo [%date% %time%] API parou (codigo: %errorlevel%). Reiniciando em 5s...
timeout /t 5 /nobreak >nul
goto loop
