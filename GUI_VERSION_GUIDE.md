# 🎨 WhisperFlow con Interfaz Gráfica (GUI)

## 🔍 Por Qué Necesitas la Versión GUI

### Problema Identificado:
- ❌ **Hot keys Ctrl+Space NO funcionan** en tu WSL2
- Los hotkeys globales requieren acceso al sistema X11/Wayland que no está disponible en background
- La librería `pynput` no puede capturar teclas fuera de la terminal

### Solución Implementada:
- ✅ **Interfaz Gráfica (GUI) con botones**
- Ventana pequeña y simple con tkinter
- Botones grandes: "🔴 GRABAR" y "⏹️ DETENER"
- MÁS confiable que hotkeys en WSL2

---

## 🚀 Cómo Iniciar la Versión GUI

### Opción 1: Modo Manual (Recomendado para Probar)

```bash
cd /mnt/d/Dev/whisperflow-cloud

# 1. Detener versión anterior (si está corriendo)
whisperflow stop

# 2. Iniciar servidor Docker
docker-compose up -d

# 3. Esperar a que servidor esté listo
sleep 10

# 4. Iniciar GUI
source .venv/bin/activate
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"
python dictation_gui.py
```

**Deberías ver una ventana aparecer** con:
- Título: "🎤 WhisperFlow Dictado"
- Botón grande rojo: "🔴 GRABAR"
- Estado de conexión

---

### Opción 2: Actualizar Scripts Automáticos (Para Uso Permanente)

**Paso 1: Actualizar el comando `whisperflow`**

```bash
cd /mnt/d/Dev/whisperflow-cloud
sudo cp whisperflow_no_systemd.sh /usr/local/bin/whisperflow
sudo chmod +x /usr/local/bin/whisperflow
```

**Paso 2: Actualizar el auto-start script**

```bash
# Reemplazar el archivo de startup
cp ~/.whisperflow_startup.sh ~/.whisperflow_startup.sh.backup

# Editar el archivo
nano ~/.whisperflow_startup.sh
```

**Cambiar las líneas 36-45:**
```bash
# ANTES:
# if ! pgrep -f "universal_dictation_client.py" > /dev/null; then
#     nohup .venv/bin/python universal_dictation_client.py > /tmp/whisperflow-client.log 2>&1 &

# DESPUÉS:
if ! pgrep -f "dictation_gui.py" > /dev/null; then
    nohup .venv/bin/python dictation_gui.py > /tmp/whisperflow-client.log 2>&1 &
```

**Guardar:** `Ctrl+X`, luego `Y`, luego `Enter`

**Paso 3: Probar**

```bash
whisperflow start
# Debería aparecer la ventana GUI
```

---

## 🎯 Cómo Usar la Interfaz GUI

### Flujo de Uso:

1. **Inicia WhisperFlow:**
   ```bash
   whisperflow start
   # O manualmente: python dictation_gui.py
   ```

2. **Verifica conexión:**
   - La ventana mostrará: "✅ Conectado al servidor"
   - El botón "GRABAR" se activará (dejará de estar gris)

3. **Abre la aplicación donde quieres dictar:**
   - Navegador (Google Docs, Gmail, ChatGPT, etc.)
   - Editor de texto (VSCode, Notepad, gedit)
   - Chat (Discord, Slack)
   - Cualquier campo de texto

4. **Haz clic en el botón "🔴 GRABAR":**
   - El botón cambiará a "⏹️ DETENER" (verde)
   - Verás "🔴 GRABANDO..." abajo del botón

5. **Habla cerca del micrófono:**
   - Di algo como: "Hello world, this is a test"
   - Puedes ver transcripción parcial mientras hablas

6. **Haz clic en "⏹️ DETENER":**
   - Verás "⏳ Procesando..."
   - El servidor Whisper transcribirá y traducirá
   - El texto se copiará automáticamente al clipboard

7. **Pega el texto:**
   - El texto está en el clipboard
   - Haz clic en la aplicación objetivo
   - Presiona `Ctrl+V` para pegar
   - Verás tu texto traducido a español

---

## 🌍 Ejemplo de Uso Completo

### Escenario: Dictar en Google Docs

**Paso 1: Inicia WhisperFlow**
```bash
whisperflow start
```

**Paso 2: Abre Google Docs**
- Ve a https://docs.google.com
- Crea un documento nuevo
- Haz clic en el documento

**Paso 3: Usa la GUI**
1. Ventana GUI debería estar visible
2. Estado: "✅ Conectado al servidor"
3. Haz clic en "🔴 GRABAR"
4. Di en inglés: *"Hello everyone, this is a test of the dictation system using Whisper Flow"*
5. Haz clic en "⏹️ DETENER"
6. Espera 2-3 segundos (verás "⏳ Procesando...")
7. Verás: "📋 Presiona Ctrl+V para pegar"
8. En Google Docs, presiona `Ctrl+V`

