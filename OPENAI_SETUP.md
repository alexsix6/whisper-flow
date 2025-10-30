# 🚀 WhisperFlow con OpenAI API - Configuración Completa

## ¿Por qué OpenAI API?

### Problema con Modelo Local:
- ❌ **MUY LENTO** para textos largos (>1 minuto de audio)
- ❌ Modelo "small" tarda **3-4 minutos** por cada minuto de audio
- ❌ Consume 100% CPU (afecta otras tareas)
- ❌ Crashea con audios muy largos

### Solución OpenAI API:
- ✅ **ULTRA RÁPIDO**: 2-5 segundos para cualquier longitud
- ✅ Alta precisión (>95%)
- ✅ NO consume recursos de tu PC
- ✅ Soporta audio hasta 25MB (~4 horas)
- ✅ Funciona con cualquier idioma

---

## 💰 Costos

**Precio:** $0.006 por minuto de audio (6 dólares por 1000 minutos)

**Estimación mensual:**
| Uso Diario | Minutos/Mes | Costo/Mes |
|------------|-------------|-----------|
| 5 min/día | 150 min | **$0.90** |
| 10 min/día | 300 min | **$1.80** |
| 30 min/día | 900 min | **$5.40** |
| 60 min/día | 1800 min | **$10.80** |

**Primer uso:** OpenAI da $5 de créditos gratis cuando te registras.

---

## 🔑 PASO 1: Obtener API Key de OpenAI

### Opción A: Si ya tienes cuenta

1. Ve a: https://platform.openai.com/api-keys
2. Haz clic en "**Create new secret key**"
3. Nombre: `WhisperFlow`
4. **Copia la key** (empieza con `sk-...`)
5. **¡IMPORTANTE!** Guárdala - solo se muestra una vez

### Opción B: Si NO tienes cuenta

1. Ve a: https://platform.openai.com/signup
2. Regístrate con tu email
3. Verifica tu email
4. Agrega método de pago (tarjeta)
   - **Primer uso:** $5 de créditos GRATIS
   - Luego cobran por uso real
5. Ve a: https://platform.openai.com/api-keys
6. Crea nueva API key

---

## 🛠️ PASO 2: Configurar WhisperFlow

### Método Fácil (Recomendado):

```bash
cd /mnt/d/Dev/whisperflow-cloud
./configurar_openai.sh
```

El script te pedirá tu API key y configurará todo automáticamente.

### Método Manual:

1. Crea archivo `.env` en `/mnt/d/Dev/whisperflow-cloud`:

```bash
# Copia el ejemplo
cp .env.example .env

# Edita el archivo
nano .env
```

2. Pega tu API key:

```env
OPENAI_API_KEY=sk-tu-api-key-aqui
TRANSCRIPTION_MODE=openai
LOCAL_MODEL=small
PORT=8181
```

3. Guarda y cierra (Ctrl+X, luego Y, luego Enter)

---

## 🚀 PASO 3: Reiniciar WhisperFlow

```bash
cd /mnt/d/Dev/whisperflow-cloud
./whisperflow_no_systemd.sh restart
```

**Deberías ver en los logs:**
```
✅ Modo OpenAI activado - Transcripción ultra-rápida disponible
✅ OpenAI Whisper API disponible para WebSocket - Modo rápido activo
```

**Si ves esto, estás usando modelo local (lento):**
```
📦 Cargando modelo local: small.pt
```

---

## 🎯 PASO 4: Probar

1. Abre la ventana GUI (debería aparecer automáticamente)
2. Verifica: "✅ Conectado al servidor"
3. Haz clic en "🔴 GRABAR"
4. **Habla un texto LARGO (1-2 minutos)** en español
5. Haz clic en "⏹️ DETENER"
6. **Espera solo 2-5 segundos** (¡mucho más rápido!)
7. Verás: "📋 Presiona Ctrl+V para pegar"
8. Presiona Ctrl+V en cualquier aplicación

