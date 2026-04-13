@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo  BACKUP DO BANCO - %date% %time%
echo ============================================
echo.

:: ── Lê variáveis do .env ─────────────────────────────────────────────────────
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "key=%%A"
    set "val=%%B"
    if "!key!"=="SUPABASE_URL"         set "SUPABASE_URL=!val!"
    if "!key!"=="SUPABASE_SERVICE_KEY" set "SUPABASE_SERVICE_KEY=!val!"
)

if "%SUPABASE_URL%"=="" (
    echo [ERRO] SUPABASE_URL nao encontrado no .env
    pause & exit /b 1
)
if "%SUPABASE_SERVICE_KEY%"=="" (
    echo [ERRO] SUPABASE_SERVICE_KEY nao encontrado no .env
    pause & exit /b 1
)

:: ── Extrai o project ref da URL (https://XXXX.supabase.co) ───────────────────
for /f "tokens=3 delims=/" %%H in ("%SUPABASE_URL%") do set "SUPABASE_HOST=%%H"
set "DB_HOST=db.%SUPABASE_HOST%"

:: ── Define o arquivo de saída com timestamp ──────────────────────────────────
set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "OUTFILE=backups\backup_%TIMESTAMP%.sql"

if not exist backups mkdir backups

echo Host:    %DB_HOST%
echo Arquivo: %OUTFILE%
echo.

:: ── Executa pg_dump ───────────────────────────────────────────────────────────
set "PGPASSWORD=%SUPABASE_SERVICE_KEY%"
pg_dump ^
    --host=%DB_HOST% ^
    --port=5432 ^
    --username=postgres ^
    --dbname=postgres ^
    --schema=public ^
    --no-owner ^
    --no-acl ^
    --file="%OUTFILE%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Backup salvo em: %OUTFILE%
) else (
    echo.
    echo [ERRO] pg_dump falhou. Verifique se o pg_dump esta no PATH.
    echo        Instale o PostgreSQL client ou adicione ao PATH:
    echo        C:\Program Files\PostgreSQL\16\bin
)

set "PGPASSWORD="
echo.
pause
