@echo off
title WhisperFlow Cloud Client
echo ============================================
echo   WhisperFlow Cloud v3.1
echo ============================================
echo.

REM --- Configuration ---
set WHISPERFLOW_AUTH_TOKEN=lgDbESsclQypi1pY53KE4GED9S8-NZTrlPTmC_psuqE
set WHISPERFLOW_SERVER=wss://whisperflow-server-518312107738.us-central1.run.app/ws

REM System Audio: use VB-CABLE (device 35, WDM-KS) when available
REM Override with: set WHISPERFLOW_SYSTEM_DEVICE=34 (for Stereo Mix)
if not defined WHISPERFLOW_SYSTEM_DEVICE set WHISPERFLOW_SYSTEM_DEVICE=35

echo Server: %WHISPERFLOW_SERVER%
echo System Audio Device: %WHISPERFLOW_SYSTEM_DEVICE%
echo.

cd /d "%~dp0"
python -c "exec(open('whisperflow_client.py').read())"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Install dependencies:
    echo   pip install sounddevice numpy websockets pyperclip customtkinter
    echo.
    pause
)