**Resultado esperado:**
```
Hola a todos, esta es una prueba del sistema de dictado usando Whisper Flow
```

---

## 📊 Ventajas de la Versión GUI

| Feature | Versión Hotkey | Versión GUI |
|---------|---------------|-------------|
| **Funciona en WSL2** | ❌ NO | ✅ SÍ |
| **Feedback Visual** | ❌ NO | ✅ SÍ (botón cambia color) |
| **Fácil de Usar** | ⚠️ Requiere recordar hotkey | ✅ Botones claros |
| **Estado Visible** | ❌ NO | ✅ Muestra conexión/grabación |
| **Transcripción Parcial** | ❌ NO | ✅ Se muestra en tiempo real |
| **Confiabilidad** | ❌ Baja en WSL2 | ✅ Alta |

---

## ⚠️ Limitaciones Conocidas

### 1. **Auto-Paste NO Funciona**
**Problema:** `pynput.keyboard` no puede simular `Ctrl+V` en WSL2

**Solución Actual:**
- El texto se copia al clipboard automáticamente
- Tú presionas `Ctrl+V` manualmente para pegar

**Solución Futura Posible:**
- Crear script PowerShell en Windows que simule Ctrl+V
- Llamarlo via WSL2

### 2. **Ventana Debe Estar Visible**
**Problema:** Si cierras la ventana GUI, el cliente se cierra

**Solución:**
- Minimiza la ventana (no la cierres)
- O déjala visible en un costado de la pantalla

### 3. **Primera Grabación Puede Ser Lenta**
**Razón:** Modelo Whisper se inicializa en primera transcripción

**Solución:**
- Segunda grabación en adelante es más rápida
- Espera pacientemente la primera vez (~5-10 segundos)

---

## 🐛 Troubleshooting

### Problema: La ventana no aparece

**Diagnóstico:**
```bash
# Ver logs
cat /tmp/whisperflow-client.log | tail -50

# Ver si el proceso está corriendo
ps aux | grep dictation_gui.py
```

**Posibles causas:**
1. `DISPLAY` no configurado → Exportar: `export DISPLAY=:0`
2. tkinter no instalado → Instalar: `sudo apt-get install python3-tk`
3. Error de Python → Revisar logs arriba

---

### Problema: Botón "GRABAR" está gris (deshabilitado)

**Causa:** No está conectado al servidor

**Solución:**
```bash
# Verificar servidor
docker ps | grep whisperflow-server
curl http://localhost:8181/health

# Reiniciar si es necesario
whisperflow restart
```

---

### Problema: Graba pero no transcribe

**Diagnóstico:**
```bash
# Ver logs del servidor
docker logs whisperflow-server | tail -50
```

**Posibles causas:**
1. Servidor no recibe audio → Verificar WebSocket conectado
2. Modelo Whisper no cargado → Ver logs servidor
3. Error en transcripción → Ver logs servidor

---

## 📝 Comandos Útiles

```bash
# Iniciar GUI manualmente
python dictation_gui.py

# Ver estado
whisperflow status

# Ver logs en tiempo real
whisperflow logs

# Reiniciar todo
whisperflow restart

# Detener
whisperflow stop
```

---

## 🎬 Video Tutorial (Texto)

```
1. Terminal: whisperflow start
   → Ventana GUI aparece

2. Ventana GUI muestra: "✅ Conectado al servidor"

3. Abre navegador → Google Docs

4. Click en documento

5. Click en ventana GUI → Botón "🔴 GRABAR"
   → Botón se vuelve verde "⏹️ DETENER"

6. Habla cerca del micrófono: "Hello world"

7. Click en "⏹️ DETENER"
   → Muestra "⏳ Procesando..."
   → Luego "📋 Presiona Ctrl+V para pegar"

8. Vuelve a Google Docs → Ctrl+V

9. Resultado: "Hola mundo"
```

---

## 💡 Mejoras Futuras Posibles

1. **Auto-Paste vía PowerShell Script**
   - Script Windows captura clipboard
   - Simula Ctrl+V automáticamente
   - Más seamless experience

2. **Hotkeys Alternativos**
   - Usar F12 o F11 en lugar de Ctrl+Space
   - Crear script PowerShell para capturar hotkey en Windows

3. **Icono en System Tray**
   - Aplicación corre en background
   - Icono en barra de tareas
   - Click derecho para grabar/detener

4. **Notificaciones de Sistema**
   - Toast notifications cuando graba
   - Sonido "beep" al iniciar/parar

---

**¡Tu sistema de dictado con GUI está listo!** 🎉

**Siguiente paso:** Ejecuta `whisperflow start` o `python dictation_gui.py` para probarlo.
