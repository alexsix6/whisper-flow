# WhisperFlow - Troubleshooting Audio en WSL2

## ✅ Problema RESUELTO: "Procesando..." Infinito

**Síntoma:** GUI stuck en "Procesando..." sin recibir transcripción

**Causa raíz:** Backend no arrancaba (faltaba torch) → GUI no podía conectar

**Solución:** Migración a OpenAI API completada
- ✅ Build optimizado: 5m48s (vs. 48 min)
- ✅ Imagen 1.58GB (vs. 9.91GB)
- ✅ Transcripción ultra-rápida: 2-5 segundos
- ✅ Container funcional: `docker logs whisperflow-server`

---

## 🎙️ Problema NUEVO: Audio Capture en WSL2

### Síntoma
- GUI graba AUDIO DEL SISTEMA (YouTube, videos) en vez del micrófono
- Errores ALSA: "Unanticipated host error -9999"
- Transcripciones incorrectas: "Subtítulos realizados por la comunidad..."

### Causa Raíz
1. **PyAudio usaba device DEFAULT (loopback)**
   - Device 1 = "default" captura audio del sistema (monitor/loopback)
   - Device 0 = "pulse" es PulseAudio directo (micrófono real)

2. **Chunk size muy pequeño (1024 bytes)**
   - OpenAI rechaza: "Audio file is too short. Minimum audio length is 0.1 seconds"
   - Genera demasiadas llamadas API

### Solución Aplicada

#### 1. Forzar Device "pulse" (index 0)
```python
# ANTES (dictation_gui.py línea 206):
self.stream = self.audio.open(
    format=pyaudio.paInt16,
    input=True,
    # ❌ NO especificaba input_device_index → usaba default (loopback)
)

# DESPUÉS (dictation_gui.py línea 236):
self.stream = self.audio.open(
    format=pyaudio.paInt16,
    input=True,
    input_device_index=0,  # ✅ Fuerza "pulse" (micrófono real)
)
```

#### 2. Aumentar Chunk Size (1024 → 4096)
```python
# ANTES:
self.chunk_size = 1024  # Muy pequeño - genera chunks de <0.1s

# DESPUÉS:
self.chunk_size = 4096  # Optimal para OpenAI API (0.25s @ 16kHz)
```

#### 3. Mejor Logging
- Log de dispositivo al inicio
- Contador de bytes/chunks enviados
- Confirmación: NO hay límite de duración

---

## 📋 Cómo Usar la GUI Optimizada

### Ejecución Normal
```bash
cd /mnt/d/Dev/whisperflow-cloud
source .venv/bin/activate
python dictation_gui.py
```

**Output esperado:**
```
🎙️  Configuración de Audio:
   - Sample Rate: 16000 Hz
   - Chunk Size: 4096 bytes
   - Input Device: 0
   - Device Name: pulse
   - Max Input Channels: 32
✅ Conectado al servidor
```

### Cambiar Device de Audio (Si Necesario)

**Opción A - Variable de Entorno:**
```bash
WHISPERFLOW_INPUT_DEVICE=1 python dictation_gui.py
```

**Opción B - Listar Devices Primero:**
```bash
python list_audio_devices.py
```

Output mostrará:
```
Device 0: pulse (INPUT + OUTPUT)
Device 1: default (INPUT + OUTPUT) [DEFAULT INPUT] [DEFAULT OUTPUT]
```

Si "pulse" no funciona, prueba "default" (device 1):
```bash
WHISPERFLOW_INPUT_DEVICE=1 python dictation_gui.py
```

---

## 🔍 Diagnóstico de Problemas

### 1. Verificar Servidor Funciona
```bash
curl http://localhost:8181/health
```

**Expected:**
```json
{"status":"healthy","model_status":"openai_ready"}
```

### 2. Verificar Container Logs
```bash
docker logs whisperflow-server --tail 50
```

**Buscar:**
- ✅ "✅ Cliente de OpenAI inicializado correctamente"
- ✅ "✅ Modo OpenAI activado"
- ❌ "ERROR" o stack traces

