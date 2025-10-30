# 🎤 Configuración de Dictado Universal para WhisperFlow

## 📋 Resumen
Este documento explica cómo configurar WhisperFlow para **dictado universal** que funcione en cualquier aplicación (Claude, ChatGPT, correo, etc.).

## 🏗️ Arquitectura Completa

```
[Hotkey Ctrl+Space] → [Cliente Universal] → [WhisperFlow Server] → [Whisper AI] → [Texto insertado automáticamente]
```

## 🔧 Instalación Paso a Paso

### 1. **Configurar el Servidor WhisperFlow**

```bash
# Navegar al directorio del proyecto
cd whisperflow-cloud

# Crear entorno virtual si no existe
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias base
pip install -r requirements.txt

# Iniciar el servidor (en una terminal separada)
./run.sh -run-server
# O manualmente: uvicorn whisperflow.fast_server:app --host 0.0.0.0 --port 8181
```

**El servidor debe estar corriendo en `http://localhost:8181`**

### 2. **Instalar Dependencias del Cliente de Dictado**

```bash
# En la misma terminal (con .venv activado)
pip install -r requirements_dictation.txt

# En Linux también instalar dependencias del sistema:
sudo apt-get update
sudo apt-get install python3-tk python3-dev portaudio19-dev

# En macOS:
# brew install python-tk portaudio

# En Windows: generalmente incluido con Python
```

### 3. **Ejecutar el Cliente de Dictado Universal**

```bash
# Asegúrate que el servidor esté corriendo primero
python universal_dictation_client.py
```

**Output esperado:**
```
🎤 Cliente de Dictado Universal iniciado
📋 Hotkey: Ctrl+Space para comenzar/parar dictado
🔌 Conectando al servidor WhisperFlow...
✅ Conectado al servidor WhisperFlow
⌨️  Escuchando hotkeys...
🔄 Presiona ESC para salir
```

## 🎯 Uso del Sistema

### **Flujo de uso típico:**

1. **Servidor corriendo** ✅ (en terminal 1: `./run.sh -run-server`)
2. **Cliente corriendo** ✅ (en terminal 2: `python universal_dictation_client.py`)
3. **Abrir cualquier aplicación** (Claude, ChatGPT, Gmail, etc.)
4. **Hacer clic en campo de texto** donde quieres dictar
5. **Presionar `Ctrl+Space`** para comenzar a grabar
6. **Hablar claramente** 🎤
7. **Presionar `Ctrl+Space` de nuevo** para parar y transcribir
8. **El texto aparece automáticamente** en la aplicación ✨

### **Teclas de acceso rápido:**
- `Ctrl+Space`: Iniciar/parar grabación
- `ESC`: Salir del cliente

## 🔍 Verificación de Funcionamiento

### **Test 1: Verificar el servidor**
```bash
# En una nueva terminal
curl http://localhost:8181/health
# Debería devolver: {"status": "healthy"}
```

### **Test 2: Test básico con el cliente existente**
```bash
# Ejecutar el cliente de prueba incluido
python tests/examples/mic_transcribe.py
```

### **Test 3: Test completo**
1. Abrir un editor de texto (gedit, notepad, etc.)
2. Ejecutar cliente universal
3. Hacer clic en el editor
4. Presionar Ctrl+Space, decir algo, presionar Ctrl+Space de nuevo
5. El texto debería aparecer automáticamente

## 🚨 Solución de Problemas

### **Error: "No conectado al servidor"**
- Verificar que el servidor esté corriendo en puerto 8181
- Verificar con: `curl http://localhost:8181/health`

### **Error: "ModuleNotFoundError: No module named 'pynput'"**
```bash
pip install pynput pyperclip websockets
```

### **Error: "Permission denied" en Linux**
```bash
# El cliente necesita permisos para capturar teclas globalmente
# Ejecutar con sudo si es necesario:
sudo python universal_dictation_client.py
```

### **El texto no se inserta**
- Verificar que la aplicación objetivo esté en foco
- Verificar que el campo de texto esté seleccionado
- Algunos campos protegidos pueden bloquear la inserción automática

### **Audio no se captura**
```bash
# Verificar dispositivos de audio disponibles
python -c "import pyaudio; p=pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

## 🎛️ Configuración Avanzada

### **Cambiar hotkey personalizada:**
Editar en `universal_dictation_client.py`:
```python
self.hotkey_combo = {Key.ctrl_l, Key.alt_l}  # Ctrl+Alt
# o
self.hotkey_combo = {Key.f12}  # Solo F12
```

### **Cambiar idioma de transcripción:**
Editar en `whisperflow/transcriber.py`:
```python
def transcribe_pcm_chunks(
    model: Whisper, chunks: list, task="transcribe", language="en", ...
```

### **Usar modelo más preciso:**
Cambiar en `whisperflow/fast_server.py`:
```python
STARTUP_MODEL_NAME = "medium.pt"  # o "large.pt" para mayor precisión
```

## 📊 Estados del Sistema

| Componente | Estado | Verificación |
|------------|--------|--------------|
| Servidor WhisperFlow | ✅ Corriendo | `curl localhost:8181/health` |
| Cliente Universal | ✅ Conectado | Mensaje "Conectado al servidor" |
| Audio | ✅ Capturando | LED de micrófono en sistema |
| Hotkeys | ✅ Escuchando | Mensaje "Escuchando hotkeys" |

## 🎯 Aplicaciones Compatibles

**Totalmente compatibles:**
- ✅ Navegadores web (Claude, ChatGPT, Gmail)
- ✅ Editores de texto (gedit, notepad, VS Code)
- ✅ Aplicaciones de office (LibreOffice, Word)
- ✅ Chat applications (Discord, Slack)

**Limitadas o bloqueadas:**
- ⚠️ Campos de contraseña (por seguridad)
- ⚠️ Aplicaciones con protección anti-automation
- ⚠️ Algunos juegos en pantalla completa

---

**¡Tu sistema de dictado universal está listo! 🎉** 