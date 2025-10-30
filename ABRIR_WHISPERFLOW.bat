@echo off
REM ============================================================================
REM WhisperFlow - Lanzador SIMPLE de GUI
REM Doble click para abrir la ventana de WhisperFlow
REM ============================================================================

REM Abrir Ubuntu y ejecutar start_gui.sh
wt.exe -w 0 wsl -d Ubuntu bash -c "cd /mnt/d/Dev/whisperflow-cloud && ./start_gui.sh; exec bash"

REM Nota: Si no tienes Windows Terminal instalado, usa esta alternativa:
REM wsl -d Ubuntu bash -c "cd /mnt/d/Dev/whisperflow-cloud && ./start_gui.sh"
