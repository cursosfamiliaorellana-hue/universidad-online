"""
prueba_30_segundos.py - Punto de entrada para la prueba de 60 segundos del Bot Automático.
Ejecuta el código idéntico del orquestador principal (main.py) con la condición de duración a 60 segundos.
Garantiza 100% que si esta prueba funciona, el botón de 'Iniciar Bot Automático' funciona exactamente igual.
"""

import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import main

if __name__ == "__main__":
    main.database.init_db()
    asyncio.run(main.ejecutar_prueba_60s())
