"""
calendar_sync.py - Sincronización con Google Calendar vía Webhook (Google Apps Script)
Compatible con Python 3.8 y 3.10+ (Windows 8 / 10 / 11).
"""

import json
import os
import sys
import requests
from typing import Optional, Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def cargar_config(ruta_config: Optional[str] = None) -> Dict[str, Any]:
    """Carga la configuración desde config.json."""
    ruta = ruta_config or CONFIG_FILE
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def debe_omitirse(
    titulo: str,
    id_clase: str,
    palabras_ignorar: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> bool:
    """
    Determina si la clase debe ser marcada como [Omitida]:
    - Si ya figura como COMPLETADA en clases.db
    - O si contiene alguna de las palabras de 'palabras_ignorar' (case-insensitive)
    """
    if database.es_clase_completada(id_clase, db_path):
        return True

    palabras = palabras_ignorar or []
    titulo_lower = titulo.lower()
    id_lower = id_clase.lower()

    for palabra in palabras:
        p = palabra.strip().lower()
        if p and (p in titulo_lower or p in id_lower):
            return True

    return False


def generar_titulo_con_icono(
    titulo_original: str,
    id_clase: str,
    palabras_ignorar: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> str:
    """
    Genera el título formateado con el icono correspondiente:
    - ⏳ [Programada] Masterclass: [Nombre]
    - ⏭️ [Omitida] Masterclass: [Nombre]
    """
    if debe_omitirse(titulo_original, id_clase, palabras_ignorar, db_path):
        return f"⏭️ [Omitida] Masterclass: {titulo_original}"
    else:
        return f"⏳ [Programada] Masterclass: {titulo_original}"


def enviar_a_calendar(
    id_clase: str,
    titulo_con_icono: str,
    inicio_iso: str,
    fin_iso: str,
    webhook_url: str,
    timeout: int = 25,
) -> Dict[str, Any]:
    """
    Envía la petición POST en formato JSON a Google Apps Script con la estructura:
    {"id_clase": id_normalizado, "titulo": titulo_con_icono, "inicio": fecha_hora_iso, "fin": fecha_hora_iso}
    """
    payload = {
        "id_clase": id_clase,
        "titulo": titulo_con_icono,
        "inicio": inicio_iso,
        "fin": fin_iso,
    }

    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=timeout)
        response_text = response.text.strip()
        status_code = response.status_code

        exito = status_code == 200 and ("CREADO" in response_text or "ACTUALIZADO" in response_text)

        return {
            "exito": exito,
            "status_code": status_code,
            "respuesta": response_text,
            "payload": payload,
            "error": None,
        }
    except Exception as exc:
        return {
            "exito": False,
            "status_code": 0,
            "respuesta": "",
            "payload": payload,
            "error": str(exc),
        }


def sincronizar_clase(
    clase_info: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sincroniza una clase individual con Google Calendar:
    clase_info debe contener:
    - id_clase (str)
    - titulo_original (str)
    - inicio_iso (str)
    - fin_iso (str)
    """
    cfg = config or cargar_config()
    webhook_url = cfg.get("calendar_webhook_url")
    if not webhook_url:
        raise ValueError("calendar_webhook_url no está definida en la configuración")

    palabras_ignorar = cfg.get("palabras_ignorar", [])

    id_clase = clase_info["id_clase"]
    titulo_original = clase_info["titulo_original"]
    inicio_iso = clase_info["inicio_iso"]
    fin_iso = clase_info["fin_iso"]

    titulo_con_icono = generar_titulo_con_icono(
        titulo_original=titulo_original,
        id_clase=id_clase,
        palabras_ignorar=palabras_ignorar,
        db_path=db_path,
    )

    resultado = enviar_a_calendar(
        id_clase=id_clase,
        titulo_con_icono=titulo_con_icono,
        inicio_iso=inicio_iso,
        fin_iso=fin_iso,
        webhook_url=webhook_url,
    )

    return resultado


def actualizar_estado_evento(
    id_clase: str,
    titulo_original: str,
    prefijo: str,
    inicio_iso: str,
    fin_iso: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Actualiza el evento en Google Calendar con un prefijo personalizado:
    Ejemplos:
    - prefijo = '🔴 [GRABANDO AHORA]'
    - prefijo = '✅ [EN TELEGRAM]'
    - prefijo = '⏭️ [Omitida]'
    - prefijo = '⏳ [Programada]'
    """
    cfg = config or cargar_config()
    webhook_url = cfg.get("calendar_webhook_url")
    if not webhook_url:
        raise ValueError("calendar_webhook_url no está definida en la configuración")

    titulo_con_icono = f"{prefijo} Masterclass: {titulo_original}"
    return enviar_a_calendar(
        id_clase=id_clase,
        titulo_con_icono=titulo_con_icono,
        inicio_iso=inicio_iso,
        fin_iso=fin_iso,
        webhook_url=webhook_url,
    )


def sincronizar_lista_clases(

    clases: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Sincroniza una lista de clases detectadas con Google Calendar."""
    cfg = config or cargar_config()
    resultados = []

    for c in clases:
        res = sincronizar_clase(c, config=cfg, db_path=db_path)
        resultados.append(
            {
                "id_clase": c["id_clase"],
                "titulo": c["titulo_original"],
                "exito": res["exito"],
                "respuesta": res["respuesta"],
                "error": res["error"],
                "inicio_iso": c["inicio_iso"],
                "fin_iso": c["fin_iso"],
            }
        )

    return resultados


if __name__ == "__main__":
    cfg = cargar_config()
    print("Probando calendar_sync...")
    test_data = {
        "id_clase": "clase_de_prueba_fase1",
        "titulo_original": "Clase de Prueba Fase 1 Automatizada",
        "inicio_iso": "2026-10-15T22:00:00-04:00",
        "fin_iso": "2026-10-15T23:00:00-04:00",
    }
    r = sincronizar_clase(test_data, config=cfg)
    print(f"Resultado test: Éxito={r['exito']}, Respuesta='{r['respuesta']}', Error={r['error']}")
