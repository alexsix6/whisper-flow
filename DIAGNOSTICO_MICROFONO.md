# 🔍 Diagnóstico Completo: Micrófono y Hotkeys

## 🎯 Tu Situación

**Problema reportado:**
- Presionas Ctrl+Space en la terminal o en Claude Desktop
- No ves ninguna señal de que esté grabando
- No estás seguro si debes ver algo o simplemente empezar a dictar

---

## 📊 Estado Actual del Sistema

### ✅ Lo que SÍ está funcionando:

1. **Servidor WhisperFlow:** ✅ HEALTHY
   ```
   Docker container corriendo en puerto 8181
   Modelo Whisper (small.pt) cargado correctamente
   ```

2. **Cliente de Dictado:** ✅ RUNNING (PID: 58412)
   ```
   Proceso Python corriendo en background
   Conectado al servidor WebSocket
   ```

3. **Audio WSL2:** ✅ CONFIGURADO
   ```
   DISPLAY=:0
   PULSE_SERVER=unix:/mnt/wslg/PulseServer
   PulseServer socket existe y es accesible
   ```

4. **Dispositivos de Audio:** ✅ DETECTADOS
   ```
   Dispositivo 0: pulse (32 canales entrada)
   Dispositivo 1: default (32 canales entrada)
   ```

### ⚠️ Lo que PUEDE estar fallando:

**Problema potencial:** Captura de hotkeys globales (Ctrl+Space)

**Razón:**
En WSL2, `pynput` (la librería que captura hotkeys) puede tener problemas para:
- Capturar teclas globales cuando la aplicación corre en background
- Acceder al sistema X11/Wayland sin una sesión GUI activa
- Interceptar hotkeys fuera de la terminal WSL

---

## 🧪 Diagnóstico Paso a Paso

He creado **2 scripts de prueba** para diagnosticar el problema:

### **Test 1: Verificar Captura de Hotkeys**

**Script:** `test_hotkey.py`

**Propósito:** Verificar si `pynput` puede capturar Ctrl+Space en tu sistema

**Cómo ejecutar:**
```bash
cd /mnt/d/Dev/whisperflow-cloud
source .venv/bin/activate
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"
python test_hotkey.py
```

**Qué esperar:**
1. El script dirá "Esperando hotkeys..."
2. Presiona **Ctrl+Space**
3. Si funciona, verás: "✅ ¡ÉXITO! Ctrl+Space detectado correctamente"
4. Presiona **ESC** para salir

**Interpretación:**
- ✅ **Si funciona:** pynput está OK, el problema está en otra parte
- ❌ **Si NO funciona:** pynput no puede capturar hotkeys en tu WSL2

---

### **Test 2: Verificar Micrófono**

**Script:** `test_microphone.py`

**Propósito:** Grabar 5 segundos de audio para verificar que el micrófono Cougar funciona

**Cómo ejecutar:**
```bash
cd /mnt/d/Dev/whisperflow-cloud
source .venv/bin/activate
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"
python test_microphone.py
```

**Qué esperar:**
1. Lista los dispositivos de audio disponibles
2. Dice "Grabando 5 segundos de audio..."
3. **HABLA CERCA DEL MICRÓFONO** durante 5 segundos
4. Crea archivo `test_microphone_recording.wav`
5. Puedes reproducirlo en Windows para verificar que grabó tu voz

**Interpretación:**
- ✅ **Si graba audio:** Tu micrófono Cougar funciona correctamente
- ❌ **Si no graba o da error:** Problema de configuración de audio

---

## 🔍 Posibles Problemas y Soluciones

### **Escenario A: Hotkeys NO funcionan (pynput falla)**

**Síntoma:**
- `test_hotkey.py` no detecta Ctrl+Space
- O solo detecta las teclas cuando presionas dentro de la terminal WSL

**Causa:**
pynput requiere acceso al servidor X11/Wayland activo. En WSL2 background, esto puede fallar.

**Soluciones:**

#### **Solución 1: Usar Aplicación GUI (Recomendada)**
En lugar de hotkey global, crear una ventana pequeña con botones:
- Botón "🔴 Grabar" → Inicia grabación
- Botón "⏹️ Detener" → Para y transcribe
- Ventana siempre visible en pantalla

#### **Solución 2: Usar Hotkey de Windows (PowerShell)**
Crear script PowerShell en Windows que:
- Captura hotkey global en Windows
- Llama a WhisperFlow via HTTP cuando se presiona
- Más confiable que pynput en WSL2

#### **Solución 3: Usar Terminal Interactiva**
Ejecutar cliente en modo interactivo:
```bash
python universal_dictation_client.py
```
- Presionar Enter para grabar
- Presionar Enter de nuevo para transcribir
- Más simple pero requiere terminal abierta

---

### **Escenario B: Hotkeys SÍ funcionan pero no se ve nada**

