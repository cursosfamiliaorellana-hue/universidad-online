"""
dashboard_web.py - Panel de Control Web Interactivo para Universidad Online
Servidor Flask en puerto 8000 (http://127.0.0.1:8000)
Proporciona:
- Modo Fantasma y Consolas Virtuales Plegables (<details>/<summary>) para Orquestador, Vigía y Sistema.
- Gestión completa de Clases y CRUD de programador_manual.py integrado (Hotmart por partes, Zoom/Voz, Modificar Mentor Efecto Dominó, Gestión de Mentores/Grupos, Ingesta Manual, Auditoría/Rescate).
- Gestión Granular de Borrado: Borrar Video Local, Borrar Material IA, Eliminar Clase del Sistema (cero peticiones a Telegram).
- Interfaz 100% Responsive adaptada a pantallas móviles y de escritorio.
"""

import asyncio
from collections import deque
import datetime
import gc
import glob
try:
    import ujson as json
except ImportError:
    try:
        import orjson as json
    except ImportError:
        import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import webbrowser
from typing import Dict, Any, List, Optional

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_GRABACIONES = os.path.join(BASE_DIR, "grabaciones")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ARCHIVO_FRENO_MANUAL = os.path.join(BASE_DIR, "DETENER_GRABACION.txt")

LOG_ORQUESTADOR_PATH = os.path.join(BASE_DIR, "logs_orquestador.txt")
LOG_VIGIA_PATH = os.path.join(BASE_DIR, "logs_vigia.txt")
LOG_SISTEMA_PATH = os.path.join(BASE_DIR, "logs_sistema.txt")

