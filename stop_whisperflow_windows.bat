@echo off
REM ============================================================================
REM WhisperFlow - Stop para Windows
REM Detiene servidor + GUI
REM ============================================================================

echo.
echo Deteniendo WhisperFlow...
echo.

wsl -d Ubuntu bash -c "cd /mnt/d/Dev/whisperflow-cloud && ./whisperflow_simple.sh stop"

echo.
echo WhisperFlow detenido
pause
