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

REM Run with Python from PATH
python whisperflow_client.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start. Make sure Python and dependencies are installed:
    echo   pip install PyAudioWPatch websockets pyperclip
    echo.
    pause
)
