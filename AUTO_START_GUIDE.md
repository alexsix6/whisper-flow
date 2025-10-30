# WhisperFlow - Guía de Automatización Completa

## 🎯 Problema Resuelto

Ya NO necesitas ejecutar comandos manualmente. Todo está automatizado.

---

## 📋 Scripts Disponibles

### 1. **`whisperflow_simple.sh`** - Launcher Principal ⭐
Todo-en-uno: Inicia/Detiene/Status

```bash
# Iniciar servidor
./whisperflow_simple.sh start

# Detener todo
./whisperflow_simple.sh stop

# Ver estado
./whisperflow_simple.sh status

# Ver logs
./whisperflow_simple.sh logs

# Iniciar GUI
./whisperflow_simple.sh gui
```

### 2. **`start_server.sh`** - Solo Servidor
Inicia SOLO Docker (sin GUI)

```bash
./start_server.sh
```

### 3. **`start_gui.sh`** - Solo GUI
Inicia SOLO GUI (requiere servidor corriendo)

```bash
./start_gui.sh
```

### 4. **`stop_whisperflow.sh`** - Detener Todo
Detiene servidor + GUI

```bash
./stop_whisperflow.sh
```

---

## 🚀 Flujo de Trabajo Típico

### Opción A - Manual (Máximo Control)

**1. Iniciar servidor una vez:**
```bash
./whisperflow_simple.sh start
```

**2. Usar GUI cuando necesites:**
```bash
./start_gui.sh
# ... dictar ...
# Ctrl+C para cerrar GUI
```

**3. Al terminar el día:**
```bash
./whisperflow_simple.sh stop
```

### Opción B - Todo Automático

**Inicio del día:**
```bash
./whisperflow_simple.sh start
./start_gui.sh &  # GUI en background
```

**Fin del día:**
```bash
./whisperflow_simple.sh stop
```

---

## 🔧 Auto-Start en Windows (OPCIONAL)

Si quieres que WhisperFlow arranque AUTOMÁTICAMENTE cuando inicies Windows:

### Paso 1: Crear Script Windows

Crear archivo: `D:\Dev\whisperflow-cloud\start_whisperflow.bat`

```batch
@echo off
REM Auto-start WhisperFlow en Windows

echo Iniciando WhisperFlow...

REM Iniciar Docker Desktop si no está corriendo
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>NUL | find /I /N "Docker Desktop.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo Iniciando Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    timeout /t 20 /nobreak
)

REM Iniciar servidor via WSL
wsl -d Ubuntu -e /mnt/d/Dev/whisperflow-cloud/whisperflow_simple.sh start

echo WhisperFlow iniciado!
echo Para GUI: wsl -d Ubuntu -e /mnt/d/Dev/whisperflow-cloud/start_gui.sh
pause
```

### Paso 2: Configurar Task Scheduler

**2.1 Abrir Task Scheduler:**
- Windows Key + R → `taskschd.msc`

**2.2 Crear Task:**
- Click: "Create Basic Task..."
- Name: "WhisperFlow Auto-Start"
- Trigger: "When I log on"
- Action: "Start a program"
  - Program: `D:\Dev\whisperflow-cloud\start_whisperflow.bat`
  - Start in: `D:\Dev\whisperflow-cloud`

**2.3 Configurar:**
- Properties → "Run whether user is logged on or not"
- ✅ "Run with highest privileges"
- Conditions → ✅ "Wake the computer to run this task"

**2.4 Test:**
- Right click task → "Run"
- Verificar que servidor inicia

---

## 🎯 Solución Problema "Sesión que No se Pudo Cerrar"

### ¿Qué Pasó?

Cuando cerraste la terminal con X, el proceso `dictation_gui.py` quedó orphan (corriendo en background).

### Solución Automática (Ya Aplicada)

Los scripts nuevos verifican y limpian procesos orphan automáticamente:

```bash
# Verificar si hay procesos orphan
pgrep -f "dictation_gui.py"

# Si hay, matar
pkill -f "dictation_gui.py"
```

Esto está integrado en `whisperflow_simple.sh stop`

### Solución Manual (Si Necesario)

```bash
# 1. Ver procesos
ps aux | grep dictation_gui

# 2. Matar por PID
kill <PID>

# 3. O forzar todo
pkill -9 -f dictation_gui.py
```

---

## 🔍 Verificaciones Automáticas

Cada vez que ejecutas `whisperflow_simple.sh start`, verifica:

1. ✅ Docker está corriendo
2. ✅ Container se inicia correctamente
3. ✅ Health check pasa (servidor funcional)
4. ✅ Limpia procesos orphan anteriores

Si algo falla, ves mensaje de error CLARO con instrucciones.

---

## 📊 Comandos Útiles

```bash
# Ver estado completo
./whisperflow_simple.sh status

# Logs en tiempo real
./whisperflow_simple.sh logs

# Reiniciar servidor (si hay problemas)
./whisperflow_simple.sh stop
./whisperflow_simple.sh start

# Ver procesos Python activos
ps aux | grep python

# Ver uso Docker
docker ps
docker stats whisperflow-server
```

---

## ⚙️ Configuración Docker Auto-Restart

El container YA tiene auto-restart configurado en `docker-compose.yml`:

```yaml
services:
  whisperflow-server:
    restart: unless-stopped  # Se reinicia automáticamente si falla
```

Esto significa:
- Si el container crashea → Se reinicia automáticamente
- Si apagas Docker → Container NO se reinicia (intencional)
- Si reinicias PC → Container se reinicia al abrir Docker Desktop

---

## 🎉 Resumen

**ANTES:**
```bash
# Comandos manuales cada vez
cd /mnt/d/Dev/whisperflow-cloud
docker-compose up -d
source .venv/bin/activate
python dictation_gui.py
# ... problemas al cerrar ...
```

**AHORA:**
```bash
# Un comando para todo
./whisperflow_simple.sh start
./start_gui.sh  # Cuando necesites GUI
# Ctrl+C cierra limpiamente
```

**OPCIONAL (Auto-start Windows):**
- Task Scheduler ejecuta al login
- Todo inicia automáticamente
- Solo ejecutas `start_gui.sh` cuando dictarás

---

## 🆘 Troubleshooting

### "Docker no está corriendo"
→ Inicia Docker Desktop manualmente

### "Servidor no responde"
```bash
./whisperflow_simple.sh logs
docker logs whisperflow-server
```

### "GUI no se cierra con Ctrl+C"
```bash
# Forzar cierre
pkill -f dictation_gui.py
```

### "Procesos orphan"
```bash
./whisperflow_simple.sh stop  # Limpia todo automáticamente
```

---

**Última actualización:** 2025-10-19
**Proyecto:** WhisperFlow v1.0.0 - OpenAI API Migration