**Resultado esperado:**
- ⚡ Procesamiento ultra-rápido (2-5 seg)
- 📝 Transcripción precisa en español
- 🚫 NO crash
- 💻 NO consume tu CPU

---

## 🔍 Verificar que OpenAI está Activo

### Método 1: Ver logs del servidor

```bash
docker logs whisperflow-server | grep -i openai
```

**Deberías ver:**
```
✅ Modo OpenAI activado - Transcripción ultra-rápida disponible
✅ OpenAI Whisper API disponible para WebSocket - Modo rápido activo
📤 Enviando XXXX bytes de audio a OpenAI API...
✅ Transcripción async completada: XXX caracteres
```

### Método 2: Observar el tiempo de procesamiento

- **Con OpenAI:** 2-5 segundos (cualquier longitud)
- **Con modelo local:** 3-4 min por cada min de audio

Si el procesamiento es rápido, OpenAI está activo ✅

---

## ⚠️ Troubleshooting

### Problema: "❌ No se pudo inicializar OpenAI"

**Causas posibles:**

1. **API key incorrecta**
   - Verifica que empiece con `sk-`
   - Verifica que no tenga espacios extras
   - Crea una nueva key si es necesario

2. **Archivo .env no cargado**
   ```bash
   # Verificar que existe
   ls -la /mnt/d/Dev/whisperflow-cloud/.env

   # Ver contenido
   cat /mnt/d/Dev/whisperflow-cloud/.env
   ```

3. **Variable de entorno no configurada**
   ```bash
   # Verificar que Docker recibe la variable
   docker exec whisperflow-server printenv OPENAI_API_KEY

   # Debería mostrar: sk-...
   ```

**Solución:**
```bash
# Re-ejecutar configuración
cd /mnt/d/Dev/whisperflow-cloud
./configurar_openai.sh

# Reiniciar con rebuild
docker-compose down
docker-compose up -d --build
./whisperflow_no_systemd.sh restart
```

### Problema: "Fallback a modelo local"

Significa que OpenAI no se pudo inicializar. Ver causas arriba.

### Problema: Biblioteca openai no instalada

```bash
# Instalar en venv local
cd /mnt/d/Dev/whisperflow-cloud
source .venv/bin/activate
pip install openai==1.12.0

# Rebuild Docker con nuevas dependencias
docker-compose up -d --build
```

---

## 📊 Monitoreo de Uso y Costos

### Ver tu uso en OpenAI:

1. Ve a: https://platform.openai.com/usage
2. Filtra por "Whisper API"
3. Verás minutos consumidos y costo

### Establecer límites de gasto:

1. Ve a: https://platform.openai.com/account/billing/limits
2. Configura límite mensual (ej: $10/mes)
3. Recibirás email si alcanzas el límite

---

## 🔄 Volver a Modelo Local (Gratis)

Si prefieres volver al modelo local:

```bash
# Editar .env
nano /mnt/d/Dev/whisperflow-cloud/.env

# Cambiar:
TRANSCRIPTION_MODE=local

# Reiniciar
./whisperflow_no_systemd.sh restart
```

**Nota:** Volverás a tener procesamiento lento para textos largos.

---

## 📝 Resumen Rápido

```bash
# 1. Obtener API key en: https://platform.openai.com/api-keys

# 2. Configurar
cd /mnt/d/Dev/whisperflow-cloud
./configurar_openai.sh

# 3. Reiniciar
./whisperflow_no_systemd.sh restart

# 4. Verificar
docker logs whisperflow-server | grep "OpenAI"

# 5. Usar normalmente - ¡Ahora es RÁPIDO!
```

---

## 🎉 ¡Listo!

Ahora puedes dictar textos LARGOS sin preocuparte por:
- ❌ Procesamiento lento
- ❌ Crashes
- ❌ Consumo de CPU
- ❌ Esperas infinitas

Disfruta de tu sistema de dictado profesional ultra-rápido! 🚀
