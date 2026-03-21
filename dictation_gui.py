#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente de Dictado con Interfaz Gráfica (GUI)
Solución alternativa para WSL2 donde hotkeys no funcionan
"""

import asyncio
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

import pyaudio
import pyperclip
import websockets

class DictationGUI:
    def __init__(self, server_url="ws://localhost:8181/ws"):
        self.server_url = server_url
        self.is_recording = False
        self.is_connected = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.audio_queue = queue.Queue()

        # Configuración de audio (OPTIMIZADO para WSL2 + OpenAI API)
        self.chunk_size = 4096  # Aumentado de 1024 → Evita chunks muy pequeños que OpenAI rechaza
        self.sample_rate = 16000  # OpenAI recomienda 16kHz
        self.audio = pyaudio.PyAudio()
        self.stream = None

        # Selección de device de audio (CRÍTICO para WSL2)
        # Device 0 = "pulse" (PulseAudio directo - micrófono real)
        # Device 1 = "default" (podría ser loopback - audio del sistema)
        self.input_device_index = int(os.getenv("WHISPERFLOW_INPUT_DEVICE", "0"))  # Force pulse by default

        # Loop de asyncio
        self.loop = None

        # Log configuración al inicio
        self._log_audio_config()

        # Crear GUI
        self.create_gui()

    def _log_audio_config(self):
        """Log configuración de audio para diagnóstico"""
        print(f"🎙️  Configuración de Audio:")
        print(f"   - Sample Rate: {self.sample_rate} Hz")
        print(f"   - Chunk Size: {self.chunk_size} bytes")
        print(f"   - Input Device: {self.input_device_index}")

        try:
            device_info = self.audio.get_device_info_by_index(self.input_device_index)
            print(f"   - Device Name: {device_info['name']}")
            print(f"   - Max Input Channels: {device_info['maxInputChannels']}")
        except Exception as e:
            print(f"   ⚠️  Warning: No se pudo obtener info del device: {e}")

    def create_gui(self):
        """Crea la interfaz gráfica"""
        self.root = tk.Tk()
        self.root.title("WhisperFlow - Dictado Universal")
        self.root.geometry("400x300")
        self.root.resizable(False, False)

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')

        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(
            main_frame,
            text="🎤 WhisperFlow Dictado",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Estado de conexión
        self.status_label = ttk.Label(
            main_frame,
            text="⏳ Conectando al servidor...",
            font=("Arial", 10)
        )
        self.status_label.pack(pady=10)

        # Botón de grabación (grande y centrado)
        self.record_button = tk.Button(
            main_frame,
            text="🔴 GRABAR",
            font=("Arial", 14, "bold"),
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            height=3,
            width=20,
            command=self.toggle_recording,
            state=tk.DISABLED
        )
        self.record_button.pack(pady=20)

        # Indicador de grabación
        self.recording_label = ttk.Label(
            main_frame,
            text="",
            font=("Arial", 12, "bold"),
            foreground="#e74c3c"
        )
        self.recording_label.pack(pady=10)

        # Transcripción actual
        self.transcription_label = ttk.Label(
            main_frame,
            text="",
            font=("Arial", 9),
            foreground="#555",
            wraplength=360
        )
        self.transcription_label.pack(pady=10)

        # Instrucciones
        instructions = ttk.Label(
            main_frame,
            text="Instrucciones:\n1. Haz clic en 'GRABAR' para empezar\n2. Habla cerca del micrófono\n3. Haz clic en 'DETENER' cuando termines\n4. El texto aparecerá en la app activa",
            font=("Arial", 8),
            foreground="#888",
            justify=tk.CENTER
        )
        instructions.pack(side=tk.BOTTOM, pady=10)

        # Configurar cierre
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def toggle_recording(self):
        """Alterna entre grabar y detener"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Inicia la grabación de audio"""
        # Reconectar si el WebSocket está cerrado o no existe
        if not self.websocket or self.websocket.closed:
            print("🔌 Reconectando al servidor para nueva sesión...")
            self.reconnect_to_server()
            # Programar inicio de grabación después de reconectar
            self.root.after(1000, self.start_recording_after_connect)
            return

        self.is_recording = True

        try:
            self.setup_audio()
        except Exception as e:
            print(f"❌ Error configurando audio: {e}")
            self.transcription_label.config(
                text=f"❌ Error con micrófono: {str(e)[:50]}"
            )
            self.record_button.config(state=tk.NORMAL)
            return

        # Actualizar UI
        self.record_button.config(
            text="⏹️ DETENER",
            bg="#27ae60",
            activebackground="#229954"
        )
        self.recording_label.config(text="🔴 GRABANDO...")
        self.transcription_label.config(text="Habla ahora...")

        # Iniciar captura de audio en thread separado
        threading.Thread(target=self.capture_audio, daemon=True).start()

    def start_recording_after_connect(self):
        """Inicia grabación después de reconectar (callback)"""
        if self.is_connected and self.websocket and not self.websocket.closed:
            self.start_recording()
        else:
            print("⚠️  No se pudo reconectar - intenta de nuevo")
            self.record_button.config(state=tk.NORMAL)

    def reconnect_to_server(self):
        """Reconecta al servidor WebSocket"""
        self.is_connected = False
        self.transcription_label.config(text="🔌 Reconectando...")
        self.record_button.config(state=tk.DISABLED)

        # Lanzar reconexión en el loop asyncio
        asyncio.run_coroutine_threadsafe(
            self.connect_to_server(),
            self.loop
        )

    def stop_recording(self):
        """Para la grabación de audio"""
        if not self.is_recording:
            return

        self.is_recording = False

        # Actualizar UI inmediatamente
        self.record_button.config(
            text="🔴 GRABAR",
            bg="#e74c3c",
            activebackground="#c0392b",
            state=tk.DISABLED  # Deshabilitar hasta que termine procesamiento
        )
        self.recording_label.config(text="⏳ Procesando...")
        self.transcription_label.config(text="Espera la transcripción...")

        # Cleanup de audio de forma segura
        self.cleanup_audio()

        # NO cerrar WebSocket - el servidor detectará que no hay más audio
        # y enviará la transcripción final
        print("⏹️ Grabación detenida - esperando transcripción final...")

    def setup_audio(self):
        """Configura el stream de audio con device específico"""
        print(f"🎙️  Abriendo stream de audio (device {self.input_device_index})...")

        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.input_device_index,  # CRÍTICO: Fuerza device específico (no default)
            frames_per_buffer=self.chunk_size,
        )

        print(f"✅ Stream de audio abierto correctamente")

    def cleanup_audio(self):
        """Limpia recursos de audio de forma segura"""
        if self.stream:
            try:
                # Intentar detener el stream de forma limpia
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except OSError as e:
                # Error -9999 es un bug conocido de PyAudio en WSL2 al cerrar stream
                # Aparece DESPUÉS de que la grabación ya terminó correctamente
                # Puede ignorarse de forma segura
                if "-9999" in str(e) or "Unanticipated host error" in str(e):
                    print("✅ Stream de audio cerrado (ignorando warning WSL2)")
                else:
                    print(f"⚠️  Warning al cerrar stream de audio: {e}")
            except Exception as e:
                print(f"⚠️  Error inesperado cerrando audio: {e}")
            finally:
                self.stream = None

    def capture_audio(self):
        """Captura audio del micrófono y lo envía al servidor

        NO HAY LÍMITE DE DURACIÓN - El loop corre mientras is_recording=True
        Soporta grabaciones infinitamente largas (solo limitado por memoria/red)
        """
        bytes_sent = 0
        chunks_sent = 0
        start_time = time.time()

        try:
            print(f"🎙️  Iniciando captura de audio...")

            while self.is_recording and self.stream:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                bytes_sent += len(data)
                chunks_sent += 1

                if self.websocket and not self.websocket.closed:
                    # Enviar al servidor via asyncio
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.send(data),
                        self.loop
                    )

                    # Log cada 10 chunks para diagnosticar (no flood console)
                    if chunks_sent % 10 == 0:
                        elapsed = time.time() - start_time
                        print(f"📊 Audio: {chunks_sent} chunks ({bytes_sent / 1024:.1f} KB) en {elapsed:.1f}s")
                else:
                    print(f"⚠️  WebSocket cerrado - deteniendo captura")
                    break

            elapsed = time.time() - start_time
            print(f"✅ Captura completa: {chunks_sent} chunks ({bytes_sent / 1024:.1f} KB) en {elapsed:.1f}s")

        except Exception as e:
            # Error -9999 es normal en WSL2 cuando el stream se cierra durante read()
            # Chequear por mensaje, NO por tipo de excepción
            if "-9999" in str(e) or "Unanticipated host error" in str(e):
                elapsed = time.time() - start_time
                print(f"✅ Captura finalizada: {chunks_sent} chunks ({bytes_sent / 1024:.1f} KB) en {elapsed:.1f}s (stream cerrado)")
            else:
                print(f"❌ Error capturando audio: {e}")
                self.is_recording = False
                error_msg = str(e)[:50]
                self.root.after(0, lambda msg=error_msg: self.transcription_label.config(
                    text=f"❌ Error: {msg}"
                ))

    def insert_text(self, text: str):
        """Inserta texto en la aplicación activa"""
        try:
            # Asegurar UTF-8 encoding
            text_utf8 = text.encode('utf-8').decode('utf-8')

            # Copiar al clipboard
            pyperclip.copy(text_utf8)

            # Esperar un poco
            time.sleep(0.1)

            # Simular Ctrl+V (NO funciona en WSL2, pero clipboard sí)
            # El usuario deberá pegar manualmente con Ctrl+V

            # Actualizar UI
            self.transcription_label.config(
                text=f"✅ Texto copiado al clipboard:\n{text[:100]}..."
            )
            self.recording_label.config(
                text="📋 Presiona Ctrl+V para pegar"
            )

            # Reactivar botón de grabación para nueva sesión
            self.record_button.config(state=tk.NORMAL)

        except Exception as e:
            print(f"❌ Error insertando texto: {e}")
            self.transcription_label.config(text=f"❌ Error: {str(e)[:50]}")
            # Reactivar botón incluso si hay error
            self.record_button.config(state=tk.NORMAL)

    async def connect_to_server(self):
        """Conecta al servidor WhisperFlow"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True

            # Actualizar UI
            self.root.after(0, lambda: self.status_label.config(
                text="✅ Conectado al servidor"
            ))
            self.root.after(0, lambda: self.record_button.config(
                state=tk.NORMAL
            ))

            # Escuchar transcripciones
            await self.listen_transcriptions()

        except Exception as e:
            print(f"❌ Error conectando al servidor: {e}")
            self.is_connected = False
            self.root.after(0, lambda: self.status_label.config(
                text=f"❌ Error: {str(e)[:50]}"
            ))

    async def listen_transcriptions(self):
        """Escucha las transcripciones del servidor"""
        try:
            async for message in self.websocket:
                data = json.loads(message)

                if not data["is_partial"]:
                    # Transcripción completa
                    text = data["data"]["text"].strip()
                    if text:
                        print(f"📝 Transcrito: {text}")
                        self.root.after(0, lambda t=text: self.insert_text(t))
                else:
                    # Transcripción parcial
                    partial_text = data["data"]["text"].strip()
                    if partial_text:
                        self.root.after(0, lambda t=partial_text:
                            self.transcription_label.config(text=f"🔄 {t[:100]}...")
                        )

        except websockets.exceptions.ConnectionClosed:
            print("🔌 Conexión WebSocket cerrada")
            # NO marcar como desconectado - la conexión se cerrará y reabrirá
            # automáticamente en la próxima grabación
        except Exception as e:
            print(f"❌ Error escuchando transcripciones: {e}")
            self.is_connected = False
            self.root.after(0, lambda: self.status_label.config(
                text=f"❌ Error: {str(e)[:50]}"
            ))
            self.root.after(0, lambda: self.record_button.config(state=tk.DISABLED))

    def on_closing(self):
        """Maneja el cierre de la ventana"""
        print("👋 Cerrando aplicación...")
        self.is_recording = False
        self.cleanup_audio()
        self.audio.terminate()
        if self.websocket:
            asyncio.run_coroutine_threadsafe(
                self.websocket.close(),
                self.loop
            )
        self.root.destroy()

    async def run_async(self):
        """Ejecuta el loop asyncio"""
        self.loop = asyncio.get_event_loop()
        await self.connect_to_server()

    def run(self):
        """Ejecuta la aplicación"""
        # Iniciar loop asyncio en thread separado
        def start_async_loop():
            asyncio.run(self.run_async())

        threading.Thread(target=start_async_loop, daemon=True).start()

        # Iniciar GUI
        self.root.mainloop()


def main():
    print("🎤 Iniciando WhisperFlow con Interfaz Gráfica...")
    app = DictationGUI()
    app.run()


if __name__ == "__main__":
    main()
