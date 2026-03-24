@echo off
title WhisperFlow Cloud Client
echo ============================================
echo   WhisperFlow Cloud - Windows Client
echo ============================================
echo.

REM Auth token for Cloud Run server
set WHISPERFLOW_AUTH_TOKEN=lgDbESsclQypi1pY53KE4GED9S8-NZTrlPTmC_psuqE

REM Server URL (Cloud Run)
set WHISPERFLOW_SERVER=wss://whisperflow-server-518312107738.us-central1.run.app/ws

echo Server: %WHISPERFLOW_SERVER%
echo.

cd /d "%~dp0"
python -c "exec(open('whisperflow_client.py').read())"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Install dependencies:
    echo   pip install sounddevice numpy websockets pyperclip
echo   This client no longer depends on soundcard.
    echo.
    pause
)
