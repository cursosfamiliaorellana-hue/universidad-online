"""
error_buffer.py - Sistema de Buffer de Errores (Offline-First) y Protocolo de Auto-Sanación
Permite registrar y almacenar fallos en 'registro_errores.json' y sincronizarlos silenciosamente
con el Agente de Inteligencia Artificial Antigravity en la Laptop Dell cuando haya conectividad.
"""

import os
import sys
import time
import json
import threading
import traceback
import datetime
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRO_ERRORES_PATH = os.path.join(BASE_DIR, "registro_errores.json")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

_buffer_lock = threading.Lock()
MAX_BUFFER_ERRORES = 250


def _cargar_config_dell() -> Dict[str, Any]:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def obtener_errores(filtro_estado: Optional[str] = None, max_items: int = 100) -> List[Dict[str, Any]]:
    """Lee y devuelve los errores almacenados en registro_errores.json."""
    with _buffer_lock:
        if not os.path.exists(REGISTRO_ERRORES_PATH):
            return []
        try:
            with open(REGISTRO_ERRORES_PATH, "r", encoding="utf-8", errors="replace") as f:
                datos = json.load(f)
            if not isinstance(datos, list):
                datos = []
        except Exception:
            return []

    if filtro_estado:
        datos = [e for e in datos if str(e.get("estado", "")).lower() == filtro_estado.lower()]

    # Ordenar más recientes primero
    return list(reversed(datos))[:max_items]


def _guardar_errores_en_disco(lista_errores: List[Dict[str, Any]]) -> bool:
    """Guarda la lista de errores de forma atómica y segura."""
    # Limitar tamaño máximo para proteger disco y memoria
    if len(lista_errores) > MAX_BUFFER_ERRORES:
        lista_errores = lista_errores[-MAX_BUFFER_ERRORES:]

    ruta_tmp = REGISTRO_ERRORES_PATH + ".tmp"
    try:
        with open(ruta_tmp, "w", encoding="utf-8", errors="replace") as f:
            json.dump(lista_errores, f, ensure_ascii=False, indent=2)
        if os.path.exists(REGISTRO_ERRORES_PATH):
            os.replace(ruta_tmp, REGISTRO_ERRORES_PATH)
        else:
            os.rename(ruta_tmp, REGISTRO_ERRORES_PATH)
        return True
    except Exception:
        try:
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)
        except Exception:
            pass
        return False


