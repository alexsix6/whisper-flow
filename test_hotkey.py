#!/usr/bin/env python3
"""
Script de prueba para verificar si pynput puede capturar hotkeys en WSL2
"""

import time
from pynput import keyboard
from pynput.keyboard import Key

print("🔍 Test de Captura de Hotkeys (pynput)")
print("=" * 50)
print("")
print("Instrucciones:")
print("1. Presiona Ctrl+Space para probar el hotkey")
print("2. Presiona ESC para salir")
print("")
print("Esperando hotkeys...")
print("")

hotkey_combo = {Key.ctrl_l, Key.space}
pressed_keys = set()
test_passed = False

def on_press(key):
    global pressed_keys, test_passed
    pressed_keys.add(key)

    print(f"⌨️  Tecla presionada: {key}")

    # Verificar si Ctrl+Space fue presionado
    if hotkey_combo <= pressed_keys:
        print("")
        print("✅ ¡ÉXITO! Ctrl+Space detectado correctamente")
        print("")
        test_passed = True

    # ESC para salir
    if key == Key.esc:
        print("")
        if test_passed:
            print("✅ Test completado exitosamente - pynput funciona correctamente")
        else:
            print("⚠️  Test incompleto - No se detectó Ctrl+Space")
        print("")
        return False

def on_release(key):
    global pressed_keys
    try:
        pressed_keys.remove(key)
    except KeyError:
        pass

# Iniciar listener
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

print("Test finalizado.")
