#!/usr/bin/env python3
"""
Test manual del WebSocket con OpenAI API
Validación E2E para verificar que el problema "Procesando..." infinito está resuelto
"""

import asyncio
import json
import websockets
import struct
import numpy as np

async def test_websocket_connection():
    """Test básico de conexión WebSocket + transcripción simulada"""

    server_url = "ws://localhost:8181/ws"

    print(f"🔌 Conectando a {server_url}...")

    try:
        async with websockets.connect(server_url) as websocket:
            print("✅ Conexión WebSocket establecida")

            # Generar audio simulado (1 segundo de silencio @ 16kHz, 16-bit PCM)
            # En un test real, esto vendría del micrófono
            duration_seconds = 1
            sample_rate = 16000
            num_samples = duration_seconds * sample_rate

            # Silencio (valores cercanos a 0)
            audio_data = np.random.randint(-100, 100, num_samples, dtype=np.int16)
            audio_bytes = audio_data.tobytes()

            print(f"📤 Enviando {len(audio_bytes)} bytes de audio simulado...")

            # Enviar audio en chunks (como lo hace la GUI real)
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                await websocket.send(chunk)
                await asyncio.sleep(0.01)  # Simular delay de captura real

            print("⏳ Esperando respuesta del servidor (máx 10 segundos)...")

            # Esperar respuesta con timeout
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)

                print(f"📩 Respuesta recibida:")
                print(f"   - is_partial: {data.get('is_partial')}")
                print(f"   - text: {data.get('data', {}).get('text', 'N/A')}")

                if data.get("is_partial") == False:
                    print("✅ TEST PASSED: Recibimos transcripción final (NO stuck en 'Procesando...')")
                    return True
                else:
                    print("⚠️  Transcripción parcial recibida, esperando final...")
                    # En producción, aquí esperaríamos más mensajes

            except asyncio.TimeoutError:
                print("❌ TEST FAILED: Timeout esperando respuesta (stuck en 'Procesando...')")
                return False

    except ConnectionRefusedError:
        print("❌ ERROR: No se pudo conectar al servidor")
        print("   Verificar que el container está corriendo: docker-compose ps")
        return False
    except Exception as e:
        print(f"❌ ERROR inesperado: {e}")
        return False

async def test_health_endpoint():
    """Test complementario del health endpoint"""
    import httpx

    print("\n🏥 Verificando health endpoint...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8181/health")
            data = response.json()

            print(f"✅ Health check OK:")
            print(f"   - status: {data.get('status')}")
            print(f"   - model_status: {data.get('model_status')}")
            print(f"   - transcription_mode: {data.get('transcription_mode')}")

            if data.get("model_status") == "openai_ready":
                print("✅ OpenAI API está lista")
                return True
            else:
                print(f"⚠️  Model status: {data.get('model_status')}")
                return False

        except Exception as e:
            print(f"❌ Error en health check: {e}")
            return False

async def main():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("WhisperFlow - Test E2E OpenAI API")
    print("=" * 60)

    # Test 1: Health endpoint
    health_ok = await test_health_endpoint()

    if not health_ok:
        print("\n❌ Health check falló - Abortando tests")
        return

    # Test 2: WebSocket connection
    print("\n" + "=" * 60)
    ws_ok = await test_websocket_connection()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN:")
    print(f"  Health endpoint: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"  WebSocket test:  {'✅ PASS' if ws_ok else '❌ FAIL'}")
    print("=" * 60)

    if health_ok and ws_ok:
        print("\n🎉 TODOS LOS TESTS PASARON")
        print("El problema 'Procesando...' infinito está RESUELTO")
    else:
        print("\n⚠️  Algunos tests fallaron - Revisar logs del servidor")

if __name__ == "__main__":
    asyncio.run(main())
