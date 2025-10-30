@echo off
REM ============================================================================
REM WhisperFlow - Launcher SIMPLIFICADO
REM Este script mantiene la terminal abierta y la GUI visible
REM ============================================================================

echo.
echo ========================================
echo   WhisperFlow - Inicio
echo ========================================
echo.

REM Verificar Docker
echo [1/2] Verificando Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Docker Desktop NO esta corriendo
    echo  Iniciando Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo.
    echo  Esperando 30 segundos para que Docker inicie...
    timeout /t 30 /nobreak
)
echo  Docker OK

REM Iniciar servidor
echo.
echo [2/2] Iniciando servidor...
wsl -d Ubuntu bash -c "cd /mnt/d/Dev/whisperflow-cloud && docker-compose up -d"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Servidor LISTO
echo ========================================
echo.
echo Ahora ejecuta en WSL (copia y pega):
echo.
echo   cd /mnt/d/Dev/whisperflow-cloud
echo   ./start_gui.sh
echo.
echo O simplemente abre Ubuntu y ejecuta esos comandos.
echo.
pause