**Síntoma:**
- `test_hotkey.py` detecta Ctrl+Space correctamente
- Pero en uso real no ves indicación de grabación

**Causa:**
El cliente corre en background sin output visible.

**Solución:**
Modificar `universal_dictation_client.py` para:
- Mostrar notificación en pantalla cuando graba
- Tocar sonido de "beep" al iniciar/parar grabación
- Crear archivo temporal con indicador visual

---

### **Escenario C: Micrófono NO graba audio**

**Síntoma:**
- `test_microphone.py` da error o graba silencio
- Archivo `.wav` creado pero sin audio

**Causa:**
- Micrófono no configurado como default en Windows
- Permisos de audio no configurados en WSL2
- Micrófono USB no reconocido por WSL2

**Soluciones:**

#### **Paso 1: Configurar micrófono en Windows**
```
Windows Settings → Sound → Input
→ Seleccionar "Micrófono Cougar" como default
→ Probar micrófono (debería mostrar barras de nivel)
```

#### **Paso 2: Verificar permisos WSL2**
```bash
# En WSL2
pactl list sources short

# Deberías ver tu micrófono Cougar listado
```

#### **Paso 3: Reiniciar audio en WSL2**
```bash
pulseaudio --kill
pulseaudio --start
```

---

## 🚀 Instrucciones para Diagnóstico

### **PASO 1: Ejecuta Test de Hotkeys**

```bash
cd /mnt/d/Dev/whisperflow-cloud
source .venv/bin/activate
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"
python test_hotkey.py
```

**Presiona Ctrl+Space varias veces**
- ¿Detecta las teclas? → Anota el resultado

**Presiona ESC para salir**

---

### **PASO 2: Ejecuta Test de Micrófono**

```bash
python test_microphone.py
```

**Habla cerca del micrófono durante 5 segundos**
- ¿Se creó el archivo `test_microphone_recording.wav`?
- ¿Puedes reproducirlo y escuchar tu voz?

---

### **PASO 3: Reporta Resultados**

**Escenario 1:**
- ✅ Hotkeys funcionan
- ✅ Micrófono graba
- **Conclusión:** Todo funciona, solo falta feedback visual
- **Solución:** Agregar indicadores visuales/sonoros

**Escenario 2:**
- ❌ Hotkeys NO funcionan
- ✅ Micrófono graba
- **Conclusión:** Problema con pynput en WSL2
- **Solución:** Implementar alternativa (GUI o PowerShell)

**Escenario 3:**
- ✅ Hotkeys funcionan
- ❌ Micrófono NO graba
- **Conclusión:** Problema de configuración de audio
- **Solución:** Configurar micrófono en Windows + WSL2

**Escenario 4:**
- ❌ Hotkeys NO funcionan
- ❌ Micrófono NO graba
- **Conclusión:** Problemas múltiples
- **Solución:** Reconfigurar audio + implementar alternativa a hotkeys

---

## 🎯 Cómo DEBERÍA funcionar el dictado (cuando todo funciona)

### **Flujo esperado:**

1. **WhisperFlow corriendo:**
   ```bash
   whisperflow status
   # ✅ Server health: HEALTHY
   # ✅ Client Status: RUNNING
   ```

2. **Presionas Ctrl+Space (primera vez):**
   - **Internamente:** Cliente empieza a capturar audio del micrófono
   - **Visible:** Debería ver mensaje en logs o indicador visual (NO implementado aún)
   - **Audio:** Micrófono empieza a grabar

3. **Hablas cerca del micrófono:**
   - Ejemplo: "Hola mundo, esto es una prueba"
   - El audio se está capturando en chunks

4. **Presionas Ctrl+Space (segunda vez):**
   - **Internamente:** Cliente para grabación y envía audio al servidor
   - **Servidor:** Whisper transcribe y traduce a español
   - **Cliente:** Recibe texto traducido

5. **Texto aparece automáticamente:**
   - Cliente simula Ctrl+V (pega desde clipboard)
   - El texto aparece en la aplicación activa
   - Resultado: "Hola mundo, esto es una prueba"

### **Problema actual:**
- Paso 2 y 4 pueden no estar funcionando (hotkeys no detectados)
- O funcionan pero no hay feedback visual

---

## 📞 Qué Necesito de Ti

Por favor ejecuta los 2 tests y reporta:

1. **Test de hotkeys:**
   - ¿Detectó Ctrl+Space? (Sí/No)
   - ¿Qué mensajes viste en pantalla?

2. **Test de micrófono:**
   - ¿Se creó el archivo .wav? (Sí/No)
   - ¿Puedes escuchar tu voz al reproducirlo? (Sí/No)

Con esta información, puedo:
- Identificar el problema exacto
- Implementar la solución correcta
- Ya sea: agregar feedback visual, o implementar método alternativo

---

**Ejecuta los tests ahora y dime qué resultados obtienes** 🔬