def registrar_error(
    modulo: str,
    error_traceback: str,
    estado: str = "Pendiente",
    detalles: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Registra un fallo en 'registro_errores.json'.
    Campos garantizados: [timestamp, modulo, error_traceback, estado="Pendiente"].
    """
    ahora_dt = datetime.datetime.now()
    ts_str = ahora_dt.strftime("%Y-%m-%d %H:%M:%S")
    uid = f"err_{int(time.time() * 1000)}"

    nueva_entrada = {
        "id": uid,
        "timestamp": ts_str,
        "modulo": str(modulo or "general").strip(),
        "error_traceback": str(error_traceback or "").strip(),
        "estado": estado,  # "Pendiente", "Enviado", "Resuelto"
    }
    if detalles:
        nueva_entrada["detalles"] = detalles

    with _buffer_lock:
        lista_actual = []
        if os.path.exists(REGISTRO_ERRORES_PATH):
            try:
                with open(REGISTRO_ERRORES_PATH, "r", encoding="utf-8", errors="replace") as f:
                    datos = json.load(f)
                    if isinstance(datos, list):
                        lista_actual = datos
            except Exception:
                lista_actual = []

        lista_actual.append(nueva_entrada)
        _guardar_errores_en_disco(lista_actual)

    return nueva_entrada


def marcar_errores_como(ids: List[str], nuevo_estado: str = "Resuelto") -> int:
    """Actualiza el estado de una lista de IDs de error (e.g. 'Enviado' o 'Resuelto')."""
    if not ids:
        return 0
    modificados = 0
    with _buffer_lock:
        if not os.path.exists(REGISTRO_ERRORES_PATH):
            return 0
        try:
            with open(REGISTRO_ERRORES_PATH, "r", encoding="utf-8", errors="replace") as f:
                lista = json.load(f)
            if not isinstance(lista, list):
                return 0
            set_ids = set(ids)
            for err in lista:
                if err.get("id") in set_ids:
                    err["estado"] = nuevo_estado
                    modificados += 1
            if modificados > 0:
                _guardar_errores_en_disco(lista)
        except Exception:
            return 0
    return modificados


def marcar_todos_resueltos() -> int:
    """Marca todos los errores pendientes o enviados como 'Resuelto'."""
    modificados = 0
    with _buffer_lock:
        if not os.path.exists(REGISTRO_ERRORES_PATH):
            return 0
        try:
            with open(REGISTRO_ERRORES_PATH, "r", encoding="utf-8", errors="replace") as f:
                lista = json.load(f)
            if not isinstance(lista, list):
                return 0
            for err in lista:
                if err.get("estado") != "Resuelto":
                    err["estado"] = "Resuelto"
                    modificados += 1
            if modificados > 0:
                _guardar_errores_en_disco(lista)
        except Exception:
            return 0
    return modificados


def limpiar_todos_los_errores() -> bool:
    """Vacía por completo el archivo de errores."""
    with _buffer_lock:
        return _guardar_errores_en_disco([])


def intentar_sincronizar_con_dell(url_antigravity: Optional[str] = None) -> bool:
    """
    Intenta enviar los errores con estado 'Pendiente' hacia la laptop Dell.
    Si la Dell está apagada o inaccesible, captura la excepción silenciosamente y mantiene los errores 'Pendientes'.
    Si la sincronización tiene éxito (HTTP 200/201), actualiza el estado a 'Enviado'.
    """
    cfg = _cargar_config_dell()
    if not url_antigravity:
        dell_ip = cfg.get("antigravity_dell_ip", "192.168.100.243")
        dell_port = cfg.get("antigravity_dell_port", 5005)
        url_antigravity = f"http://{dell_ip}:{dell_port}/api/antigravity/sync_errores"

    # Obtener pendientes
    errores_pendientes = obtener_errores(filtro_estado="Pendiente", max_items=50)
    if not errores_pendientes:
        return True  # Nada pendiente por enviar

    payload = {
        "origen": "Laptop_Acer_Cliente",
        "timestamp_envio": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_errores": len(errores_pendientes),
        "errores": errores_pendientes
    }

    try:
        datos_json = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url_antigravity,
            data=datos_json,
            headers={"Content-Type": "application/json", "User-Agent": "BotUniversidadOnline-SelfHealing/1.0"},
            method="POST"
        )
        # Timeout corto (4s) para no congelar hilos
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status in (200, 201, 202, 204):
                ids_enviados = [e["id"] for e in errores_pendientes if "id" in e]
                marcar_errores_como(ids_enviados, nuevo_estado="Enviado")
                return True
    except Exception:
        # Modo silencioso: la Dell está apagada o inaccesible; se preserva estado 'Pendiente'
        pass

    return False


def iniciar_hilo_sincronizacion_background(intervalo_segundos: int = 300) -> threading.Thread:
    """
    Inicia un hilo demonio ultra-ligero que ejecuta la sincronización silenciosa periódica
    cada 5 minutos (300 segundos por defecto).
    """
    def _worker():
        # Espera inicial para permitir arranque de los servicios principales
        time.sleep(15)
        while True:
            try:
                intentar_sincronizar_con_dell()
            except Exception:
                pass
            time.sleep(intervalo_segundos)

    t = threading.Thread(target=_worker, name="SyncAntigravityDellThread", daemon=True)
    t.start()
    return t


def instalar_manejador_global(modulo_nombre: str = "general"):
    """
    Instala un interceptor de excepciones en sys.excepthook y threading.excepthook
    para capturar cualquier error no controlado y guardarlo automáticamente en registro_errores.json.
    """
    original_excepthook = sys.excepthook

    def _interceptor_global(exctype, value, tb):
        try:
            tb_str = "".join(traceback.format_exception(exctype, value, tb))
            registrar_error(
                modulo=modulo_nombre,
                error_traceback=tb_str,
                estado="Pendiente"
            )
        except Exception:
            pass
        if original_excepthook:
            try:
                original_excepthook(exctype, value, tb)
            except Exception:
                pass

    sys.excepthook = _interceptor_global

    if hasattr(threading, "excepthook"):
        original_thread_excepthook = threading.excepthook

        def _interceptor_thread(args):
            try:
                tb_str = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
                registrar_error(
                    modulo=f"{modulo_nombre}_thread",
                    error_traceback=tb_str,
                    estado="Pendiente"
                )
            except Exception:
                pass
            if original_thread_excepthook:
                try:
                    original_thread_excepthook(args)
                except Exception:
                    pass

        threading.excepthook = _interceptor_thread
