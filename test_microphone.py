#!/usr/bin/env python3
"""
Script de prueba para verificar si el micrófono funciona en WSL2
"""

import pyaudio
import wave
import sys

print("🎤 Test de Micrófono en WSL2")
print("=" * 50)
print("")

# Configuración
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5
OUTPUT_FILE = "test_microphone_recording.wav"

# Inicializar PyAudio
audio = pyaudio.PyAudio()

# Listar dispositivos disponibles
print("Dispositivos de audio disponibles:")
print("-" * 50)
for i in range(audio.get_device_count()):
    info = audio.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:  # Solo mostrar dispositivos de entrada
        print(f"  [{i}] {info['name']}")
        print(f"      Canales: {info['maxInputChannels']}")
        print(f"      Sample Rate: {int(info['defaultSampleRate'])} Hz")
        print("")

print("=" * 50)
print("")
print(f"📹 Grabando {RECORD_SECONDS} segundos de audio...")
print("   Habla algo cerca del micrófono...")
print("")

try:
    # Abrir stream de audio
    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    frames = []

    # Grabar
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        # Indicador de progreso
        if i % 10 == 0:
            print(".", end="", flush=True)

    print("")
    print("")
    print("✅ Grabación completada")

    # Detener stream
    stream.stop_stream()
    stream.close()

    # Guardar archivo
    print(f"💾 Guardando audio en: {OUTPUT_FILE}")
    wf = wave.open(OUTPUT_FILE, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print("")
    print("=" * 50)
    print("✅ TEST EXITOSO")
    print("=" * 50)
    print("")
    print(f"El archivo '{OUTPUT_FILE}' fue creado.")
    print("Puedes reproducirlo para verificar que el micrófono funciona.")
    print("")
    print("En Windows, puedes reproducirlo con:")
    print(f"  PowerShell: Start-Process '{OUTPUT_FILE}'")
    print(f"  O desde el explorador de archivos")
    print("")

except Exception as e:
    print("")
    print("=" * 50)
    print("❌ ERROR")
    print("=" * 50)
    print(f"Error al grabar: {e}")
    print("")
    sys.exit(1)

finally:
    audio.terminate()