### 3. Verificar Captura de Audio
Al grabar, la consola debe mostrar:
```
🎙️  Abriendo stream de audio (device 0)...
✅ Stream de audio abierto correctamente
🎙️  Iniciando captura de audio...
📊 Audio: 10 chunks (40.0 KB) en 2.5s
📊 Audio: 20 chunks (80.0 KB) en 5.0s
✅ Captura completa: 25 chunks (100.0 KB) en 6.2s
```

**Si ves:**
- `❌ Error capturando audio` → Prueba otro device
- `⚠️ WebSocket cerrado` → Servidor no responde

### 4. Verificar Transcripciones
```bash
docker logs whisperflow-server --tail 100 | grep "Transcripción"
```

**Expected:**
```
INFO:root:✅ Transcripción async completada: 214 caracteres
```

**Si ves:**
```
ERROR:root:❌ Error en transcripción async OpenAI: Audio file is too short
```
→ Habla más tiempo (>1 segundo) o verifica chunk_size=4096

---

## ⚙️ Configuración Avanzada

### Cambiar Sample Rate
Edita `dictation_gui.py` línea 31:
```python
self.sample_rate = 16000  # OpenAI recomienda 16kHz
# Alternativas: 44100, 48000 (si 16000 da errores ALSA)
```

### Suprimir Warnings ALSA
```bash
export PULSE_LATENCY_MSEC=30
python dictation_gui.py 2>/dev/null  # Oculta stderr
```

### Verificar PulseAudio WSL2
```bash
echo $PULSE_SERVER
# Expected: unix:/mnt/wslg/PulseServer

ps aux | grep pulseaudio
# Si no corre: sudo service pulseaudio start
```

---

## ✅ Confirmación: NO Hay Límites de Duración

**Código (dictation_gui.py líneas 263-265):**
```python
def capture_audio(self):
    """
    NO HAY LÍMITE DE DURACIÓN - El loop corre mientras is_recording=True
    Soporta grabaciones infinitamente largas (solo limitado por memoria/red)
    """
```

**Evidencia:**
- El `while` loop corre indefinidamente (línea 273)
- Solo se detiene cuando usuario presiona DETENER
- Logs muestran `chunks_sent` incrementando sin límite

**Test:**
1. Presiona GRABAR
2. Habla por 30+ segundos
3. Verás logs cada 10 chunks → Confirma captura continua
4. Presiona DETENER cuando termines

---

## 🎯 Cambios Aplicados - Resumen

### dictation_gui.py

| Línea | Cambio | Razón |
|-------|--------|-------|
| 9 | `import os` | Para leer WHISPERFLOW_INPUT_DEVICE |
| 30 | `chunk_size = 4096` | Evitar "Audio too short" |
| 38 | `input_device_index = 0` | Fuerza "pulse" (micrófono) |
| 44-61 | `_log_audio_config()` | Diagnóstico al inicio |
| 236 | `input_device_index=X` | CRÍTICO: Especifica device |
| 263-302 | Better logging | Contador bytes/chunks/tiempo |

### Nuevos Archivos

- `list_audio_devices.py` - Diagnóstico de devices disponibles
- `test_websocket_openai.py` - Test E2E sin depender de micrófono
- `TROUBLESHOOTING_AUDIO.md` - Esta guía
- `dictation_gui.py.backup` - Backup original

---

## 📞 Soporte

**Si el problema persiste:**

1. Ejecuta diagnóstico completo:
```bash
python list_audio_devices.py > audio_devices.txt
docker logs whisperflow-server > server_logs.txt
```

2. Prueba test automatizado:
```bash
python test_websocket_openai.py
```

3. Verifica requirements locales:
```bash
source .venv/bin/activate
pip list | grep -E "pyaudio|websockets|openai"
```

**Última actualización:** 2025-10-19 (WhisperFlow v1.0.0 - OpenAI API Migration)
