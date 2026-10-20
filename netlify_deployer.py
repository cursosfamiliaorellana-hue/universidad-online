"""
netlify_deployer.py - Despliegue Automático a Netlify para Universidad Online PWA
Proporciona una dirección web HTTPS 100% permanente, fija y gratuita para siempre (ej: https://uo-rutas.netlify.app).
Permite que el celular del usuario se actualice automáticamente en cualquier lugar con solo conectarse a internet.
"""

import io
import json
import os
import random
import re
import shutil
import string
import sys
import urllib.parse
import webbrowser
import zipfile
from typing import Optional, Dict, Any
import requests

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


def cargar_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def crear_zip_app_web() -> bytes:
    """Empaqueta los archivos de app_web/ en un buffer ZIP en memoria con index.html en la raíz."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        archivos_clave = ["index.html", "manifest.json", "sw.js", "icon-192.png", "icon-512.png"]
        for nombre in archivos_clave:
            ruta = os.path.join(APP_WEB_DIR, nombre)
            if os.path.exists(ruta):
                zf.write(ruta, arcname=nombre)
            else:
                # Buscar en directorio raíz si no está en app_web
                ruta_raiz = os.path.join(BASE_DIR, nombre)
                if os.path.exists(ruta_raiz):
                    zf.write(ruta_raiz, arcname=nombre)
    buffer.seek(0)
    return buffer.getvalue()


def crear_o_obtener_sitio(token: str, nombre_deseado: str = "uo-rutas") -> Dict[str, Any]:
    """
    Crea o recupera un sitio en Netlify bajo la cuenta del token.
    Devuelve dict con 'site_id', 'url', 'name'.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    cfg = cargar_config()
    site_id_guardado = cfg.get("netlify_site_id")

    # Si ya tenemos un site_id guardado, comprobar si es accesible
    if site_id_guardado:
        try:
            r = requests.get(f"https://api.netlify.com/api/v1/sites/{site_id_guardado}", headers=headers, timeout=15)
            if r.status_code == 200:
                s = r.json()
                if s.get("sso_login"):
                    try:
                        requests.patch(f"https://api.netlify.com/api/v1/sites/{s['id']}", headers=headers, json={"sso_login": False, "password": ""}, timeout=10)
                    except Exception:
                        pass
                return {
                    "site_id": s.get("id"),
                    "url": s.get("ssl_url") or s.get("url"),
                    "name": s.get("name"),
                }
        except Exception:
            pass

    # Intentar crear con el nombre deseado
    payload = {"name": nombre_deseado}
    r = requests.post("https://api.netlify.com/api/v1/sites", headers=headers, json=payload, timeout=20)

    if r.status_code == 201:
        s = r.json()
        site_id = s.get("id")
        url = s.get("ssl_url") or s.get("url")
        cfg["netlify_site_id"] = site_id
        cfg["pwa_public_url"] = url
        guardar_config(cfg)
        return {"site_id": site_id, "url": url, "name": s.get("name")}

    # Si el nombre ya está ocupado (422), agregar un sufijo único
    if r.status_code == 422:
        sufijo = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        payload["name"] = f"{nombre_deseado}-{sufijo}"
        r2 = requests.post("https://api.netlify.com/api/v1/sites", headers=headers, json=payload, timeout=20)
        if r2.status_code == 201:
            s = r2.json()
            site_id = s.get("id")
            url = s.get("ssl_url") or s.get("url")
            cfg["netlify_site_id"] = site_id
            cfg["pwa_public_url"] = url
            guardar_config(cfg)
            return {"site_id": site_id, "url": url, "name": s.get("name")}

    raise RuntimeError(f"Error creando sitio en Netlify: {r.status_code} - {r.text}")


def desplegar_app_web(token: Optional[str] = None, site_id: Optional[str] = None) -> Optional[str]:
    """
    Despliega la última versión de app_web a Netlify.
    Devuelve la URL HTTPS permanente en caso de éxito.
    """
    cfg = cargar_config()
    t = token or cfg.get("netlify_token")
    if not t:
        print("[Netlify] No se ha configurado 'netlify_token' en config.json. Despliegue omitido.")
        return None

    sid = site_id or cfg.get("netlify_site_id")
    if not sid:
        print("[Netlify] Obteniendo o creando sitio en Netlify...")
        try:
            info_sitio = crear_o_obtener_sitio(t)
            sid = info_sitio["site_id"]
        except Exception as e:
            print(f"[Netlify] Error al inicializar sitio: {e}")
            return None

    # Preparar el archivo ZIP de app_web
    zip_bytes = crear_zip_app_web()
    if not zip_bytes:
        print("[Netlify] [!] Error: No se encontraron archivos para desplegar en app_web.")
        return None

    print(f"\n[Netlify] 🚀 Desplegando última versión de la App Web a Netlify ({len(zip_bytes) / 1024:.1f} KB)...")
    headers = {
        "Authorization": f"Bearer {t}",
        "Content-Type": "application/zip",
    }

    try:
        url_deploy = f"https://api.netlify.com/api/v1/sites/{sid}/deploys"
        resp = requests.post(url_deploy, headers=headers, data=zip_bytes, timeout=40)

        if resp.status_code in (200, 201):
            datos = resp.json()
            url_final = datos.get("ssl_url") or datos.get("url")
            print(f"[Netlify] ✅ ¡Despliegue exitoso! App Web online en tiempo real:")
            print(f"          🔗 {url_final}")
            cfg["pwa_public_url"] = url_final
            guardar_config(cfg)
            generar_pagina_qr_netlify(url_final)
            return url_final
        else:
            print(f"[Netlify] ❌ Error en despliegue: {resp.status_code} - {resp.text}")
            return None
    except Exception as exc:
        print(f"[Netlify] ❌ Excepción durante el despliegue: {exc}")
        return None


