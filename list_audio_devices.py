#!/usr/bin/env python3
"""
Lista todos los dispositivos de audio disponibles en el sistema
Para diagnosticar problemas de micrófono en WSL2
"""

import pyaudio

def list_audio_devices():
    """Lista todos los dispositivos de audio con sus capabilities"""
    p = pyaudio.PyAudio()

    print("=" * 80)
    print("DISPOSITIVOS DE AUDIO DISPONIBLES")
    print("=" * 80)

    default_input = p.get_default_input_device_info()
    default_output = p.get_default_output_device_info()

    print(f"\n🎤 DEFAULT INPUT DEVICE: {default_input['name']} (index: {default_input['index']})")
    print(f"🔊 DEFAULT OUTPUT DEVICE: {default_output['name']} (index: {default_output['index']})")

    print("\n" + "=" * 80)
    print("TODOS LOS DISPOSITIVOS:")
    print("=" * 80)

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)

        # Determinar tipo
        device_type = []
        if info['maxInputChannels'] > 0:
            device_type.append("INPUT")
        if info['maxOutputChannels'] > 0:
            device_type.append("OUTPUT")

        type_str = " + ".join(device_type) if device_type else "UNKNOWN"

        # Detectar si es loopback/monitor
        is_monitor = "monitor" in info['name'].lower() or "loopback" in info['name'].lower()
        monitor_flag = " [⚠️ LOOPBACK/MONITOR]" if is_monitor else ""

        # Detectar si es el default
        is_default_input = (i == default_input['index'])
        is_default_output = (i == default_output['index'])
        default_flag = ""
        if is_default_input:
            default_flag += " [🎤 DEFAULT INPUT]"
        if is_default_output:
            default_flag += " [🔊 DEFAULT OUTPUT]"

        print(f"\nDevice {i}: {info['name']}")
        print(f"  Type: {type_str}{monitor_flag}{default_flag}")
        print(f"  Max Input Channels: {info['maxInputChannels']}")
        print(f"  Max Output Channels: {info['maxOutputChannels']}")
        print(f"  Default Sample Rate: {info['defaultSampleRate']} Hz")
        print(f"  Host API: {p.get_host_api_info_by_index(info['hostApi'])['name']}")

    p.terminate()

    print("\n" + "=" * 80)
    print("RECOMENDACIONES:")
    print("=" * 80)
    print("1. Para GRABAR VOZ: Usa un device INPUT que NO sea monitor/loopback")
    print("2. Si ves errores ALSA: Prueba diferentes devices o sample rates")
    print("3. El DEFAULT INPUT podría ser loopback - verifica arriba")
    print("=" * 80)

if __name__ == "__main__":
    list_audio_devices()
