@echo off
REM ============================================================================
REM WhisperFlow - Configurador AUTO-START
REM Ejecuta como ADMINISTRADOR para configurar inicio automático
REM ============================================================================

echo.
echo ========================================
echo   WhisperFlow - Configuracion Auto-Start
echo ========================================
echo.

REM Verificar permisos de administrador
net session >nul 2>&1
if %errorlevel% NEQ 0 (
    echo ❌ ERROR: Necesitas ejecutar como ADMINISTRADOR
    echo.
    echo Click derecho en este archivo y selecciona:
    echo "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

echo ✅ Permisos de administrador verificados
echo.

REM Crear tarea programada
echo [1/2] Creando tarea programada...

schtasks /Create /TN "WhisperFlow-AutoStart" /TR "D:\Dev\whisperflow-cloud\INICIAR_WHISPERFLOW.bat" /SC ONLOGON /RL HIGHEST /F

if %errorlevel% EQU 0 (
    echo ✅ Tarea creada exitosamente
) else (
    echo ❌ Error creando tarea
    pause
    exit /b 1
)

echo.
echo [2/2] Configurando opciones avanzadas...

REM Configurar para ejecutar aunque el usuario no esté logueado
schtasks /Change /TN "WhisperFlow-AutoStart" /RU "%USERNAME%" /RP

echo.
echo ========================================
echo   ✅ CONFIGURACION COMPLETA
echo ========================================
echo.
echo WhisperFlow ahora se iniciara automaticamente cuando:
echo  - Inicies sesion en Windows
echo  - Enciendas tu computadora
echo.
echo El SERVIDOR iniciara automaticamente (Docker)
echo La GUI la abres cuando necesites con: ABRIR_WHISPERFLOW.bat
echo.
echo Para DESACTIVAR auto-start:
echo  1. Abre "Programador de tareas" (taskschd.msc)
echo  2. Busca "WhisperFlow-AutoStart"
echo  3. Click derecho → Deshabilitar o Eliminar
echo.
pause
