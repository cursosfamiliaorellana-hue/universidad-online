"""
servidor_app.py - Servidor Web Local + Túnel HTTPS Gratuito (Cloudflare Tunnel)
Permite abrir e instalar la App Web / PWA de Universidad Online en cualquier celular
(Android / iOS) con HTTPS seguro, funcionamiento offline y sincronización en vivo.
"""

import http.server
import json
import os
import re
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
CLOUDFLARED_EXE = os.path.join(BASE_DIR, "cloudflared.exe")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
QR_HTML_FILE = os.path.join(BASE_DIR, "app_web", "qr_acceso.html")


def encontrar_puerto_libre(puerto_inicial: int = 8080) -> int:
    """Busca un puerto libre a partir del puerto inicial."""
    puerto = puerto_inicial
    while puerto < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
            puerto += 1
    return 8080


class PWAHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Manejador HTTP que sirve app_web y añade encabezados correctos para Service Workers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_WEB_DIR, **kwargs)

    def end_headers(self):
        # Permitir Service Workers y habilitar CORS
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Service-Worker-Allowed", "/")
        super().end_headers()

    def log_message(self, format, *args):
        # Silenciar logs ruidosos para mantener la consola limpia
        pass


def iniciar_servidor_http(puerto: int) -> socketserver.TCPServer:
    """Inicia el servidor HTTP en un hilo secundario."""
    server = socketserver.TCPServer(("127.0.0.1", puerto), PWAHTTPRequestHandler)
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    return server


def actualizar_config_url(url: str):
    """Guarda la URL pública actual en config.json para que los bots la conozcan."""
    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["pwa_public_url"] = url
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


def generar_pagina_qr(url_publica: str) -> str:
    """Crea una página HTML con el Código QR de acceso instantáneo."""
    url_enc = urllib.parse.quote(url_publica)
    qr_img_api = f"https://api.qrserver.com/v1/create-qr-code/?size=360x360&margin=15&data={url_enc}"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Acceso Móvil - App Universidad Online</title>
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
      max-width: 440px;
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
    <h1>📱 App Web Universidad Online</h1>
    <p>Escanea este código con la cámara de tu celular (Android o iPhone) para abrir la aplicación:</p>
    
    <div class="qr-box">
      <img src="{qr_img_api}" alt="Código QR de Acceso Móvil" />
    </div>

    <div class="link-box">{url_publica}</div>

    <button class="btn" onclick="navigator.clipboard.writeText('{url_publica}').then(() => alert('¡Enlace copiado al portapapeles!'))">
      📋 Copiar Enlace
    </button>

    <div class="steps">
      <b>🚀 Para instalarla en tu pantalla de inicio:</b>
      <ul>
        <li><b>Android (Chrome):</b> Toca el banner <i>"Instalar App"</i> o el menú ⋮ ➔ <i>"Añadir a pantalla de inicio"</i>.</li>
        <li><b>iPhone (Safari):</b> Toca el botón <i>Compartir</i> (icono de cuadrado con flecha hacia arriba) ➔ <i>"Añadir a pantalla de inicio"</i>.</li>
        <li><b>Modo Offline:</b> Una vez abierta, funcionará incluso si te quedas sin conexión a internet.</li>
      </ul>
    </div>
  </div>
</body>
</html>"""
    with open(QR_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    return QR_HTML_FILE


def ejecutar():
    print("=" * 80)
    print("   UNIVERSIDAD ONLINE - SERVIDOR APP WEB + TÚNEL HTTPS SEGURO (OPCIÓN B)")
    print("=" * 80)

    # 1. Asegurar que existe app_web/index.html
    index_path = os.path.join(APP_WEB_DIR, "index.html")
    if not os.path.exists(index_path):
        import route_builder
        print("[*] Generando plataforma web didáctica inicial...")
        route_builder.generar_tablero_rutas()

    # 2. Iniciar Servidor Local
    puerto = encontrar_puerto_libre(8080)
    print(f"\n[1/3] Iniciando Servidor Web local en http://127.0.0.1:{puerto}...")
    iniciar_servidor_http(puerto)
    print(f"      ✅ Servidor local activo sirviendo carpeta 'app_web/'.")

    # 3. Iniciar Túnel Cloudflare
    if not os.path.exists(CLOUDFLARED_EXE):
        print(f"[!] Error: No se encontró 'cloudflared.exe' en {BASE_DIR}")
        return

    print(f"\n[2/3] Generando túnel HTTPS seguro con Cloudflare (gratuito, sin registro)...")
    cmd = [CLOUDFLARED_EXE, "tunnel", "--url", f"http://127.0.0.1:{puerto}"]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    url_publica = None
    t0 = time.time()
    while time.time() - t0 < 30:
        line = proc.stderr.readline()
        if not line:
            time.sleep(0.1)
            continue
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url_publica = match.group(0)
            break

    if not url_publica:
        print("[!] No se pudo obtener la URL de Cloudflare a tiempo. Revisa tu conexión a internet.")
        proc.terminate()
        return

    # 4. Guardar y mostrar
    actualizar_config_url(url_publica)
    copiar_al_portapapeles(url_publica)
    qr_file = generar_pagina_qr(url_publica)

    print("\n" + "=" * 80)
    print("   🎉 ¡TU APP WEB YA ESTÁ DISPONIBLE EN INTERNET CON HTTPS SEGURO! 🎉")
    print("=" * 80)
    print(f"\n   🔗 ENLACE OFICIAL PARA TU CELULAR:")
    print(f"      {url_publica}\n")
    print(f"   📋 ¡El enlace ha sido copiado automáticamente a tu portapapeles!")
    print(f"   📷 Abriendo ventana con Código QR para escanear con la cámara...\n")
    print("   ℹ️  INSTRUCCIONES PARA TU CELULAR:")
    print("      1. Escanea el Código QR que se abrió en tu pantalla con tu cámara.")
    print("      2. En tu navegador móvil (Chrome / Safari), pulsa 'Instalar App'")
    print("         o 'Añadir a la pantalla de inicio'.")
    print("      3. ¡Listo! Tendrás el icono en tu celular y funcionará tanto")
    print("         online como 100% offline.")
    print("=" * 80)
    print("   Presiona Ctrl + C en esta ventana cuando desees apagar el servidor.")
    print("=" * 80 + "\n")

    # Abrir página con QR en el navegador
    try:
        webbrowser.open(f"file:///{qr_file}")
    except Exception:
        pass

    # Mantener el proceso vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[Servidor] Deteniendo túnel y servidor web limpiamente...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            pass
        print("[Servidor] Servidor detenido. ¡Hasta la próxima!")


if __name__ == "__main__":
    ejecutar()