# Asegurar archivos de logs
for lp in [LOG_ORQUESTADOR_PATH, LOG_VIGIA_PATH, LOG_SISTEMA_PATH]:
    if not os.path.exists(lp):
        try:
            with open(lp, "w", encoding="utf-8") as f:
                f.write(f"--- Log inicializado el {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        except Exception:
            pass

try:
    from flask import Flask, jsonify, request, render_template_string
    try:
        from flask_cors import CORS
    except ImportError:
        CORS = None
except Exception as e_imp:
    try:
        with open("error_panel_critico.txt", "w", encoding="utf-8") as f:
            f.write("Error al importar Flask: " + str(e_imp))
    except Exception:
        pass
    raise

import database
import route_builder

try:
    import pytz
except ImportError:
    pytz = None

app = Flask(__name__)
if CORS:
    try:
        CORS(app)
    except Exception:
        pass

LOG_BUFFER = deque(maxlen=400)
_log_lock = threading.Lock()


def cargar_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def normalizar_id(texto: str) -> str:
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    return re.sub(r"[\s-]+", "_", texto)


def registrar_log_sistema(mensaje: str, nivel: str = "INFO"):
    """Registra en memoria y en logs_sistema.txt con rotación preventiva."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entrada = {
        "timestamp": ts,
        "mensaje": mensaje.strip(),
        "nivel": nivel.upper(),
    }
    with _log_lock:
        LOG_BUFFER.append(entrada)
    linea = f"[{ts}] [{nivel.upper()}] {mensaje.strip()}\n"
    try:
        with open(LOG_SISTEMA_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(linea)
    except Exception:
        pass


class StdoutInterceptor:
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, original_stdout):
        self.original_stdout = original_stdout

    def write(self, s):
        try:
            if not s:
                return
            if self.original_stdout:
                try:
                    self.original_stdout.write(s)
                except TypeError:
                    try:
                        if isinstance(s, (bytes, bytearray)):
                            self.original_stdout.write(s.decode("utf-8", errors="replace"))
                        else:
                            self.original_stdout.write(str(s).encode("utf-8", errors="replace"))
                    except Exception:
                        pass
                except Exception:
                    pass

            if isinstance(s, (bytes, bytearray)):
                try:
                    texto = s.decode("utf-8", errors="replace")
                except Exception:
                    texto = str(s)
            else:
                texto = str(s)

            stripped = texto.strip()
            if stripped and len(stripped) > 1:
                if "GET /api/" in stripped or "GET /static/" in stripped:
                    return
                lvl = "ERROR" if "[!]" in stripped or "error" in stripped.lower() else ("SUCCESS" if "✅" in stripped or "éxito" in stripped.lower() else "INFO")
                registrar_log_sistema(stripped, lvl)
        except Exception:
            pass

    def flush(self):
        try:
            if self.original_stdout:
                self.original_stdout.flush()
        except Exception:
            pass


try:
    sys.stdout = StdoutInterceptor(sys.stdout)
    sys.stderr = StdoutInterceptor(sys.stderr)
except Exception:
    pass

registrar_log_sistema("Dashboard Web Activo en http://127.0.0.1:8000 (Modo Fantasma & Responsive)", "INFO")


def leer_ultimas_lineas_archivo(ruta: str, max_lineas: int = 150) -> List[Dict[str, str]]:
    if not os.path.exists(ruta):
        return [{"timestamp": "--:--:--", "mensaje": "[Log no iniciado aún]", "nivel": "INFO"}]
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            lineas = f.readlines()[-max_lineas:]
        resultado = []
        for l in lineas:
            txt = l.strip()
            if not txt:
                continue
            ts = "--:--:--"
            if txt.startswith("[") and "]" in txt:
                partes = txt.split("]", 2)
                ts = partes[0].replace("[", "")
            lvl = "ERROR" if "[!]" in txt or "error" in txt.lower() else ("SUCCESS" if "✅" in txt or "éxito" in txt.lower() else "INFO")
            resultado.append({"timestamp": ts, "mensaje": txt, "nivel": lvl})
        return resultado
    except Exception as e:
        return [{"timestamp": "--:--:--", "mensaje": f"Error leyendo {os.path.basename(ruta)}: {e}", "nivel": "ERROR"}]


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Panel de Control Web · Bot Universidad Online</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #07090e;
      --card-bg: #0f1422;
      --card-border: #1e293b;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.25);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --purple: #a855f7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      padding: 16px;
      line-height: 1.5;
    }
    @media (min-width: 768px) {
      body { padding: 24px; }
    }
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 14px;
    }
    .brand-title {
      font-size: 22px;
      font-weight: 800;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-badges-group {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .badge-status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-vigia-paused {
      background: rgba(245, 158, 11, 0.15);
      color: var(--warning);
      border-color: rgba(245, 158, 11, 0.3);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background-color: currentColor;
      border-radius: 50%;
      box-shadow: 0 0 8px currentColor;
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    .toolbar-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    @media (min-width: 640px) {
      .kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 14px 16px;
      transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover {
      transform: translateY(-2px);
      border-color: #334155;
    }
    .kpi-label {
      font-size: 11px;
      color: var(--text-muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .kpi-value {
      font-size: 24px;
      font-weight: 800;
      color: var(--text);
    }
    .controls-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      gap: 10px;
      flex-wrap: wrap;
    }
    .search-box {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 10px 14px;
      color: var(--text);
      font-size: 13px;
      width: 100%;
      max-width: 340px;
    }
    .search-box:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }
    .btn {
      background: #1e293b;
      color: #f1f5f9;
      border: 1px solid #334155;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .btn:hover { background: #334155; }
    .btn:active { transform: scale(0.98); }
    .btn-primary { background: #0284c7; border-color: #0369a1; color: white; }
    .btn-primary:hover { background: #0369a1; }
    .btn-danger { background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
    .btn-danger:hover { background: rgba(239, 68, 68, 0.3); color: white; }
    .btn-warning { background: rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.4); color: #fde68a; }
    .btn-warning:hover { background: rgba(245, 158, 11, 0.3); }
    .btn-success { background: rgba(16, 185, 129, 0.15); border-color: rgba(16, 185, 129, 0.4); color: #6ee7b7; }
    .btn-success:hover { background: rgba(16, 185, 129, 0.3); }
    .btn-purple { background: rgba(168, 85, 247, 0.15); border-color: rgba(168, 85, 247, 0.4); color: #d8b4fe; }
    .btn-purple:hover { background: rgba(168, 85, 247, 0.3); }

    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow-x: auto;
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
      min-width: 900px;
    }
    th {
      background: #131b2e;
      color: var(--text-muted);
      font-weight: 700;
      padding: 12px 14px;
      border-bottom: 1px solid var(--card-border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    td {
      padding: 12px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      vertical-align: middle;
    }
    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }
    .badge-estado {
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 11px;
      display: inline-block;
      white-space: nowrap;
    }
    .st-GRABANDO { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .st-COMPLETADA { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .st-PENDIENTE { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .st-OCULTA { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }
    .st-CANCELADO_MANUALMENTE { background: rgba(100, 116, 139, 0.2); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.3); }

    .action-group {
      display: flex;
      gap: 5px;
      flex-wrap: wrap;
      align-items: center;
    }
    .action-btn-sm {
      padding: 4px 7px;
      font-size: 11px;
      border-radius: 6px;
    }

    /* Consolas Virtuales Plegables (<details>/<summary>) */
    .consoles-section {
      display: flex;
      flex-direction: column;
      gap: 14px;
      margin-top: 10px;
    }
    .console-box {
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      transition: all 0.2s;
    }
    .console-box summary {
      padding: 12px 16px;
      background: #0e1526;
      font-weight: 700;
      font-size: 13px;
      color: #cbd5e1;
      cursor: pointer;
      user-select: none;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid transparent;
    }
    .console-box[open] summary {
      border-bottom: 1px solid var(--card-border);
    }
    .console-box summary:hover {
      background: #141e34;
      color: #38bdf8;
    }
    .console-body {
      padding: 12px;
      background: #04060a;
    }
    .console-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 11px;
      color: var(--text-muted);
    }
    .terminal-logs {
      background: #000000;
      border: 1px solid #1e293b;
      border-radius: 8px;
      height: 200px;
      overflow-y: auto;
      padding: 10px 12px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #cbd5e1;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .log-row { display: flex; gap: 8px; line-height: 1.4; word-break: break-word; }
    .log-time { color: #64748b; flex-shrink: 0; }
    .log-lvl-INFO { color: #38bdf8; }
    .log-lvl-SUCCESS { color: #34d399; }
    .log-lvl-ERROR { color: #f87171; }
    .log-lvl-WARN { color: #fbbf24; }

    /* Modales */
    .modal-backdrop {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding: 16px;
    }
    .modal-box {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 14px;
      padding: 22px;
      max-width: 480px;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
    }
    .modal-title { font-size: 16px; font-weight: 800; margin-bottom: 12px; color: #f8fafc; }
    .modal-body { font-size: 13px; color: var(--text-muted); margin-bottom: 18px; line-height: 1.6; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
    .form-group { margin-bottom: 12px; text-align: left; }
    .form-group label { display: block; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px; }
    .form-control {
      width: 100%;
      background: #090d16;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 8px 12px;
      color: #f8fafc;
      font-size: 13px;
    }
    .form-control:focus { outline: none; border-color: var(--accent); }
    .form-hint { font-size: 11px; color: #64748b; margin-top: 3px; }
  </style>
</head>
<body>

  <!-- Top Bar -->
  <div class="top-bar">
    <div class="brand-title">
      <span>🚀</span> Bot Universidad Online · Panel Web
    </div>
    <div class="status-badges-group">
      <div class="badge-status">
        <span class="pulse-dot"></span> Orquestador Activo (8000)
      </div>
      <div class="badge-status" id="badge-vigia">
        <span class="pulse-dot"></span> Vigía Activo
      </div>
      <a class="btn btn-primary" href="https://cursosfamiliaorellana-hue.github.io/universidad-online/" target="_blank">📱 App Web LMS</a>
    </div>
  </div>

  <!-- Barra de Acciones Globales (CRUD programador_manual.py) -->
  <div class="toolbar-actions">
    <button class="btn btn-primary" onclick="abrirModalHotmart()">➕ Programar Hotmart</button>
    <button class="btn btn-purple" onclick="abrirModalMentoria()">🎙️ Programar Mentoría</button>
    <button class="btn btn-danger" onclick="detenerGrabacionInmediata()">🛑 Freno Inmediato</button>
    <button class="btn btn-warning" id="btn-toggle-vigia" onclick="togglePausaVigia()">⏸️ Pausar Vigía Hoy</button>
    <button class="btn" onclick="abrirModalMentores()">👥 Mentores & Grupos</button>
    <button class="btn" onclick="escanearIngesta()">📥 Escanear Ingesta</button>
    <button class="btn" onclick="auditarRescatar()">🔍 Auditar & Rescatar</button>
    <button class="btn" onclick="regenerarAppWeb()">🔄 Sincronizar Web</button>
  </div>

  <!-- KPIs Operativos -->
  <div class="kpi-grid">
    <div class="kpi-card" onclick="cargarDatos()" style="cursor: pointer;" title="Clic para ver todas las clases">
      <div class="kpi-label">TOTAL CLASES</div>
      <div class="kpi-value" id="kpi-total">0</div>
    </div>
    <div class="kpi-card" onclick="filtrarPorEstado('GRABANDO')" style="cursor: pointer;" title="Clic para filtrar clases grabando en vivo">
      <div class="kpi-label">🔴 GRABANDO AHORA</div>
      <div class="kpi-value" id="kpi-grabando" style="color: #f87171;">0</div>
    </div>
    <div class="kpi-card" onclick="filtrarPorEstado('COMPLETADA')" style="cursor: pointer;" title="Clic para filtrar clases completadas en Telegram y Web">
      <div class="kpi-label">✅ EN TELEGRAM & WEB</div>
      <div class="kpi-value" id="kpi-completadas" style="color: #34d399;">0</div>
    </div>
    <div class="kpi-card" onclick="filtrarHoy()" style="cursor: pointer;" title="Clic para ver el cronograma de hoy y pendientes">
      <div class="kpi-label">⏳ PENDIENTES / CRONOGRAMA</div>
      <div class="kpi-value" id="kpi-pendientes" style="color: #fbbf24;">0</div>
    </div>
    <div class="kpi-card" onclick="abrirModalMentores()" style="cursor: pointer;" title="Clic para gestionar mentores y grupos">
      <div class="kpi-label">🎙️ MENTORES REGISTRADOS</div>
      <div class="kpi-value" id="kpi-mentores" style="color: #c084fc;">0</div>
    </div>
  </div>

  <!-- Controles de Filtro -->
  <div class="controls-bar">
    <input type="text" class="search-box" id="filtroTexto" placeholder="🔍 Buscar por título, mentor o ID..." oninput="filtrarTabla()">
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <button class="btn btn-warning" onclick="filtrarHoy()">📅 Ver Cronograma de Hoy / Pendientes</button>
      <button class="btn" onclick="cargarDatos()">🔄 Ver Todas / Refrescar</button>
    </div>
  </div>

  <!-- Tabla de Clases -->
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Fecha / ID</th>
          <th>Título de la Masterclass</th>
          <th>Mentor / Transversal</th>
          <th>Estado</th>
          <th>Enlaces</th>
          <th>Acciones de Control & Borrado Granular</th>
        </tr>
      </thead>
      <tbody id="tabla-clases">
        <tr><td colspan="6" style="text-align: center; color: #64748b; padding: 24px;">Cargando clases registradas...</td></tr>
      </tbody>
    </table>
  </div>

  <!-- Consolas Virtuales Plegables (<details>/<summary>) -->
  <div class="consoles-section">
    <!-- Consola 1: Orquestador -->
    <details class="console-box" id="sec-orquestador" open>
      <summary>
        <span>⚡ Consola 1: Orquestador en Vivo (main.py)</span>
        <span style="font-size: 11px; color: #38bdf8;">logs_orquestador.txt ▼</span>
      </summary>
      <div class="console-body">
        <div class="console-toolbar">
          <label><input type="checkbox" id="chk-auto-orq" checked> Auto-Scroll</label>
          <div>
            <button class="btn action-btn-sm" onclick="cargarLogArchivo('orquestador')">🔄 Recargar</button>
            <button class="btn action-btn-sm" onclick="limpiarLogArchivo('orquestador')">🧹 Limpiar</button>
          </div>
        </div>
        <div class="terminal-logs" id="terminal-orquestador"></div>
      </div>
    </details>

    <!-- Consola 2: Vigía Telegram -->
    <details class="console-box" id="sec-vigia">
      <summary>
        <span>🦅 Consola 2: Vigía Telegram & Voice Chats (vigia_mentorias.py)</span>
        <span style="font-size: 11px; color: #a855f7;">logs_vigia.txt ▼</span>
      </summary>
      <div class="console-body">
        <div class="console-toolbar">
          <label><input type="checkbox" id="chk-auto-vigia" checked> Auto-Scroll</label>
          <div>
            <button class="btn action-btn-sm" onclick="cargarLogArchivo('vigia')">🔄 Recargar</button>
            <button class="btn action-btn-sm" onclick="limpiarLogArchivo('vigia')">🧹 Limpiar</button>
          </div>
        </div>
        <div class="terminal-logs" id="terminal-vigia"></div>
      </div>
    </details>

    <!-- Consola 3: Sistema & Dashboard -->
    <details class="console-box" id="sec-sistema">
      <summary>
        <span>🖥️ Consola 3: Sistema Web & Dashboard (dashboard_web.py)</span>
        <span style="font-size: 11px; color: #10b981;">logs_sistema.txt ▼</span>
      </summary>
      <div class="console-body">
        <div class="console-toolbar">
          <label><input type="checkbox" id="chk-auto-sis" checked> Auto-Scroll</label>
          <div>
            <button class="btn action-btn-sm" onclick="cargarLogArchivo('sistema')">🔄 Recargar</button>
            <button class="btn action-btn-sm" onclick="limpiarLogArchivo('sistema')">🧹 Limpiar</button>
          </div>
        </div>
        <div class="terminal-logs" id="terminal-sistema"></div>
      </div>
    </details>
  </div>

  <!-- MODAL: Programar Hotmart -->
  <div class="modal-backdrop" id="modal-hotmart">
    <div class="modal-box">
      <div class="modal-title">➕ Programar Masterclass de Hotmart</div>
      <div class="form-group">
        <label>Título o Nombre de la Clase</label>
        <input type="text" class="form-control" id="hm-nombre" placeholder="Ej: Lanzamiento 100K">
      </div>
      <div class="form-group">
        <label>URL de Hotmart (Opcional si usa búsqueda inteligente)</label>
        <input type="text" class="form-control" id="hm-url" placeholder="https://consumer.hotmart.com/...">
      </div>
      <div class="form-group">
        <label>¿Está dividida en partes (Parte 1, 2, 3...)?</label>
        <select class="form-control" id="hm-es-multi" onchange="document.getElementById('hm-num-parte-div').style.display = this.value === 'si' ? 'block' : 'none'">
          <option value="no">No, es una sola parte</option>
          <option value="si">Sí, está dividida en partes</option>
        </select>
      </div>
      <div class="form-group" id="hm-num-parte-div" style="display: none;">
        <label>Número de Parte</label>
        <input type="number" class="form-control" id="hm-num-parte" value="1" min="1">
      </div>
      <div class="form-group">
        <label>Hora de Inicio (formato 24h ej. '15:30' o escribe 'ahora')</label>
        <input type="text" class="form-control" id="hm-horario" value="ahora">
        <div class="form-hint">Si la hora ya pasó hoy, se programará automáticamente para mañana.</div>
      </div>
      <div class="form-group">
        <label>Duración Estimada (Minutos)</label>
        <input type="number" class="form-control" id="hm-duracion" value="60" min="5">
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="cerrarModales()">Cancelar</button>
        <button class="btn btn-primary" onclick="guardarProgramacionHotmart()">Agendar Masterclass</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Programar Mentoría -->
  <div class="modal-backdrop" id="modal-mentoria">
    <div class="modal-box">
      <div class="modal-title">🎙️ Programar o Iniciar Mentoría</div>
      <div class="form-group">
        <label>Tema de la Mentoría</label>
        <input type="text" class="form-control" id="ment-tema" placeholder="Ej: Estrategia de Cierres de Alto Valor">
      </div>
      <div class="form-group">
        <label>Enlace de Zoom o Tipo de Llamada</label>
        <input type="text" class="form-control" id="ment-enlace" value="chat_voz_telegram">
        <div class="form-hint">Deja 'chat_voz_telegram' para llamadas de voz o pega el link de Zoom.</div>
      </div>
      <div class="form-group">
        <label>Hora de Inicio ('ahora' o formato '20:00')</label>
        <input type="text" class="form-control" id="ment-horario" value="ahora">
      </div>
      <div class="form-group">
        <label>Duración Estimada (Minutos)</label>
        <input type="number" class="form-control" id="ment-duracion" value="180" min="10">
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="cerrarModales()">Cancelar</button>
        <button class="btn btn-purple" onclick="guardarProgramacionMentoria()">Agendar Mentoría</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Modificar Mentor (Efecto Dominó) -->
  <div class="modal-backdrop" id="modal-mentor-domino">
    <div class="modal-box">
      <div class="modal-title">✏️ Modificar Mentor ("Efecto Dominó")</div>
      <div class="modal-body" id="modal-domino-info"></div>
      <input type="hidden" id="domino-id-clase">
      <div class="form-group">
        <label>Nombre Real del Mentor</label>
        <input type="text" class="form-control" id="domino-nuevo-mentor" placeholder="Ej: Vinicius Loureiro">
        <div class="form-hint">Se actualizará el archivo MP4 local, la Base de Datos SQLite, el post de Telegram y la App Web LMS.</div>
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="cerrarModales()">Cancelar</button>
        <button class="btn btn-primary" onclick="ejecutarEfectoDomino()">Aplicar Efecto Dominó</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Gestión de Mentores y Grupos -->
  <div class="modal-backdrop" id="modal-mentores-gestion">
    <div class="modal-box" style="max-width: 600px;">
      <div class="modal-title">👥 Gestión de Mentores y Canales de Telegram</div>
      <div style="margin-bottom: 16px;">
        <div style="font-weight: 700; font-size: 12px; color: #38bdf8; margin-bottom: 6px;">Añadir Nuevo Mentor o Canal</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;">
          <input type="text" class="form-control" id="mgr-nombre" placeholder="Nombre Mentor o Canal">
          <input type="text" class="form-control" id="mgr-palabra" placeholder="Palabra Clave / ID Grupo">
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;">
          <input type="text" class="form-control" id="mgr-especialidad" placeholder="Especialidad (ej. Tráfico)">
          <select class="form-control" id="mgr-tipo">
            <option value="MENTOR">Mentor Individual</option>
            <option value="GENERAL">Canal/Grupo General</option>
          </select>
        </div>
        <button class="btn btn-success action-btn-sm" onclick="agregarMentorGrupo()">➕ Registrar Mentor/Grupo</button>
      </div>
      <div style="border-top: 1px solid #1e293b; padding-top: 12px;">
        <div style="font-weight: 700; font-size: 12px; color: #94a3b8; margin-bottom: 8px;">Mentores y Canales Activos</div>
        <div id="lista-mentores-grupos" style="max-height: 200px; overflow-y: auto; font-size: 12px;"></div>
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="cerrarModales()">Cerrar</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Confirmación de Acciones de Borrado -->
  <div class="modal-backdrop" id="modal-confirm-accion">
    <div class="modal-box">
      <div class="modal-title" id="confirm-titulo">⚠️ Confirmar Acción</div>
      <div class="modal-body" id="confirm-mensaje"></div>
      <div class="modal-actions">
        <button class="btn" onclick="cerrarModales()">Cancelar</button>
        <button class="btn btn-danger" id="btn-confirm-proceder">Confirmar</button>
      </div>
    </div>
  </div>

  <script>
    let TODAS_LAS_CLASES = [];
    let VIGIA_PAUSADO = false;

    async function cargarDatos() {
      try {
        const [resClases, resVigia] = await Promise.all([
          fetch('/api/clases'),
          fetch('/api/vigia/estado')
        ]);
        if (resClases.ok) {
          TODAS_LAS_CLASES = await resClases.json();
          renderTabla(TODAS_LAS_CLASES);
          actualizarKPIs();
        }
        if (resVigia.ok) {
          const vigiaData = await resVigia.json();
          VIGIA_PAUSADO = vigiaData.pausado;
          const badge = document.getElementById('badge-vigia');
          const btn = document.getElementById('btn-toggle-vigia');
          if (VIGIA_PAUSADO) {
            badge.className = 'badge-status badge-vigia-paused';
            badge.innerHTML = `<span class="pulse-dot"></span> ⏸️ Vigía Pausado (${vigiaData.limite_pausa || 'Hoy'})`;
            btn.className = 'btn btn-success';
            btn.textContent = '▶️ Reanudar Vigía';
          } else {
            badge.className = 'badge-status';
            badge.innerHTML = `<span class="pulse-dot"></span> 🟢 Vigía Activo`;
            btn.className = 'btn btn-warning';
            btn.textContent = '⏸️ Pausar Vigía Hoy';
          }
        }
      } catch (e) {
        console.error('Error cargando datos:', e);
      }
    }

    function actualizarKPIs() {
      const total = TODAS_LAS_CLASES.length;
      const grabando = TODAS_LAS_CLASES.filter(c => c.estado === 'GRABANDO').length;
      const comp = TODAS_LAS_CLASES.filter(c => c.estado === 'COMPLETADA').length;
      const pend = TODAS_LAS_CLASES.filter(c => c.estado === 'PENDIENTE' || c.regrabacion_activa == 1).length;
      const mentoresSet = new Set(TODAS_LAS_CLASES.map(c => c.mentor_identificado).filter(Boolean));

      document.getElementById('kpi-total').textContent = total;
      document.getElementById('kpi-grabando').textContent = grabando;
      document.getElementById('kpi-completadas').textContent = comp;
      document.getElementById('kpi-pendientes').textContent = pend;
      document.getElementById('kpi-mentores').textContent = mentoresSet.size;
    }

    function renderTabla(clases) {
      const tbody = document.getElementById('tabla-clases');
      if (clases.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #64748b; padding: 24px;">No hay clases registradas.</td></tr>';
        return;
      }

      tbody.innerHTML = clases.map(c => {
        const esGrabando = c.estado === 'GRABANDO';
        const esRegrab = c.regrabacion_activa == 1;
        const estadoLabel = esRegrab ? 'RE-GRABACIÓN' : c.estado;
        const claseBadge = esRegrab ? 'st-PENDIENTE' : ('st-' + (c.estado || 'PENDIENTE'));
        const tgLink = c.telegram_url || c.telegram_web_url;
        const nlmLink = c.notebook_url;
        const tieneVideoLocal = !!c.ruta_archivo;

        return `
          <tr>
            <td>
              <div style="font-weight: 700; color: #f1f5f9;">${(c.fecha_grabacion || '-').substring(0, 16).replace('T', ' ')}</div>
              <div style="font-size: 11px; color: #64748b; font-family: monospace;">${c.id_clase}</div>
            </td>
            <td>
              <div style="font-weight: 600; color: #e2e8f0;">${c.titulo_original}</div>
              <div style="font-size: 11px; color: #94a3b8;">${tieneVideoLocal ? '📁 ' + c.ruta_archivo.split(/[\\\\/]/).pop() : '☁️ Solo en Nube (Video purgado)'}</div>
            </td>
            <td>
              <div style="color: #38bdf8; font-weight: 600;">${c.mentor_identificado || 'General'}</div>
              <div style="font-size: 11px; color: #64748b;">${c.transversal || 'General'}</div>
            </td>
            <td>
              <span class="badge-estado ${claseBadge}">${estadoLabel}</span>
            </td>
            <td>
              <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                ${tgLink ? `<a class="btn btn-success action-btn-sm" href="${tgLink}" target="_blank">🎬 TG</a>` : '<span style="color: #475569; font-size: 11px;">TG Pend.</span>'}
                ${nlmLink ? `<a class="btn btn-purple action-btn-sm" href="${nlmLink}" target="_blank">🧠 NLM</a>` : ''}
              </div>
            </td>
            <td>
              <div class="action-group">
                ${esGrabando ? `<button class="btn btn-danger action-btn-sm" onclick="hotCancel('${c.id_clase}')">🛑 Cancelar</button>` : ''}
                <button class="btn btn-warning action-btn-sm" onclick="regrabarSeguro('${c.id_clase}')">🔁 Re-grabar</button>
                <button class="btn btn-primary action-btn-sm" onclick="forzarSubida('${c.id_clase}')">🚀 Subir TG</button>
                <button class="btn action-btn-sm" onclick="abrirModalDomino('${c.id_clase}', '${c.titulo_original.replace(/'/g, "\\\\'")}', '${c.mentor_identificado || ''}')">✏️ Mentor</button>
                <button class="btn action-btn-sm" onclick="toggleVisibilidadWeb('${c.id_clase}', ${c.estado === 'OCULTA'})">${c.estado === 'OCULTA' ? '👁️ Mostrar' : '👁️ Ocultar'}</button>
                
                <!-- 3 Botones Independientes de Gestión de Borrado -->
                <button class="btn btn-danger action-btn-sm" title="Elimina el MP4 local, preserva Telegram y Web" onclick="confirmarBorrarVideoLocal('${c.id_clase}', '${c.titulo_original.replace(/'/g, "\\\\'")}')">🗑️ Video Local</button>
                <button class="btn btn-danger action-btn-sm" title="Elimina resúmenes y material IA local" onclick="confirmarBorrarMaterialIA('${c.id_clase}', '${c.titulo_original.replace(/'/g, "\\\\'")}')">🗑️ Material IA</button>
                <button class="btn btn-danger action-btn-sm" title="Elimina de la base de datos y Web (NUNCA de Telegram)" onclick="confirmarEliminarSistema('${c.id_clase}', '${c.titulo_original.replace(/'/g, "\\\\'")}')">🗑️ Eliminar Clase</button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function filtrarTabla() {
      const q = document.getElementById('filtroTexto').value.toLowerCase();
      const filtradas = TODAS_LAS_CLASES.filter(c => {
        return (c.titulo_original && c.titulo_original.toLowerCase().includes(q)) ||
               (c.id_clase && c.id_clase.toLowerCase().includes(q)) ||
               (c.mentor_identificado && c.mentor_identificado.toLowerCase().includes(q)) ||
               (c.transversal && c.transversal.toLowerCase().includes(q));
      });
      renderTabla(filtradas);
    }

    function filtrarHoy() {
      const hoy = new Date();
      const aaaa = hoy.getFullYear();
      const mm = String(hoy.getMonth() + 1).padStart(2, '0');
      const dd = String(hoy.getDate()).padStart(2, '0');
      const hoyISO = `${aaaa}-${mm}-${dd}`;
      const hoySlash = `${dd}/${mm}/${aaaa}`;

      const filtradas = TODAS_LAS_CLASES.filter(c => {
        const f = c.fecha_grabacion || '';
        const esHoy = f.includes(hoyISO) || f.includes(hoySlash);
        const esPendiente = c.estado === 'PENDIENTE' || c.estado === 'GRABANDO' || c.regrabacion_activa == 1;
        return esHoy || esPendiente;
      });
      renderTabla(filtradas);
    }

    function filtrarPorEstado(estadoFiltro) {
      const filtradas = TODAS_LAS_CLASES.filter(c => c.estado === estadoFiltro);
      renderTabla(filtradas);
    }

    // Acciones de Borrado Granular
    function confirmarBorrarVideoLocal(idClase, titulo) {
      abrirModalConfirmacion(
        '🗑️ Borrar SOLO Video Local',
        `¿Deseas eliminar físicamente el video pesado (.mp4/.webm) de "${titulo}"? El enlace a Telegram y la ficha interactiva en la Web se mantendrán 100% disponibles.`,
        async () => {
          const res = await fetch('/api/clase/borrar_video_local', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id_clase: idClase})
          });
          const d = await res.json();
          alert(d.mensaje || 'Video local eliminado.');
          cargarDatos();
        }
      );
    }

    function confirmarBorrarMaterialIA(idClase, titulo) {
      abrirModalConfirmacion(
        '🗑️ Borrar Material IA Local',
        `¿Deseas purgar los archivos locales de IA (.md, .png, audios temporales) de "${titulo}"? La base de datos, los posts en Telegram y la App Web no se verán afectados.`,
        async () => {
          const res = await fetch('/api/clase/borrar_material_ia', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id_clase: idClase})
          });
          const d = await res.json();
          alert(d.mensaje || 'Material IA local purgado.');
          cargarDatos();
        }
      );
    }

    function confirmarEliminarSistema(idClase, titulo) {
      abrirModalConfirmacion(
        '💥 Eliminar Clase del Sistema',
        `¿Confirmas la eliminación total de "${titulo}" (ID: ${idClase}) de la base de datos y la App Web? NOTA: Tu publicación en Telegram permanecerá intacta (no se borra nada de la nube).`,
        async () => {
          const res = await fetch('/api/clase/eliminar_del_sistema', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id_clase: idClase})
          });
          const d = await res.json();
          alert(d.mensaje || 'Clase eliminada del sistema.');
          cargarDatos();
        }
      );
    }

    // Modal helpers
    function abrirModalConfirmacion(titulo, mensaje, onConfirm) {
      document.getElementById('confirm-titulo').textContent = titulo;
      document.getElementById('confirm-mensaje').textContent = mensaje;
      document.getElementById('btn-confirm-proceder').onclick = () => {
        cerrarModales();
        onConfirm();
      };
      document.getElementById('modal-confirm-accion').style.display = 'flex';
    }

    function cerrarModales() {
      document.querySelectorAll('.modal-backdrop').forEach(m => m.style.display = 'none');
    }

    // Detener Inmediata / Hot-Cancel
    async function detenerGrabacionInmediata() {
      if (!confirm('🛑 ¿Detener de inmediato cualquier grabación activa? El video grabado hasta el momento se guardará limpiamente.')) return;
      try {
        const res = await fetch('/api/detener_grabacion', { method: 'POST' });
        const d = await res.json();
        alert(d.mensaje || 'Señal de parada enviada.');
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function hotCancel(idClase) {
      if (!confirm('¿Abortar grabación en curso para esta clase? El material grabado se preservará.')) return;
      try {
        const res = await fetch('/api/hot_cancel', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id_clase: idClase})
        });
        const d = await res.json();
        alert(d.mensaje || 'Grabación cancelada.');
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function regrabarSeguro(idClase) {
      if (!confirm('Safe Overwrite: ¿Programar re-grabación? Los enlaces actuales se mantendrán hasta que finalice la nueva grabación.')) return;
      try {
        const res = await fetch('/api/regrabar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id_clase: idClase})
        });
        const d = await res.json();
        alert(d.mensaje || 'Re-grabación programada.');
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function forzarSubida(idClase) {
      try {
        const res = await fetch('/api/forzar_subida', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id_clase: idClase})
        });
        const d = await res.json();
        alert(d.mensaje || 'Subida iniciada en segundo plano.');
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function toggleVisibilidadWeb(idClase, actualmenteOculta) {
      try {
        const res = await fetch('/api/clase/cambiar_visibilidad', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id_clase: idClase, ocultar: !actualmenteOculta})
        });
        const d = await res.json();
        alert(d.mensaje || 'Visibilidad actualizada.');
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function togglePausaVigia() {
      const endpoint = VIGIA_PAUSADO ? '/api/vigia/reanudar' : '/api/vigia/pausar';
      try {
        const res = await fetch(endpoint, { method: 'POST' });
        const d = await res.json();
        alert(d.mensaje || 'Estado del vigía actualizado.');
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    // Modal Programar Hotmart
    function abrirModalHotmart() {
      document.getElementById('hm-nombre').value = '';
      document.getElementById('hm-url').value = '';
      document.getElementById('hm-es-multi').value = 'no';
      document.getElementById('hm-num-parte-div').style.display = 'none';
      document.getElementById('hm-horario').value = 'ahora';
      document.getElementById('hm-duracion').value = '60';
      document.getElementById('modal-hotmart').style.display = 'flex';
    }

    async function guardarProgramacionHotmart() {
      const nombre = document.getElementById('hm-nombre').value.trim();
      const url = document.getElementById('hm-url').value.trim();
      const esMulti = document.getElementById('hm-es-multi').value === 'si';
      const numParte = parseInt(document.getElementById('hm-num-parte').value) || 1;
      const horario = document.getElementById('hm-horario').value.trim() || 'ahora';
      const duracion = parseInt(document.getElementById('hm-duracion').value) || 60;

      if (!nombre && !url) {
        alert('Ingresa al menos un nombre o URL para identificar la clase.');
        return;
      }
      try {
        const res = await fetch('/api/programar_hotmart', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            nombre_base: nombre,
            url_hotmart: url,
            es_multi: esMulti,
            num_parte: numParte,
            horario: horario,
            duracion_min: duracion
          })
        });
        const d = await res.json();
        cerrarModales();
        alert(d.mensaje || 'Clase de Hotmart agendada con éxito.');
        cargarDatos();
      } catch (e) {
        alert('Error agendando Hotmart: ' + e);
      }
    }

    // Modal Programar Mentoría
    function abrirModalMentoria() {
      document.getElementById('ment-tema').value = '';
      document.getElementById('ment-enlace').value = 'chat_voz_telegram';
      document.getElementById('ment-horario').value = 'ahora';
      document.getElementById('ment-duracion').value = '180';
      document.getElementById('modal-mentoria').style.display = 'flex';
    }

    async function guardarProgramacionMentoria() {
      const tema = document.getElementById('ment-tema').value.trim() || 'Mentoría Estratégica';
      const enlace = document.getElementById('ment-enlace').value.trim() || 'chat_voz_telegram';
      const horario = document.getElementById('ment-horario').value.trim() || 'ahora';
      const duracion = parseInt(document.getElementById('ment-duracion').value) || 180;

      try {
        const res = await fetch('/api/programar_mentoria', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            tema: tema,
            enlace: enlace,
            horario: horario,
            duracion_min: duracion
          })
        });
        const d = await res.json();
        cerrarModales();
        alert(d.mensaje || 'Mentoría agendada con éxito.');
        cargarDatos();
      } catch (e) {
        alert('Error agendando mentoría: ' + e);
      }
    }

    // Efecto Dominó
    function abrirModalDomino(idClase, titulo, mentorActual) {
      document.getElementById('domino-id-clase').value = idClase;
      document.getElementById('domino-nuevo-mentor').value = mentorActual || '';
      document.getElementById('modal-domino-info').innerHTML = `Clase seleccionada: <strong>${titulo}</strong> (ID: <code>${idClase}</code>)`;
      document.getElementById('modal-mentor-domino').style.display = 'flex';
    }

    async function ejecutarEfectoDomino() {
      const idClase = document.getElementById('domino-id-clase').value;
      const nuevoMentor = document.getElementById('domino-nuevo-mentor').value.trim();
      if (!nuevoMentor) {
        alert('Ingresa el nombre del mentor.');
        return;
      }
      try {
        const res = await fetch('/api/mentor/renombrar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ id_clase: idClase, nuevo_mentor: nuevoMentor })
        });
        const d = await res.json();
        cerrarModales();
        alert(d.mensaje || 'Efecto Dominó aplicado con éxito.');
        cargarDatos();
      } catch (e) {
        alert('Error en Efecto Dominó: ' + e);
      }
    }

    // Modal Mentores
    async function abrirModalMentores() {
      document.getElementById('modal-mentores-gestion').style.display = 'flex';
      cargarListaMentores();
    }

    async function cargarListaMentores() {
      const cont = document.getElementById('lista-mentores-grupos');
      cont.innerHTML = '<span style="color: #64748b;">Cargando mentores...</span>';
      try {
        const res = await fetch('/api/mentores/listar');
        if (res.ok) {
          const mentores = await res.json();
          if (mentores.length === 0) {
            cont.innerHTML = '<span style="color: #64748b;">No hay mentores registrados.</span>';
            return;
          }
          cont.innerHTML = mentores.map(m => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #1e293b;">
              <div>
                <strong>${m.nombre_mentor}</strong> 
                <span style="color: #94a3b8;">(${m.especialidad})</span> - 
                <code>${m.palabra_clave_grupo}</code>
              </div>
              <button class="btn btn-danger action-btn-sm" onclick="desactivarMentor('${m.palabra_clave_grupo}')">Desactivar</button>
            </div>
          `).join('');
        }
      } catch (e) {
        cont.innerHTML = '<span style="color: #f87171;">Error cargando mentores.</span>';
      }
    }

    async function agregarMentorGrupo() {
      const nombre = document.getElementById('mgr-nombre').value.trim();
      const palabra = document.getElementById('mgr-palabra').value.trim();
      const especialidad = document.getElementById('mgr-especialidad').value.trim() || 'General';
      const tipo = document.getElementById('mgr-tipo').value;
      if (!nombre || !palabra) {
        alert('Nombre y palabra clave son obligatorios.');
        return;
      }
      try {
        const res = await fetch('/api/mentores/agregar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ nombre: nombre, palabra_clave: palabra, especialidad: especialidad, tipo: tipo })
        });
        const d = await res.json();
        alert(d.mensaje || 'Mentor registrado.');
        document.getElementById('mgr-nombre').value = '';
        document.getElementById('mgr-palabra').value = '';
        cargarListaMentores();
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function desactivarMentor(palabra) {
      if (!confirm(`¿Desactivar el grupo o mentor '${palabra}'?`)) return;
      try {
        const res = await fetch('/api/mentores/desactivar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ palabra_clave: palabra })
        });
        const d = await res.json();
        alert(d.mensaje || 'Mentor desactivado.');
        cargarListaMentores();
        cargarDatos();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    // Ingesta & Rescate
    async function escanearIngesta() {
      if (!confirm('¿Escanear carpetas de Ingesta_Manual y Playbooks_Externos en busca de material nuevo?')) return;
      try {
        const res = await fetch('/api/escanear_ingesta', { method: 'POST' });
        const d = await res.json();
        alert(d.mensaje || 'Escaneo de ingesta iniciado en segundo plano.');
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function auditarRescatar() {
      if (!confirm('¿Iniciar auditoría y rescate de videos y tareas incompletas en segundo plano?')) return;
      try {
        const res = await fetch('/api/auditar_rescatar', { method: 'POST' });
        const d = await res.json();
        alert(d.mensaje || 'Auditoría y rescate iniciados.');
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function regenerarAppWeb() {
      try {
        const res = await fetch('/api/regenerar_web', { method: 'POST' });
        const d = await res.json();
        alert(d.mensaje || 'App Web LMS sincronizada.');
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    // Streaming de Logs Plegables
    async function cargarLogArchivo(tipo) {
      const containerId = 'terminal-' + tipo;
      const chkId = tipo === 'orquestador' ? 'chk-auto-orq' : (tipo === 'vigia' ? 'chk-auto-vigia' : 'chk-auto-sis');
      try {
        const res = await fetch('/api/logs/' + tipo);
        if (res.ok) {
          const logs = await res.json();
          const terminal = document.getElementById(containerId);
          if (terminal) {
            terminal.innerHTML = logs.map(l => `
              <div class="log-row">
                <span class="log-time">[${l.timestamp}]</span>
                <span class="log-lvl-${l.nivel}">${l.mensaje}</span>
              </div>
            `).join('');
            const chk = document.getElementById(chkId);
            if (chk && chk.checked) {
              terminal.scrollTop = terminal.scrollHeight;
            }
          }
        }
      } catch (e) {
        console.error('Error cargando log ' + tipo, e);
      }
    }

    async function limpiarLogArchivo(tipo) {
      try {
        await fetch('/api/logs/limpiar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ tipo: tipo })
        });
        const terminal = document.getElementById('terminal-' + tipo);
        if (terminal) terminal.innerHTML = '';
      } catch (e) {
        alert('Error limpiando log: ' + e);
      }
    }

    function refrescarTodosLosLogs() {
      if (document.getElementById('sec-orquestador').open) cargarLogArchivo('orquestador');
      if (document.getElementById('sec-vigia').open) cargarLogArchivo('vigia');
      if (document.getElementById('sec-sistema').open) cargarLogArchivo('sistema');
    }

    // Inicialización y Polling
    cargarDatos();
    refrescarTodosLosLogs();
    setInterval(cargarDatos, 5000);
    setInterval(refrescarTodosLosLogs, 2500);
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/clases", methods=["GET"])
def api_clases():
    try:
        clases = database.listar_clases()
        return jsonify(clases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard_resumen", methods=["GET"])
def api_dashboard_resumen():
    try:
        resumen = database.obtener_resumen_dashboard()
        pausado, limite = database.obtener_estado_pausa_vigia()
        resumen["vigia_pausado"] = pausado
        resumen["vigia_limite"] = limite
        return jsonify(resumen)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs/<tipo>", methods=["GET"])
def api_get_logs(tipo):
    if tipo == "orquestador":
        return jsonify(leer_ultimas_lineas_archivo(LOG_ORQUESTADOR_PATH, 160))
    elif tipo == "vigia":
        return jsonify(leer_ultimas_lineas_archivo(LOG_VIGIA_PATH, 160))
    elif tipo == "sistema":
        return jsonify(leer_ultimas_lineas_archivo(LOG_SISTEMA_PATH, 160))
    return jsonify([])


@app.route("/api/logs/limpiar", methods=["POST"])
def api_limpiar_log():
    payload = request.get_json() or {}
    tipo = payload.get("tipo", "sistema")
    ruta = LOG_SISTEMA_PATH
    if tipo == "orquestador":
        ruta = LOG_ORQUESTADOR_PATH
    elif tipo == "vigia":
        ruta = LOG_VIGIA_PATH

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(f"--- Log limpiado el {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        return jsonify({"status": "ok", "mensaje": f"Log {tipo} limpiado."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- GESTIÓN GRANULAR DE BORRADO ---
@app.route("/api/clase/borrar_video_local", methods=["POST"])
def api_borrar_video_local():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    res = database.borrar_video_local_clase(id_clase)
    registrar_log_sistema(f"🗑️ [Borrado Video Local] {id_clase}: {res.get('mensaje')}", "WARN")
    return jsonify(res)


@app.route("/api/clase/borrar_material_ia", methods=["POST"])
def api_borrar_material_ia():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    res = database.borrar_material_ia_clase(id_clase)
    registrar_log_sistema(f"🗑️ [Borrado Material IA] {id_clase}: {res.get('mensaje')}", "WARN")
    return jsonify(res)


@app.route("/api/clase/eliminar_del_sistema", methods=["POST"])
def api_eliminar_del_sistema():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    res = database.eliminar_clase_sistema(id_clase)
    registrar_log_sistema(f"🗑️ [Eliminar del Sistema] {id_clase}: {res.get('mensaje')}", "WARN")
    return jsonify(res)


@app.route("/api/clase/cambiar_visibilidad", methods=["POST"])
def api_cambiar_visibilidad():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    ocultar = payload.get("ocultar", False)
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    database.cambiar_visibilidad_web_clase(id_clase, ocultar=ocultar)
    try:
        route_builder.generar_tablero_rutas(auto_deploy=True)
    except Exception:
        pass
    est = "OCULTA" if ocultar else "COMPLETADA"
    registrar_log_sistema(f"👁️ Visibilidad de {id_clase} cambiada a {est}", "INFO")
    return jsonify({"status": "ok", "mensaje": f"Visibilidad de {id_clase} actualizada a {est}."})


# --- ACCIONES DE CONTROL OPERATIVO ---
@app.route("/api/detener_grabacion", methods=["POST"])
def api_detener_grabacion():
    try:
        with open(ARCHIVO_FRENO_MANUAL, "w", encoding="utf-8") as f:
            f.write("STOP")
        registrar_log_sistema("🛑 [Freno Inmediato] Señal 'STOP' escrita en DETENER_GRABACION.txt.", "WARN")
        return jsonify({"status": "ok", "mensaje": "Señal de freno enviada. El grabador finalizará el video limpiamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hot_cancel", methods=["POST"])
def api_hot_cancel():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    database.cancelar_clase_manualmente(id_clase)
    with open(ARCHIVO_FRENO_MANUAL, "w", encoding="utf-8") as f:
        f.write("STOP")
    registrar_log_sistema(f"🛑 [Hot-Cancel] Cancelada en caliente: '{id_clase}'", "WARN")
    return jsonify({"status": "ok", "mensaje": f"Grabación cancelada para {id_clase}. Archivo parcial preservado."})


@app.route("/api/regrabar", methods=["POST"])
def api_regrabar():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    database.marcar_regrabacion_segura(id_clase)
    registrar_log_sistema(f"🔁 [Safe Overwrite] Re-grabación activada para: '{id_clase}'", "INFO")
    return jsonify({"status": "ok", "mensaje": f"Safe Overwrite activado para {id_clase}."})


def _worker_forzar_subida(id_clase: str):
    registrar_log_sistema(f"🚀 Iniciando forzado de subida a Telegram para '{id_clase}'...", "INFO")
    try:
        import telegram_uploader
        clase = database.obtener_clase(id_clase)
        if not clase:
            registrar_log_sistema(f"No se encontró la clase '{id_clase}' en la BD.", "ERROR")
            return
        ruta_video = clase.get("ruta_archivo")
        if not ruta_video or not os.path.exists(ruta_video):
            for root, _, files in os.walk(DIR_GRABACIONES):
                for f in files:
                    if id_clase.lower() in f.lower() and f.endswith(".mp4"):
                        ruta_video = os.path.join(root, f)
                        break
                if ruta_video:
                    break
        if not ruta_video or not os.path.exists(ruta_video):
            registrar_log_sistema(f"No se encontró archivo de video local para '{id_clase}'.", "ERROR")
            return
        analisis = {}
        if clase.get("analisis_json"):
            try:
                analisis = json.loads(clase["analisis_json"])
            except Exception:
                pass
        asyncio.run(telegram_uploader.subir_entrega_completa_telegram(
            ruta_video=ruta_video,
            titulo_clase=clase.get("titulo_original", "Masterclass"),
            fecha_clase=clase.get("fecha_grabacion", ""),
            duracion_min=clase.get("duracion_minutos", 60),
            analisis=analisis,
            notebook_url=clase.get("notebook_url"),
        ))
        route_builder.generar_tablero_rutas(auto_deploy=True)
        registrar_log_sistema(f"✅ Subida forzada completada para '{id_clase}'.", "SUCCESS")
    except Exception as e:
        registrar_log_sistema(f"Error forzando subida para '{id_clase}': {e}", "ERROR")


@app.route("/api/forzar_subida", methods=["POST"])
def api_forzar_subida():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400
    threading.Thread(target=_worker_forzar_subida, args=(id_clase,), daemon=True).start()
    return jsonify({"status": "ok", "mensaje": f"Subida a Telegram encolada para {id_clase}."})


# --- VIGÍA: PAUSAR / REANUDAR ---
@app.route("/api/vigia/estado", methods=["GET"])
def api_vigia_estado():
    pausado, limite = database.obtener_estado_pausa_vigia()
    return jsonify({"pausado": pausado, "limite_pausa": limite})


@app.route("/api/vigia/pausar", methods=["POST"])
def api_vigia_pausar():
    cfg = cargar_config()
    tz_nombre = cfg.get("timezone_local", "America/La_Paz")
    if pytz:
        tz = pytz.timezone(tz_nombre)
        ahora = datetime.datetime.now(tz)
    else:
        ahora = datetime.datetime.now()
    fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
    hasta_str = fin_dia.strftime("%Y-%m-%d %H:%M:%S")
    database.pausar_vigia_telegram(hasta_dt_str=hasta_str, motivo="Pausado desde Panel Web")
    registrar_log_sistema(f"⏸️ Vigía silenciado hasta: {hasta_str}", "WARN")
    return jsonify({"status": "ok", "mensaje": f"Vigía de Telegram pausado hasta las {hasta_str}."})


@app.route("/api/vigia/reanudar", methods=["POST"])
def api_vigia_reanudar():
    database.reanudar_vigia_telegram()
    registrar_log_sistema("▶️ Vigía de Telegram reanudado.", "SUCCESS")
    return jsonify({"status": "ok", "mensaje": "Vigía de Telegram reanudado exitosamente."})


# --- PROGRAMACIÓN DE HOTMART & MENTORÍAS ---
@app.route("/api/programar_hotmart", methods=["POST"])
def api_programar_hotmart():
    payload = request.get_json() or {}
    nombre_base = payload.get("nombre_base", "").strip()
    url_hotmart = payload.get("url_hotmart", "").strip()
    es_multi = payload.get("es_multi", False)
    num_parte = int(payload.get("num_parte", 1))
    horario_str = payload.get("horario", "ahora").strip().lower()
    duracion_min = int(payload.get("duracion_min", 60))

    if not nombre_base and url_hotmart:
        nombre_base = "Masterclass Hotmart"

    if es_multi:
        titulo_parte = f"{nombre_base} (Parte {num_parte})"
        id_parte = f"{normalizar_id(nombre_base)}_p{num_parte}"
        num_hotmart = num_parte
    else:
        titulo_parte = nombre_base
        id_parte = normalizar_id(nombre_base)
        num_hotmart = 0

    cfg = cargar_config()
    tz_nombre = cfg.get("timezone_local", "America/La_Paz")
    tz = pytz.timezone(tz_nombre) if pytz else None
    ahora = datetime.datetime.now(tz) if tz else datetime.datetime.now()

    if horario_str == "ahora":
        hora_inicio = ahora
    else:
        try:
            h, m = map(int, horario_str.split(":"))
            hora_inicio = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
            if hora_inicio < ahora - datetime.timedelta(minutes=5):
                hora_inicio += datetime.timedelta(days=1)
        except Exception:
            hora_inicio = ahora

    inicio_iso = hora_inicio.strftime("%Y-%m-%dT%H:%M:%S-04:00")
    analisis_json = json.dumps({"es_busqueda_inteligente": not bool(url_hotmart), "numero_parte_hotmart": num_hotmart})

    database.guardar_o_actualizar_clase(
        id_clase=id_parte,
        titulo_original=titulo_parte,
        fecha_grabacion=inicio_iso,
        estado="PENDIENTE",
        ruta_archivo="",
        url_hotmart=url_hotmart,
    )
    database.ejecutar_query(
        "UPDATE clases_grabadas SET duracion_min = ?, analisis_json = ? WHERE id_clase = ?",
        (duracion_min, analisis_json, id_parte),
    )
    registrar_log_sistema(f"📅 [Hotmart Agendada] '{titulo_parte}' para {hora_inicio.strftime('%H:%M')} ({duracion_min} min)", "SUCCESS")
    return jsonify({"status": "ok", "mensaje": f"Agendada: {titulo_parte} para las {hora_inicio.strftime('%H:%M')} ({duracion_min} min)."})


@app.route("/api/programar_mentoria", methods=["POST"])
def api_programar_mentoria():
    payload = request.get_json() or {}
    tema = payload.get("tema", "").strip() or "Mentoría Estratégica"
    enlace = payload.get("enlace", "").strip() or "chat_voz_telegram"
    horario_str = payload.get("horario", "ahora").strip().lower()
    duracion_min = int(payload.get("duracion_min", 180))

    cfg = cargar_config()
    tz_nombre = cfg.get("timezone_local", "America/La_Paz")
    tz = pytz.timezone(tz_nombre) if pytz else None
    ahora = datetime.datetime.now(tz) if tz else datetime.datetime.now()

    if horario_str == "ahora":
        hora_inicio = ahora
    else:
        try:
            h, m = map(int, horario_str.split(":"))
            hora_inicio = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
            if hora_inicio < ahora - datetime.timedelta(minutes=5):
                hora_inicio += datetime.timedelta(days=1)
        except Exception:
            hora_inicio = ahora

    id_clase = f"mentoria_{int(time.time())}"
    inicio_iso = hora_inicio.strftime("%Y-%m-%dT%H:%M:%S-04:00")
    fin_iso = (hora_inicio + datetime.timedelta(minutes=duracion_min)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

    database.guardar_o_actualizar_clase(id_clase, f"Mentoría: {tema}", inicio_iso, "PENDIENTE", "", enlace)
    database.ejecutar_query("UPDATE clases_grabadas SET duracion_min = ?, transversal = 'Mentorías' WHERE id_clase = ?", (duracion_min, id_clase))

    try:
        import calendar_sync
        calendar_sync.actualizar_estado_evento(id_clase, f"Mentoría: {tema}", "⏳ [Agendada]", inicio_iso, fin_iso, cfg)
    except Exception:
        pass

    registrar_log_sistema(f"🎙️ [Mentoría Agendada] 'Mentoría: {tema}' a las {hora_inicio.strftime('%H:%M')}", "SUCCESS")
    return jsonify({"status": "ok", "mensaje": f"Mentoría '{tema}' agendada para las {hora_inicio.strftime('%H:%M')}."})


# --- MODIFICAR MENTOR (EFECTO DOMINÓ) ---
@app.route("/api/mentor/renombrar", methods=["POST"])
def api_mentor_renombrar():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    nuevo_mentor = payload.get("nuevo_mentor", "").strip()
    if not id_clase or not nuevo_mentor:
        return jsonify({"error": "Faltan id_clase o nuevo_mentor"}), 400

    elegida = database.obtener_clase(id_clase)
    if not elegida:
        return jsonify({"error": f"No se encontró la clase '{id_clase}'"}), 404

    titulo_actual = elegida.get("titulo_original", "Mentoría")
    titulo_limpio = re.sub(r"\s*\(Mentor:.*?\)", "", titulo_actual, flags=re.IGNORECASE).strip()
    nuevo_titulo = f"{titulo_limpio} (Mentor: {nuevo_mentor})"

    ruta_actual = elegida.get("ruta_archivo") or ""
    nueva_ruta = ruta_actual
    if ruta_actual and os.path.exists(ruta_actual):
        try:
            carpeta = os.path.dirname(ruta_actual)
            slug = normalizar_id(nuevo_mentor)
            base_limpia = re.sub(r"_mentor_[a-z0-9_]+", "", os.path.splitext(os.path.basename(ruta_actual))[0])
            nueva_ruta = os.path.join(carpeta, f"{base_limpia}_mentor_{slug}.mp4")
            if nueva_ruta != ruta_actual:
                os.replace(ruta_actual, nueva_ruta)
        except Exception:
            pass

    analisis = {}
    if elegida.get("analisis_json"):
        try:
            analisis = json.loads(elegida["analisis_json"])
        except Exception:
            analisis = {}
    analisis["mentor_identificado"] = nuevo_mentor

    database.ejecutar_query(
        "UPDATE clases_grabadas SET titulo_original = ?, ruta_archivo = ?, analisis_json = ?, mentor = ? WHERE id_clase = ?",
        (nuevo_titulo, nueva_ruta, json.dumps(analisis, ensure_ascii=False), nuevo_mentor, id_clase),
    )

    tg_url = elegida.get("telegram_url") or ""
    if tg_url:
        try:
            import telegram_uploader
            asyncio.run(telegram_uploader.editar_caption_en_telegram(
                telegram_url=tg_url,
                nuevo_titulo=nuevo_titulo,
                fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),
                duracion_min=int(elegida.get("duracion_min") or 60),
                analisis=analisis,
            ))
        except Exception as e_tg:
            registrar_log_sistema(f"Aviso editando Telegram en efecto dominó: {e_tg}", "WARN")

    try:
        route_builder.generar_tablero_rutas(auto_deploy=True)
    except Exception:
        pass

    registrar_log_sistema(f"✏️ [Efecto Dominó] Mentor renombrado a '{nuevo_mentor}' en '{id_clase}'.", "SUCCESS")
    return jsonify({"status": "ok", "mensaje": f"Efecto dominó aplicado: {nuevo_titulo}. Base de datos, archivo y Web sincronizados."})


# --- MENTORES Y GRUPOS DE TELEGRAM ---
@app.route("/api/mentores/listar", methods=["GET"])
def api_mentores_listar():
    try:
        lista = database.listar_mentores_grupos()
        return jsonify(lista)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mentores/agregar", methods=["POST"])
def api_mentores_agregar():
    payload = request.get_json() or {}
    nombre = payload.get("nombre", "").strip()
    palabra = payload.get("palabra_clave", "").strip()
    esp = payload.get("especialidad", "General").strip()
    tipo = payload.get("tipo", "MENTOR").strip().upper()

    if not nombre or not palabra:
        return jsonify({"error": "Nombre y palabra clave son obligatorios"}), 400

    if tipo == "GENERAL":
        database.agregar_grupo_general(nombre, palabra, esp)
    else:
        database.agregar_o_actualizar_mentor_grupo(nombre, palabra, esp, tipo_grupo="MENTOR")

    try:
        route_builder.generar_tablero_rutas(auto_deploy=True)
    except Exception:
        pass

    registrar_log_sistema(f"👥 Mentor/Grupo '{nombre}' ({palabra}) registrado en el Vigía.", "SUCCESS")
    return jsonify({"status": "ok", "mensaje": f"Mentor o canal '{nombre}' vinculado correctamente al Vigía."})


@app.route("/api/mentores/desactivar", methods=["POST"])
def api_mentores_desactivar():
    payload = request.get_json() or {}
    palabra = payload.get("palabra_clave", "").strip()
    if not palabra:
        return jsonify({"error": "Falta palabra_clave"}), 400
    exito = database.desactivar_grupo_vigilado(palabra)
    if exito:
        try:
            route_builder.generar_tablero_rutas(auto_deploy=True)
        except Exception:
            pass
        registrar_log_sistema(f"👥 Grupo o mentor '{palabra}' desactivado del Vigía.", "INFO")
        return jsonify({"status": "ok", "mensaje": f"Grupo o mentor '{palabra}' desactivado."})
    return jsonify({"error": "No se encontró el registro activo"}), 404


# --- INGESTA MANUAL & RESCATE (BACKGROUND WORKERS) ---
def _worker_escanear_ingesta():
    registrar_log_sistema("📥 [Ingesta] Iniciando escaneo de Ingesta_Manual y Playbooks...", "INFO")
    try:
        carpetas = {
            "masterclasses": os.path.join(BASE_DIR, "Ingesta_Manual", "Masterclasses"),
            "mentorias": os.path.join(BASE_DIR, "Ingesta_Manual", "Mentorias"),
            "independientes": os.path.join(BASE_DIR, "Ingesta_Manual", "Grabaciones_Independientes"),
            "playbooks": os.path.join(BASE_DIR, "Playbooks_Externos"),
        }
        for c in carpetas.values():
            os.makedirs(c, exist_ok=True)

        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT ruta_archivo FROM ingesta_manual_registro")
            ya_ingestados = {r[0] for r in cur.fetchall()}
        finally:
            conn.close()

        import ai_analyzer
        import telegram_uploader

        formatos = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".m4a", ".wav", ".pdf", ".md", ".txt")
        procesados = 0

        for cat_clave, folder_path in carpetas.items():
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in formatos:
                        continue
                    ruta_completa = os.path.abspath(os.path.join(root, f))
                    if ruta_completa in ya_ingestados:
                        continue
                    nombre_sin_ext = os.path.splitext(f)[0].replace("_", " ").strip().title()
                    id_clase = f"ingesta_{cat_clave}_{normalizar_id(nombre_sin_ext)[:22]}_{int(time.time()) % 10000}"
                    registrar_log_sistema(f"📥 Procesando nuevo archivo de ingesta: '{f}'...", "INFO")

                    ruta_mp3 = ruta_completa if ext in (".mp3", ".m4a", ".wav") else None
                    if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
                        try:
                            ruta_mp3 = ai_analyzer.extraer_audio_ligero(ruta_completa)
                        except Exception:
                            ruta_mp3 = None

                    analisis = ai_analyzer.analizar_clase_con_gemini(nombre_sin_ext, ruta_mp3) or {
                        "transversal": "General",
                        "nivel": 1,
                        "resumen_didactico": f"Documento o clase ingestada: {nombre_sin_ext}.",
                        "flashcards": []
                    }

                    res_tg = {}
                    try:
                        res_tg = asyncio.run(telegram_uploader.subir_entrega_completa_telegram(
                            ruta_video=ruta_completa if ext in (".mp4", ".webm", ".pdf") else "",
                            titulo_clase=nombre_sin_ext,
                            fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),
                            duracion_min=60,
                            analisis=analisis,
                        ))
                    except Exception as e_tg:
                        registrar_log_sistema(f"Aviso subiendo a TG en ingesta: {e_tg}", "WARN")

                    tg_url = res_tg.get("telegram_url") if isinstance(res_tg, dict) else ""
                    database.guardar_o_actualizar_clase(
                        id_clase=id_clase,
                        titulo_original=nombre_sin_ext,
                        fecha_grabacion=datetime.datetime.now().isoformat(),
                        estado="COMPLETADA",
                        ruta_archivo=ruta_completa,
                        telegram_url=tg_url,
                    )
                    database.guardar_analisis_clase(id_clase, analisis)

                    conn_reg = database.get_connection()
                    try:
                        with conn_reg:
                            conn_reg.execute(
                                "INSERT OR IGNORE INTO ingesta_manual_registro (ruta_archivo, id_clase, carpeta_origen, fecha_ingesta) VALUES (?, ?, ?, ?)",
                                (ruta_completa, id_clase, cat_clave, datetime.datetime.now().isoformat())
                            )
                    finally:
                        conn_reg.close()

                    procesados += 1

        if procesados > 0:
            route_builder.generar_tablero_rutas(auto_deploy=True)
            registrar_log_sistema(f"🎉 Ingesta finalizada: {procesados} archivos nuevos incorporados.", "SUCCESS")
        else:
            registrar_log_sistema("✅ Escaneo de ingesta completado: No había archivos nuevos.", "INFO")
    except Exception as e:
        registrar_log_sistema(f"Error en escaneo de ingesta: {e}", "ERROR")


@app.route("/api/escanear_ingesta", methods=["POST"])
def api_escanear_ingesta():
    threading.Thread(target=_worker_escanear_ingesta, daemon=True).start()
    return jsonify({"status": "ok", "mensaje": "Escaneo de Ingesta Manual iniciado en segundo plano."})


def _worker_auditar_rescatar():
    registrar_log_sistema("🔍 [Auditoría] Escaneando procesos incompletos...", "INFO")
    try:
        clases = database.listar_clases()
        pendientes = []
        for c in clases:
            ruta = c.get("ruta_archivo") or ""
            tg = c.get("telegram_url") or c.get("telegram_app_url") or ""
            if ruta and os.path.exists(ruta) and not tg and os.path.getsize(ruta) > 2 * 1024 * 1024:
                pendientes.append(c)

        import telegram_uploader
        for c in pendientes:
            tit = c.get("titulo_original", "Clase")
            registrar_log_sistema(f"📤 Rescatando y subiendo a Telegram: '{tit}'...", "INFO")
            try:
                analisis = json.loads(c["analisis_json"]) if c.get("analisis_json") else {"transversal": "General", "nivel": 1, "resumen_didactico": tit}
                res_tg = asyncio.run(telegram_uploader.subir_entrega_completa_telegram(
                    ruta_video=c.get("ruta_archivo"),
                    titulo_clase=tit,
                    fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),
                    duracion_min=int(c.get("duracion_min") or 60),
                    analisis=analisis,
                ))
                tg_url = res_tg.get("telegram_url") if isinstance(res_tg, dict) else ""
                database.guardar_o_actualizar_clase(id_clase=c["id_clase"], titulo_original=tit, estado="COMPLETADA", telegram_url=tg_url)
                registrar_log_sistema(f"✅ '{tit}' rescatado y subido a Telegram.", "SUCCESS")
            except Exception as e_res:
                registrar_log_sistema(f"Error rescatando '{tit}': {e_res}", "ERROR")

        route_builder.generar_tablero_rutas(auto_deploy=True)
        registrar_log_sistema("🎉 Auditoría y rescate finalizados con éxito.", "SUCCESS")
    except Exception as e:
        registrar_log_sistema(f"Error en auditoría y rescate: {e}", "ERROR")


@app.route("/api/auditar_rescatar", methods=["POST"])
def api_auditar_rescatar():
    threading.Thread(target=_worker_auditar_rescatar, daemon=True).start()
    return jsonify({"status": "ok", "mensaje": "Auditoría y rescate de procesos iniciado en segundo plano."})


@app.route("/api/regenerar_web", methods=["POST"])
def api_regenerar_web():
    try:
        route_builder.generar_tablero_rutas(auto_deploy=True)
        registrar_log_sistema("✅ App Web LMS regenerada y sincronizada.", "SUCCESS")
        return jsonify({"status": "ok", "mensaje": "App Web LMS sincronizada correctamente con GitHub Pages."})
    except Exception as e:
        registrar_log_sistema(f"Error regenerando App Web: {e}", "ERROR")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    puerto = 8000
    print("\n" + "=" * 80)
    print(f"   PANEL DE CONTROL WEB - BOT UNIVERSIDAD ONLINE")
    print(f"   Acceso: http://127.0.0.1:{puerto}")
    print("=" * 80 + "\n")

    try:
        with open("flask_live.txt", "a") as f:
            f.write("Iniciando servidor Flask...\n")
        app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)
    except Exception as e:
        with open("flask_live.txt", "a") as f:
            f.write(f"ERROR FATAL: {str(e)}\n")