def generar_pagina_qr_netlify(url_publica: str) -> str:
    """Crea una página HTML con el Código QR y enlace permanente para el celular."""
    url_enc = urllib.parse.quote(url_publica)
    qr_img_api = f"https://api.qrserver.com/v1/create-qr-code/?size=360x360&margin=15&data={url_enc}"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>App Web Móvil Permanente - Universidad Online</title>
  <style>
    body {{
      background: #0b0f19;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 20px;
      text-align: center;
    }}
    .card {{
      background: #151d2e;
      border: 1px solid #243048;
      border-radius: 16px;
      padding: 32px 24px;
      max-width: 480px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
    h1 {{ font-size: 22px; margin-bottom: 8px; color: #fbbf24; }}
    p {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }}
    .qr-box {{
      background: #ffffff;
      padding: 16px;
      border-radius: 12px;
      display: inline-block;
      margin-bottom: 24px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    }}
    .qr-box img {{
      width: 260px;
      height: 260px;
      display: block;
    }}
    .url-badge {{
      background: #1e293b;
      padding: 12px 18px;
      border-radius: 8px;
      font-family: monospace;
      font-size: 15px;
      color: #38bdf8;
      word-break: break-all;
      margin-bottom: 20px;
      border: 1px solid #334155;
    }}
    .btn {{
      background: linear-gradient(135deg, #10b981, #059669);
      color: #000;
      font-weight: 800;
      padding: 12px 24px;
      border-radius: 999px;
      text-decoration: none;
      font-size: 14px;
      display: inline-block;
      transition: transform 0.2s;
    }}
    .btn:hover {{ transform: scale(1.05); }}
    .steps {{
      text-align: left;
      background: rgba(0,0,0,0.3);
      padding: 16px;
      border-radius: 8px;
      margin-top: 24px;
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>📱 App Web Móvil Permanente</h1>
    <p>Escanea este código con la cámara de tu celular. Este enlace es <b>100% fijo para siempre</b> y se actualiza automáticamente con cada masterclass.</p>
    
    <div class="qr-box">
      <img src="{qr_img_api}" alt="Código QR de Acceso Móvil Permanente" />
    </div>

    <div class="url-badge">{url_publica}</div>

    <a href="{url_publica}" target="_blank" class="btn">🌐 Abrir en esta Computadora</a>

    <div class="steps">
      <b>💡 Pasos para tener el icono en tu celular:</b><br>
      1. Abre la cámara de tu celular y escanea el código QR.<br>
      2. Abre el enlace en Chrome (Android) o Safari (iPhone).<br>
      3. Pulsa <b>"Instalar App"</b> o selecciona <b>"Añadir a la pantalla de inicio"</b>.<br>
      4. ¡Listo! Tendrás el icono en tu celular y siempre que tengas internet se actualizará solo.
    </div>
  </div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(QR_HTML_FILE), exist_ok=True)
    with open(QR_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    return QR_HTML_FILE


def configurar_interactivo():
    """Asistente de configuración de Netlify por consola."""
    print("=" * 80)
    print("   CONFIGURACIÓN DE ENLACE FIJO PERMANENTE EN NETLIFY (UNIVERSIDAD ONLINE)")
    print("=" * 80)
    print("\nPara que tu App Web tenga una dirección fija en internet (ej: https://uo-rutas.netlify.app)")
    print("y tu celular se actualice automáticamente con cada masterclass, necesitamos un Token de Netlify.")
    print("\nPasos para obtener tu Token gratuito (30 segundos):")
    print("1. Abre https://app.netlify.com/ e inicia sesión (puedes entrar con Google).")
    print("2. Ve a: User Settings -> Applications -> Personal access tokens")
    print("   (O entra directo a: https://app.netlify.com/user/applications#personal-access-tokens)")
    print("3. Haz clic en 'New access token', dale un nombre (ej: 'Bot') y pulsa 'Generate token'.")
    print("4. Copia el token generado y pégalo a continuación.\n")

    cfg = cargar_config()
    token_actual = cfg.get("netlify_token", "")
    prompt = f"Pega tu Netlify Personal Access Token [{'ya configurado' if token_actual else 'requerido'}]: "
    nuevo_token = input(prompt).strip()

    token_usar = nuevo_token if nuevo_token else token_actual
    if not token_usar:
        print("[!] No se ingresó ningún token. Configuración cancelada.")
        return

    cfg["netlify_token"] = token_usar
    guardar_config(cfg)
    print("\n[1/2] Token guardado en config.json.")

    print("[2/2] Creando sitio y realizando primer despliegue a Netlify...")
    url_final = desplegar_app_web(token=token_usar)

    if url_final:
        print("\n" + "=" * 80)
        print("   🎉 ¡ENLACE FIJO PERMANENTE CREADO CON ÉXITO! 🎉")
        print("=" * 80)
        print(f"\n   🔗 TU DIRECCIÓN WEB PERMANENTE:")
        print(f"      {url_final}\n")
        print("   Esta dirección NUNCA va a cambiar. Ábrela o escanea el QR en tu celular")
        print("   e instálala con 'Añadir a pantalla de inicio'.")
        print("=" * 80)
        try:
            webbrowser.open(f"file:///{QR_HTML_FILE}")
        except Exception:
            pass
    else:
        print("\n[!] Hubo un error al desplegar a Netlify. Verifica que el token sea correcto.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--deploy":
        desplegar_app_web()
    else:
        configurar_interactivo()
