@echo off
REM ============================================================================
REM WhisperFlow - Launcher para Windows
REM Ejecuta esto para iniciar TODO (servidor + GUI)
REM ============================================================================

echo.
echo ========================================
echo   WhisperFlow - Inicio Automatico
echo ========================================
echo.

REM Verificar Docker
echo [1/3] Verificando Docker...
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>NUL | find /I /N "Docker Desktop.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo.
    echo  Docker Desktop NO esta corriendo
    echo  Iniciando Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo.
    echo  Esperando 20 segundos para que Docker inicie...
    timeout /t 20 /nobreak
)
echo  Docker OK

REM Iniciar servidor
echo.
echo [2/3] Iniciando servidor...
wsl -d Ubuntu bash -c "cd /mnt/d/Dev/whisperflow-cloud && ./whisperflow_simple.sh start"

REM Iniciar GUI (ahora VISIBLE, no en background)
echo.
echo [3/3] Iniciando GUI...
echo  La ventana de WhisperFlow va a aparecer...
echo.
start "WhisperFlow GUI" wsl -d Ubuntu bash -c "cd /mnt/d/Dev/whisperflow-cloud && ./start_gui.sh"

echo.
echo ========================================
echo   WhisperFlow LISTO
echo ========================================
echo.
echo  La ventana de dictado debe estar visible
echo  Click GRABAR cuando necesites dictar
echo.
echo  Para detener:
echo    Ejecuta: stop_whisperflow_windows.bat
echo.
pause
