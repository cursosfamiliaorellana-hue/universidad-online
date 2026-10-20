"""
dashboard_web.py - Panel de Control Web Interactivo para Universidad Online
Servidor Flask en puerto 8000 (http://127.0.0.1:8000)
Proporciona control en tiempo real: tabla de clases, streaming de logs,
Hot-Cancel, Re-grabación (Safe Overwrite), Forzar Subida y Borrado Seguro.
"""

import asyncio
from collections import deque
import datetime
import json
import os
import shutil
import sys
import threading
import time
import webbrowser
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, jsonify, request, render_template_string

import database
import route_builder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_GRABACIONES = os.path.join(BASE_DIR, "grabaciones")

app = Flask(__name__)

# Buffer circular en memoria para logs en vivo
LOG_BUFFER = deque(maxlen=400)
_log_lock = threading.Lock()


def registrar_log(mensaje: str, nivel: str = "INFO"):
    """Añade un mensaje con timestamp al buffer de logs web."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entrada = {
        "timestamp": ts,
        "mensaje": mensaje.strip(),
        "nivel": nivel.upper(),
    }
    with _log_lock:
        LOG_BUFFER.append(entrada)
    print(f"[{ts}] [{nivel}] {mensaje}")


class StdoutInterceptor:
    """Captura prints de consola para mostrarlos en el visor web sin perder salida original."""
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout

    def write(self, s):
        if self.original_stdout:
            self.original_stdout.write(s)
        stripped = s.strip()
        if stripped and len(stripped) > 1:
            # Filtrar accesos HTTP repetitivos de Flask
            if "GET /api/" in stripped or "GET /static/" in stripped:
                return
            lvl = "ERROR" if "[!]" in stripped or "error" in stripped.lower() else ("SUCCESS" if "✅" in stripped or "éxito" in stripped.lower() else "INFO")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with _log_lock:
                LOG_BUFFER.append({"timestamp": ts, "mensaje": stripped, "nivel": lvl})

    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()


# Interceptar stdout de forma no intrusiva
try:
    sys.stdout = StdoutInterceptor(sys.stdout)
except Exception:
    pass

registrar_log("Iniciando Dashboard Web de Universidad Online en http://127.0.0.1:8000...", "INFO")


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      padding: 24px;
      line-height: 1.5;
    }
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }
    .brand-title {
      font-size: 24px;
      font-weight: 800;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 10px;
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
    .pulse-dot {
      width: 8px;
      height: 8px;
      background-color: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--success);
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px;
      transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover {
      transform: translateY(-2px);
      border-color: #334155;
    }
    .kpi-label {
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 600;
      margin-bottom: 6px;
    }
    .kpi-value {
      font-size: 28px;
      font-weight: 800;
      color: var(--text);
    }
    .controls-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      gap: 12px;
      flex-wrap: wrap;
    }
    .search-box {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 10px 16px;
      color: var(--text);
      font-size: 14px;
      width: 320px;
      max-width: 100%;
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
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .btn:hover {
      background: #334155;
    }
    .btn-primary {
      background: #0284c7;
      border-color: #0369a1;
      color: white;
    }
    .btn-primary:hover {
      background: #0369a1;
    }
    .btn-danger {
      background: rgba(239, 68, 68, 0.15);
      border-color: rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.3);
      color: white;
    }
    .btn-warning {
      background: rgba(245, 158, 11, 0.15);
      border-color: rgba(245, 158, 11, 0.4);
      color: #fde68a;
    }
    .btn-warning:hover {
      background: rgba(245, 158, 11, 0.3);
    }
    .btn-success {
      background: rgba(16, 185, 129, 0.15);
      border-color: rgba(16, 185, 129, 0.4);
      color: #6ee7b7;
    }
    .btn-success:hover {
      background: rgba(16, 185, 129, 0.3);
    }
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      overflow-x: auto;
      margin-bottom: 24px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }
    th {
      background: #131b2e;
      color: var(--text-muted);
      font-weight: 700;
      padding: 14px 16px;
      border-bottom: 1px solid var(--card-border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      vertical-align: middle;
    }
    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }
    .badge-estado {
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 11px;
      display: inline-block;
    }
    .st-GRABANDO { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .st-COMPLETADA { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .st-PENDIENTE { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .st-CANCELADO_MANUALMENTE { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }
    .st-OVERLAP { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }

    .action-group {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .log-panel {
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px;
    }
    .log-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .log-title {
      font-size: 14px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
      color: #38bdf8;
    }
    .log-terminal {
      background: #04060a;
      border: 1px solid #1e293b;
      border-radius: 10px;
      height: 220px;
      overflow-y: auto;
      padding: 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #cbd5e1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .log-row {
      display: flex;
      gap: 8px;
    }
    .log-time { color: #64748b; flex-shrink: 0; }
    .log-lvl-INFO { color: #38bdf8; }
    .log-lvl-SUCCESS { color: #34d399; }
    .log-lvl-ERROR { color: #f87171; }
    .log-lvl-WARN { color: #fbbf24; }

    /* Modal */
    .modal-backdrop {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      align-items: center;
      justify-content: center;
      z-index: 9999;
    }
    .modal-box {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 24px;
      max-width: 440px;
      width: 90%;
      text-align: center;
    }
    .modal-title { font-size: 18px; font-weight: 700; margin-bottom: 10px; }
    .modal-body { font-size: 14px; color: var(--text-muted); margin-bottom: 20px; }
    .modal-actions { display: flex; justify-content: center; gap: 12px; }
  </style>
</head>
<body>

  <div class="top-bar">
    <div class="brand-title">
      <span>🚀</span> Bot Universidad Online · Panel de Control
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
      <div class="badge-status">
        <span class="pulse-dot"></span> Motor Activo (Puerto 8000)
      </div>
      <button class="btn btn-primary" onclick="regenerarAppWeb()">🔄 Sincronizar App Web LMS</button>
      <a class="btn" href="http://127.0.0.1:8080" target="_blank">📱 Ver App Celular</a>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">TOTAL CLASES REGISTRADAS</div>
      <div class="kpi-value" id="kpi-total">0</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">🔴 GRABANDO EN VIVO</div>
      <div class="kpi-value" id="kpi-grabando" style="color: #f87171;">0</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">✅ COMPLETADAS & EN TELEGRAM</div>
      <div class="kpi-value" id="kpi-completadas" style="color: #34d399;">0</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">⏳ PENDIENTES / RE-GRABACIÓN</div>
      <div class="kpi-value" id="kpi-pendientes" style="color: #fbbf24;">0</div>
    </div>
  </div>

  <div class="controls-bar">
    <input type="text" class="search-box" id="filtroTexto" placeholder="🔍 Buscar por título, mentor o ID..." oninput="filtrarTabla()">
    <div style="display: flex; gap: 8px;">
      <button class="btn" onclick="cargarClases()">🔄 Refrescar</button>
    </div>
  </div>

  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Fecha / ID</th>
          <th>Título de la Masterclass</th>
          <th>Mentor / Transversal</th>
          <th>Estado</th>
          <th>Enlaces</th>
          <th>Acciones Rápidas</th>
        </tr>
      </thead>
      <tbody id="tabla-clases">
        <tr><td colspan="6" style="text-align: center; color: #64748b;">Cargando clases...</td></tr>
      </tbody>
    </table>
  </div>

  <div class="log-panel">
    <div class="log-header">
      <div class="log-title">
        <span>⚡</span> Consola de Eventos y Logs en Vivo
      </div>
      <div>
        <label style="font-size: 12px; color: #94a3b8; margin-right: 12px;">
          <input type="checkbox" id="chk-autoscroll" checked> Auto-Scroll
        </label>
        <button class="btn" onclick="limpiarLogs()" style="padding: 4px 8px; font-size: 11px;">🧹 Limpiar</button>
      </div>
    </div>
    <div class="log-terminal" id="terminal-logs">
      <div class="log-row"><span class="log-time">--:--:--</span><span class="log-lvl-INFO">[Panel] Conectado al flujo de eventos...</span></div>
    </div>
  </div>

  <!-- Modal Borrado Seguro -->
  <div class="modal-backdrop" id="modal-borrado">
    <div class="modal-box">
      <div class="modal-title">⚠️ Confirmar Borrado Seguro</div>
      <div class="modal-body" id="modal-borrado-texto">
        ¿Estás seguro de que deseas eliminar físicamente esta clase y todos sus archivos asociados?
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="cerrarModalBorrado()">Cancelar</button>
        <button class="btn btn-danger" id="btn-confirmar-borrado">Sí, Borrado Físico</button>
      </div>
    </div>
  </div>

  <script>
    let TODAS_LAS_CLASES = [];
    let CLASE_A_BORRAR = null;

    async function cargarClases() {
      try {
        const res = await fetch('/api/clases');
        if (res.ok) {
          TODAS_LAS_CLASES = await res.json();
          actualizarKPIs();
          renderTabla(TODAS_LAS_CLASES);
        }
      } catch (err) {
        console.error('Error cargando clases:', err);
      }
    }

    function actualizarKPIs() {
      const total = TODAS_LAS_CLASES.length;
      const grabando = TODAS_LAS_CLASES.filter(c => c.estado === 'GRABANDO').length;
      const comp = TODAS_LAS_CLASES.filter(c => c.estado === 'COMPLETADA').length;
      const pend = TODAS_LAS_CLASES.filter(c => c.estado === 'PENDIENTE' || c.regrabacion_activa == 1).length;

      document.getElementById('kpi-total').textContent = total;
      document.getElementById('kpi-grabando').textContent = grabando;
      document.getElementById('kpi-completadas').textContent = comp;
      document.getElementById('kpi-pendientes').textContent = pend;
    }

    function renderTabla(clases) {
      const tbody = document.getElementById('tabla-clases');
      if (clases.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #64748b;">No hay clases registradas.</td></tr>';
        return;
      }

      tbody.innerHTML = clases.map(c => {
        const esGrabando = c.estado === 'GRABANDO';
        const esRegrab = c.regrabacion_activa == 1;
        const estadoLabel = esRegrab ? 'RE-GRABACIÓN PENDIENTE' : c.estado;
        const claseBadge = esRegrab ? 'st-PENDIENTE' : ('st-' + (c.estado || 'PENDIENTE'));
        const tgLink = c.telegram_url || c.telegram_web_url;

        return `
          <tr>
            <td>
              <div style="font-weight: 700; color: #f1f5f9;">${c.fecha_grabacion || '-'}</div>
              <div style="font-size: 11px; color: #64748b; font-family: monospace;">${c.id_clase}</div>
            </td>
            <td>
              <div style="font-weight: 600; color: #e2e8f0;">${c.titulo_original}</div>
              <div style="font-size: 11px; color: #94a3b8;">${c.ruta_archivo ? '📁 ' + c.ruta_archivo.split(/[\\\\/]/).pop() : '⏳ Sin archivo físico'}</div>
            </td>
            <td>
              <div style="color: #38bdf8; font-weight: 600;">${c.mentor_identificado || 'General'}</div>
              <div style="font-size: 11px; color: #64748b;">${c.transversal || 'General'}</div>
            </td>
            <td>
              <span class="badge-estado ${claseBadge}">${estadoLabel}</span>
            </td>
            <td>
              ${tgLink ? `<a class="btn btn-success" style="padding: 4px 8px; font-size: 11px;" href="${tgLink}" target="_blank">🎬 Telegram</a>` : '<span style="color: #475569; font-size: 11px;">Pendiente</span>'}
            </td>
            <td>
              <div class="action-group">
                ${esGrabando ? `
                  <button class="btn btn-danger" style="padding: 4px 8px; font-size: 11px;" onclick="hotCancel('${c.id_clase}')">🛑 Hot-Cancel</button>
                ` : ''}
                <button class="btn btn-warning" style="padding: 4px 8px; font-size: 11px;" onclick="regrabarSeguro('${c.id_clase}')">🔁 Re-grabar</button>
                <button class="btn btn-primary" style="padding: 4px 8px; font-size: 11px;" onclick="forzarSubida('${c.id_clase}')">🚀 Subir TG</button>
                <button class="btn btn-danger" style="padding: 4px 8px; font-size: 11px;" onclick="abrirModalBorrado('${c.id_clase}', '${c.titulo_original.replace(/'/g, "\\\\'")}')">🗑️</button>
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

    async function hotCancel(idClase) {
      if (!confirm('¿Deseas abortar de forma limpia la grabación en curso para esta clase? El material grabado hasta el momento se preservará.')) return;
      try {
        const res = await fetch('/api/hot_cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_clase: idClase })
        });
        const d = await res.json();
        alert(d.mensaje || 'Grabación cancelada limpiamente.');
        cargarClases();
      } catch (e) {
        alert('Error en Hot-Cancel: ' + e);
      }
    }

    async function regrabarSeguro(idClase) {
      if (!confirm('Safe Overwrite: ¿Programar re-grabación? Los videos y enlaces actuales se mantendrán intactos en la App Web hasta que la nueva grabación termine.')) return;
      try {
        const res = await fetch('/api/regrabar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_clase: idClase })
        });
        const d = await res.json();
        alert(d.mensaje || 'Re-grabación segura programada.');
        cargarClases();
      } catch (e) {
        alert('Error al programar re-grabación: ' + e);
      }
    }

    async function forzarSubida(idClase) {
      try {
        const res = await fetch('/api/forzar_subida', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_clase: idClase })
        });
        const d = await res.json();
        alert(d.mensaje || 'Subida iniciada en segundo plano.');
        cargarClases();
      } catch (e) {
        alert('Error al forzar subida: ' + e);
      }
    }

    function abrirModalBorrado(idClase, titulo) {
      CLASE_A_BORRAR = idClase;
      document.getElementById('modal-borrado-texto').textContent =
        `¿Confirmas la eliminación física total de "${titulo}" (ID: ${idClase})? Esta acción destruirá los archivos multimedia locales y su registro en la BD.`;
      document.getElementById('modal-borrado').style.display = 'flex';
      document.getElementById('btn-confirmar-borrado').onclick = ejecutarBorradoSeguro;
    }

    function cerrarModalBorrado() {
      document.getElementById('modal-borrado').style.display = 'none';
      CLASE_A_BORRAR = null;
    }

    async function ejecutarBorradoSeguro() {
      if (!CLASE_A_BORRAR) return;
      try {
        const res = await fetch('/api/borrado_seguro', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_clase: CLASE_A_BORRAR })
        });
        const d = await res.json();
        cerrarModalBorrado();
        alert(d.mensaje || 'Borrado seguro completado.');
        cargarClases();
      } catch (e) {
        alert('Error al borrar clase: ' + e);
      }
    }

    async function regenerarAppWeb() {
      try {
        const res = await fetch('/api/regenerar_web', { method: 'POST' });
        const d = await res.json();
        alert(d.mensaje || 'App Web sincronizada con éxito.');
      } catch (e) {
        alert('Error al regenerar App Web: ' + e);
      }
    }

    async function cargarLogs() {
      try {
        const res = await fetch('/api/logs');
        if (res.ok) {
          const logs = await res.json();
          const terminal = document.getElementById('terminal-logs');
          terminal.innerHTML = logs.map(l => `
            <div class="log-row">
              <span class="log-time">[${l.timestamp}]</span>
              <span class="log-lvl-${l.nivel}">${l.mensaje}</span>
            </div>
          `).join('');

          if (document.getElementById('chk-autoscroll').checked) {
            terminal.scrollTop = terminal.scrollHeight;
          }
        }
      } catch (e) {
        console.error('Error cargando logs:', e);
      }
    }

    function limpiarLogs() {
      fetch('/api/limpiar_logs', { method: 'POST' });
      document.getElementById('terminal-logs').innerHTML = '';
    }

    // Polling automático
    cargarClases();
    cargarLogs();
    setInterval(cargarClases, 5000);
    setInterval(cargarLogs, 2500);
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


@app.route("/api/logs", methods=["GET"])
def api_logs():
    with _log_lock:
        return jsonify(list(LOG_BUFFER))


@app.route("/api/limpiar_logs", methods=["POST"])
def api_limpiar_logs():
    with _log_lock:
        LOG_BUFFER.clear()
    return jsonify({"status": "ok"})


@app.route("/api/hot_cancel", methods=["POST"])
def api_hot_cancel():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400

    database.cancelar_clase_manualmente(id_clase)
    registrar_log(f"🛑 [Hot-Cancel] Grabación cancelada manualmente para: '{id_clase}'", "WARN")
    return jsonify({"status": "ok", "mensaje": f"Grabación cancelada limpiamente para {id_clase}. Archivos parciales preservados."})


@app.route("/api/regrabar", methods=["POST"])
def api_regrabar():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400

    database.marcar_regrabacion_segura(id_clase)
    registrar_log(f"🔁 [Safe Overwrite] Re-grabación diferida activada para: '{id_clase}'", "INFO")
    return jsonify({"status": "ok", "mensaje": f"Re-grabación segura activada para {id_clase}. Los datos anteriores se conservarán hasta finalizar la nueva."})


def _worker_forzar_subida(id_clase: str):
    """Ejecuta la subida de una clase en segundo plano."""
    registrar_log(f"🚀 Iniciando forzado de subida a Telegram para '{id_clase}'...", "INFO")
    try:
        import telegram_uploader
        clase = database.obtener_clase(id_clase)
        if not clase:
            registrar_log(f"No se encontró la clase '{id_clase}' en la base de datos.", "ERROR")
            return

        ruta_video = clase.get("ruta_archivo")
        if not ruta_video or not os.path.exists(ruta_video):
            # Intentar buscar en carpeta grabaciones
            for root, _, files in os.walk(DIR_GRABACIONES):
                for f in files:
                    if id_clase.lower() in f.lower() and f.endswith(".mp4"):
                        ruta_video = os.path.join(root, f)
                        break
                if ruta_video:
                    break

        if not ruta_video or not os.path.exists(ruta_video):
            registrar_log(f"No se encontró archivo de video local para '{id_clase}'.", "ERROR")
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
        registrar_log(f"✅ Subida forzada a Telegram completada para '{id_clase}'.", "SUCCESS")
    except Exception as e:
        registrar_log(f"Error forzando subida para '{id_clase}': {e}", "ERROR")


@app.route("/api/forzar_subida", methods=["POST"])
def api_forzar_subida():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400

    t = threading.Thread(target=_worker_forzar_subida, args=(id_clase,), daemon=True)
    t.start()
    return jsonify({"status": "ok", "mensaje": f"Subida a Telegram encolada en segundo plano para {id_clase}."})


@app.route("/api/borrado_seguro", methods=["POST"])
def api_borrado_seguro():
    payload = request.get_json() or {}
    id_clase = payload.get("id_clase")
    if not id_clase:
        return jsonify({"error": "Falta id_clase"}), 400

    database.eliminar_clase(id_clase)
    route_builder.generar_tablero_rutas(auto_deploy=False)
    registrar_log(f"🗑️ [Borrado Seguro] Clase eliminada físicamente: '{id_clase}'", "WARN")
    return jsonify({"status": "ok", "mensaje": f"Clase {id_clase} y archivos locales eliminados físicamente."})


@app.route("/api/regenerar_web", methods=["POST"])
def api_regenerar_web():
    try:
        route_builder.generar_tablero_rutas(auto_deploy=True)
        registrar_log("✅ App Web LMS regenerada y sincronizada.", "SUCCESS")
        return jsonify({"status": "ok", "mensaje": "App Web LMS regenerada y sincronizada correctamente."})
    except Exception as e:
        registrar_log(f"Error regenerando App Web: {e}", "ERROR")
        return jsonify({"error": str(e)}), 500


def abrir_navegador():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    puerto = 8000
    print("\n" + "=" * 80)
    print(f"   PANEL DE CONTROL WEB - BOT UNIVERSIDAD ONLINE")
    print(f"   Acceso: http://127.0.0.1:{puerto}")
    print("=" * 80 + "\n")

    threading.Thread(target=abrir_navegador, daemon=True).start()
    app.run(host="127.0.0.1", port=puerto, debug=False)
