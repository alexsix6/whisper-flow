#!/usr/bin/env python3
"""
Cliente de Dictado Universal para WhisperFlow
Permite dictar en cualquier aplicación usando hotkeys
"""

import asyncio
import json
import queue
import threading
import time
from typing import Optional

import pyaudio
import pynput
import pyperclip
import websockets
from pynput import keyboard
from pynput.keyboard import Key, Listener


class UniversalDictationClient:
    def __init__(self, server_url="ws://localhost:8181/ws"):
        self.server_url = server_url
        self.is_recording = False
        self.is_connected = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.transcription_buffer = []
        self.audio_queue = queue.Queue()
        self.hotkey_combo = {Key.ctrl_l, Key.space}  # Ctrl+Space para activar
        self.pressed = set()
        
        # Configuración de audio
        self.chunk_size = 1024
        self.sample_rate = 16000
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        print("🎤 Cliente de Dictado Universal iniciado")
        print("📋 Hotkey: Ctrl+Space para comenzar/parar dictado")
        print("🔌 Conectando al servidor WhisperFlow...")

    def setup_audio(self):
        """Configura el stream de audio"""
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

    def cleanup_audio(self):
        """Limpia recursos de audio"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

    async def connect_to_server(self, max_retries=5):
        """Conecta al servidor WhisperFlow con retry logic"""
        for attempt in range(max_retries):
            try:
                self.websocket = await websockets.connect(self.server_url)
                self.is_connected = True
                print("✅ Conectado al servidor WhisperFlow")

                # Inicia el hilo de escucha de transcripciones
                asyncio.create_task(self.listen_transcriptions())
                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    print(f"⚠️  Intento {attempt+1}/{max_retries} falló. Reintentando en {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ Error conectando después de {max_retries} intentos: {e}")
                    self.is_connected = False
                    return False

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
                        self.insert_text(text)
                else:
                    # Transcripción parcial (opcional: mostrar progreso)
                    partial_text = data["data"]["text"].strip()
                    if partial_text:
                        print(f"🔄 Parcial: {partial_text}", end='\r')
                        
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Conexión perdida. Reintentando...")
            self.is_connected = False
            await asyncio.sleep(2)  # Wait 2s before reconnecting
            await self.connect_to_server()  # Retry connection with exponential backoff
        except Exception as e:
            print(f"❌ Error escuchando transcripciones: {e}")
            self.is_connected = False

    def insert_text(self, text: str):
        """Inserta texto en la aplicación activa"""
        try:
            # Método 1: Clipboard + Ctrl+V (más compatible)
            pyperclip.copy(text)
            
            # Pequeña pausa para que el clipboard se actualice
            time.sleep(0.1)
            
            # Simula Ctrl+V para pegar
            keyboard_controller = pynput.keyboard.Controller()
            keyboard_controller.press(Key.ctrl_l)
            keyboard_controller.press('v')
            keyboard_controller.release('v')
            keyboard_controller.release(Key.ctrl_l)
            
            print(f"✅ Texto insertado: {text[:50]}...")
            
            # Método 2: Escribir directamente (comentado, menos confiable)
            # keyboard_controller.type(text)
            
        except Exception as e:
            print(f"❌ Error insertando texto: {e}")

    def start_recording(self):
        """Inicia la grabación de audio"""
        if not self.is_connected:
            print("❌ No conectado al servidor")
            return
            
        if self.is_recording:
            return
            
        self.is_recording = True
        self.setup_audio()
        print("🔴 Grabando... (Ctrl+Space para parar)")
        
        # Inicia hilo de captura de audio
        threading.Thread(target=self.capture_audio, daemon=True).start()

    def stop_recording(self):
        """Para la grabación de audio"""
        if not self.is_recording:
            return
            
        self.is_recording = False
        self.cleanup_audio()
        print("⏹️  Grabación detenida")

    def capture_audio(self):
        """Captura audio del micrófono y lo envía al servidor"""
        try:
            while self.is_recording and self.stream:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                if self.websocket and not self.websocket.closed:
                    # Envía el chunk de audio al servidor
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.send(data), 
                        asyncio.get_event_loop()
                    )
                else:
                    break
                    
        except Exception as e:
            print(f"❌ Error capturando audio: {e}")
            self.stop_recording()

    def on_press(self, key):
        """Maneja teclas presionadas"""
        self.pressed.add(key)
        
        # Verifica si se presionó la combinación hotkey
        if self.hotkey_combo <= self.pressed:
            if not self.is_recording:
                self.start_recording()
            else:
                self.stop_recording()

    def on_release(self, key):
        """Maneja teclas liberadas"""
        try:
            self.pressed.remove(key)
        except KeyError:
            pass
        
        # ESC para salir
        if key == Key.esc:
            print("👋 Saliendo...")
            self.stop_recording()
            return False

    async def run(self):
        """Ejecuta el cliente principal"""
        # Conecta al servidor
        await self.connect_to_server()
        
        if not self.is_connected:
            return
        
        # Configura el listener de teclado
        listener = Listener(on_press=self.on_press, on_release=self.on_release)
        listener.start()
        
        print("⌨️  Escuchando hotkeys...")
        print("🔄 Presiona ESC para salir")
        
        try:
            # Mantiene el programa corriendo
            while True:
                await asyncio.sleep(0.1)
                if not listener.running:
                    break
        except KeyboardInterrupt:
            print("👋 Interrumpido por usuario")
        finally:
            self.stop_recording()
            if self.websocket:
                await self.websocket.close()
            listener.stop()


async def main():
    client = UniversalDictationClient()
    await client.run()


if __name__ == "__main__":
    asyncio.run(main()) 