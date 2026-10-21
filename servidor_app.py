"""
servidor_app.py - Servidor Web Local para App Web / PWA de Universidad Online
Sirve la plataforma web didáctica en la Red Local (Wi-Fi) permitiendo su visualización
e instalación en cualquier celular (Android / iOS) o computadora de la misma red.
"""

import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_WEB_DIR = os.path.join(BASE_DIR, "app_web")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
QR_HTML_FILE = os.path.join(BASE_DIR, "app_web", "qr_acceso.html")


def obtener_ip_local() -> str:
    """Detecta la IP local de la computadora en la red Wi-Fi o Ethernet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def encontrar_puerto_libre(puerto_inicial: int = 8080) -> int:
    """Busca un puerto libre a partir del puerto inicial."""
    puerto = puerto_inicial
    while puerto < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("0.0.0.0", puerto)) != 0:
                return puerto
            puerto += 1
    return 8080


class PWAHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Manejador HTTP que sirve app_web y añade encabezados correctos para Service Workers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Service-Worker-Allowed", "/")
        super().end_headers()

    def log_message(self, format, *args):
        pass


def iniciar_servidor_http(puerto: int) -> socketserver.TCPServer:
    """Inicia el servidor HTTP en un hilo secundario escuchando en todas las interfaces (0.0.0.0)."""
    server = socketserver.TCPServer(("0.0.0.0", puerto), PWAHTTPRequestHandler)
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    return server


def actualizar_config_url(url: str):
    """Guarda la URL local actual en config.json para los componentes del sistema."""
    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["pwa_local_url"] = url
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Aviso] No se pudo actualizar config.json: {e}")


def copiar_al_portapapeles(texto: str):
    """Copia la URL al portapapeles de Windows."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{texto}'"],
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


def generar_pagina_qr(url_acceso: str, ip_local: str, puerto: int) -> str:
    """Crea una página HTML con el Código QR de acceso instantáneo para celulares en la misma Wi-Fi."""
    url_enc = urllib.parse.quote(url_acceso)
    qr_img_api = f"https://api.qrserver.com/v1/create-qr-code/?size=360x360&margin=15&data={url_enc}"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Acceso Móvil Red Local - App Universidad Online</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      margin: 0;
      padding: 30px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 90vh;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 24px;
      padding: 32px;
      max-width: 460px;
      text-align: center;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5);
    }}
    h1 {{
      font-size: 1.5rem;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    p {{
      color: #94a3b8;
      font-size: 0.95rem;
      line-height: 1.4;
      margin-bottom: 24px;
    }}
    .qr-box {{
      background: #ffffff;
      padding: 16px;
      border-radius: 16px;
      display: inline-block;
      margin-bottom: 24px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    }}
    .qr-box img {{
      display: block;
      width: 280px;
      height: 280px;
    }}
    .link-box {{
      background: #090d16;
      border: 1px solid #3b82f6;
      border-radius: 12px;
      padding: 12px;
      word-break: break-all;
      font-family: monospace;
      font-size: 0.95rem;
      color: #60a5fa;
      margin-bottom: 16px;
    }}
    .btn {{
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 0.95rem;
      cursor: pointer;
      text-decoration: none;
      display: inline-block;
      transition: opacity 0.2s;
    }}
    .btn:hover {{ opacity: 0.9; }}
    .steps {{
      text-align: left;
      margin-top: 24px;
      border-top: 1px solid #334155;
      padding-top: 18px;
      font-size: 0.85rem;
      color: #cbd5e1;
    }}
    .steps li {{
      margin-bottom: 8px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>📱 App Web Universidad Online (Red Local)</h1>
    <p>Conéctate a la misma red Wi-Fi y escanea este código con tu celular:</p>
    
    <div class="qr-box">
      <img src="{qr_img_api}" alt="Código QR de Acceso Móvil" />
    </div>

    <div class="link-box">{url_acceso}</div>

    <button class="btn" onclick="navigator.clipboard.writeText('{url_acceso}').then(() => alert('¡Enlace copiado al portapapeles!'))">
      📋 Copiar Enlace
    </button>

    <div class="steps">
      <b>🚀 Acceso desde cualquier dispositivo en la misma red Wi-Fi:</b>
      <ul>
        <li><b>Computadora local:</b> <a href="http://127.0.0.1:{puerto}/" style="color: #38bdf8;">http://127.0.0.1:{puerto}/</a></li>
        <li><b>Celular / Tablet:</b> <a href="{url_acceso}" style="color: #38bdf8;">{url_acceso}</a></li>
        <li><b>Añadir a pantalla de inicio:</b> En Chrome ⋮ ➔ "Añadir a pantalla de inicio" o en Safari Compartir ➔ "Añadir a pantalla de inicio".</li>
      </ul>
    </div>
  </div>
</body>
</html>"""
    os.makedirs(os.path.dirname(QR_HTML_FILE), exist_ok=True)
    with open(QR_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    return QR_HTML_FILE


def ejecutar():
    print("=" * 80)
    print("   UNIVERSIDAD ONLINE - SERVIDOR APP WEB EN RED LOCAL (0.0.0.0)")
    print("=" * 80)

    # 1. Asegurar que existe app_web/index.html
    index_path = os.path.join(APP_WEB_DIR, "index.html")
    if not os.path.exists(index_path):
        import route_builder
        print("[*] Generando plataforma web didáctica inicial...")
        route_builder.generar_tablero_rutas()

    # 2. Iniciar Servidor Local en 0.0.0.0
    puerto = encontrar_puerto_libre(8080)
    ip_local = obtener_ip_local()
    url_local = f"http://{ip_local}:{puerto}/"
    url_loopback = f"http://127.0.0.1:{puerto}/"

    print(f"\n[1/2] Iniciando Servidor Web local en puerto {puerto}...")
    server = iniciar_servidor_http(puerto)
    print(f"      ✅ Servidor local activo en todas las interfaces (0.0.0.0:{puerto}).")
    print(f"      👉 Acceso PC local:      {url_loopback}")
    print(f"      👉 Acceso Celular Wi-Fi: {url_local}")

    actualizar_config_url(url_local)
    copiar_al_portapapeles(url_local)
    qr_file = generar_pagina_qr(url_local, ip_local, puerto)

    print("\n" + "=" * 80)
    print("   🎉 ¡APP WEB DISPONIBLE EN RED LOCAL! 🎉")
    print("=" * 80)
    print(f"\n   🔗 ENLACE PARA TU CELULAR (MISMA RED WI-FI):")
    print(f"      {url_local}\n")
    print(f"   📋 ¡El enlace ha sido copiado automáticamente a tu portapapeles!")
    print(f"   📷 Abriendo ventana con Código QR para escanear con la cámara...\n")
    print("   ℹ️  INSTRUCCIONES PARA TU CELULAR:")
    print("      1. Asegúrate de estar conectado a la misma red Wi-Fi de esta PC.")
    print("      2. Escanea el Código QR que se abrió en tu pantalla con la cámara.")
    print("      3. En el navegador (Chrome/Safari), pulsa 'Añadir a pantalla de inicio'.")
    print("=" * 80)
    print("   Presiona Ctrl + C en esta ventana cuando desees apagar el servidor.")
    print("=" * 80 + "\n")

    try:
        webbrowser.open(f"file:///{qr_file}")
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[Servidor] Deteniendo servidor web limpiamente...")
        server.shutdown()
        print("[Servidor] Servidor detenido. ¡Hasta la próxima!")


if __name__ == "__main__":
    ejecutar()
