@echo off
echo ============================================
echo  DIAGNOSTICO API - %date% %time%
echo ============================================
echo.
echo [1] Processo uvicorn rodando?
tasklist | findstr /i "uvicorn python"
echo.
echo [2] O que esta na porta 8000?
netstat -ano | findstr ":8000"
echo.
echo [3] Ultimas 30 linhas do log:
powershell -command "Get-Content logs\api.log -Tail 30"
echo.
echo ============================================
pause
