"""
configurar_github.py - Asistente Interactivo de Conexión con GitHub Pages
Configura el repositorio remoto de Git con Personal Access Token (PAT) guardado en config.json.
Elimina para siempre el error de 'dubious ownership' con safe.directory "*" y permite push 100% desatendido.
Optimizado para Windows 8 Pro y Python 3.8 (100% compatible con terminales legacy y CP1252/ASCII).
"""

import json
import os
import re
import subprocess
import sys

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def safe_print(texto: str = ""):
    try:
        print(texto)
    except Exception:
        try:
            print(texto.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


def cargar_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_config(datos: dict):
    cfg_actual = cargar_config()
    cfg_actual.update(datos)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg_actual, f, indent=2, ensure_ascii=False)
    except Exception as e:
        safe_print(f"[AVISO] No se pudo guardar config.json: {e}")


def localizar_git_exe() -> str:
    """Busca git en el proyecto local (MinGit portable) y en rutas conocidas de Windows."""
    # 1. Prioridad: MinGit portable dentro de la carpeta del bot
    local_git = os.path.join(BASE_DIR, "git", "cmd", "git.exe")
    if os.path.exists(local_git):
        dir_git = os.path.dirname(local_git)
        if dir_git not in os.environ.get("PATH", ""):
            os.environ["PATH"] = dir_git + os.pathsep + os.environ.get("PATH", "")
        return local_git

    # 2. Comando directo 'git' en el PATH del sistema
    try:
        res = subprocess.run(
            ["git", "--version"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if res.returncode == 0:
            return "git"
    except Exception:
        pass

    # 3. Rutas conocidas en Windows
    rutas_candidatas = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\git.exe"),
        r"C:\Git\cmd\git.exe",
        r"C:\Git\bin\git.exe",
    ]

    for ruta in rutas_candidatas:
        if os.path.exists(ruta):
            dir_git = os.path.dirname(ruta)
            if dir_git not in os.environ.get("PATH", ""):
                os.environ["PATH"] = dir_git + os.pathsep + os.environ.get("PATH", "")
            return ruta

    return ""


def ejecutar_git_cmd(git_exe: str, args: list) -> subprocess.CompletedProcess:
    """Ejecuta un comando de Git de forma segura en Windows asegurando safe.directory."""
    cmd = [git_exe] + args
    return subprocess.run(
        cmd,
        cwd=BASE_DIR,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def construir_url_autenticada(repo_url: str, token: str) -> str:
    """Inserta el Personal Access Token de forma segura en la URL HTTPS de GitHub."""
    if not token:
        return repo_url
    url_limpia = re.sub(r"https?://(?:[^@]+@)?", "https://", repo_url.strip())
    if "https://" in url_limpia:
        return url_limpia.replace("https://", f"https://{token.strip()}@")
    return repo_url


def main():
    safe_print("================================================================================")
    safe_print("       UNIVERSIDAD ONLINE - ASISTENTE DE CONEXION CON GITHUB PAGES")
    safe_print("================================================================================")
    safe_print()
    safe_print("Este asistente conectara la carpeta de tu bot con tu repositorio de GitHub.")
    safe_print("Configura el Token de Acceso Personal para que las subidas sean 100% automaticas.")
    safe_print()

    git_exe = localizar_git_exe()
    if not git_exe:
        safe_print("[ERROR] Git no esta disponible en el sistema ni en z:\\git\\cmd\\git.exe.")
        safe_print("Por favor, verifica que la carpeta 'git' este presente en la raiz del bot.")
        try:
            input("Presiona Enter para salir...")
        except Exception:
            pass
        return

    safe_print(f"[OK] Git detectado correctamente: {git_exe}")
    safe_print()

    # SOLUCIÓN CRÍTICA AL ERROR 'dubious ownership' de Windows 8:
    # Registra safe.directory en la configuración global del usuario de Windows actual
    ejecutar_git_cmd(git_exe, ["config", "--global", "--add", "safe.directory", "*"])
    ejecutar_git_cmd(git_exe, ["config", "--global", "--add", "safe.directory", BASE_DIR])
    ejecutar_git_cmd(git_exe, ["config", "--global", "--add", "safe.directory", BASE_DIR.replace("\\", "/")])

    cfg = cargar_config()

    # 1. URL del repositorio
    repo_default = cfg.get("github_repo_url") or "https://github.com/cursosfamiliaorellana-hue/universidad-online.git"
    safe_print(f"URL de repositorio configurada: {repo_default}")
    repo_in = ""
    try:
        repo_in = input(f"-> Presiona Enter para usarla o pega una nueva URL [{repo_default}]:\n> ").strip()
    except Exception:
        pass
    repo_url = repo_in if repo_in else repo_default

    # 2. Token de Acceso Personal (PAT)
    token_existente = cfg.get("github_token", "").strip()
    token_ingresado = ""
    if token_existente:
        safe_print(f"\n[OK] Se detecto un Token guardado previamente en config.json ({token_existente[:6]}...{token_existente[-4:]}).")
        try:
            cambiar = input("-> Presiona Enter para conservarlo o escribe uno nuevo (o 'borrar'):\n> ").strip()
            if not cambiar:
                token_ingresado = token_existente
            elif cambiar.lower() == "borrar":
                token_ingresado = ""
            else:
                token_ingresado = cambiar
        except Exception:
            token_ingresado = token_existente
    else:
        safe_print("\n[IMPORTANTE] Para que Windows no pida contraseñas en cada subida,")
        safe_print("ingresa tu Personal Access Token (PAT) de GitHub (inicia con ghp_...).")
        safe_print("Si aún no lo tienes, puedes presionar Enter y agregarlo luego en config.json.")
        try:
            token_ingresado = input("-> Pega tu GitHub Token (ghp_...):\n> ").strip()
        except Exception:
            token_ingresado = ""

    # Guardar en config.json
    guardar_config({
        "github_token": token_ingresado,
        "github_repo_url": repo_url,
    })

    # 3. Datos de Autor
    nombre_git = "David Herbas Orellana"
    email_git = "cursosfamiliaorellana@gmail.com"
    try:
        n_in = input(f"\n-> Ingresa tu nombre para los commits [{nombre_git}]: ").strip()
        if n_in:
            nombre_git = n_in
        e_in = input(f"-> Ingresa tu email de GitHub [{email_git}]: ").strip()
        if e_in:
            email_git = e_in
    except Exception:
        pass

    safe_print()
    safe_print("[INFO] Configurando repositorio local y vinculando remoto...")

    ejecutar_git_cmd(git_exe, ["init"])
    ejecutar_git_cmd(git_exe, ["config", "user.name", nombre_git])
    ejecutar_git_cmd(git_exe, ["config", "user.email", email_git])
    ejecutar_git_cmd(git_exe, ["branch", "-M", "main"])

    url_remoto_final = construir_url_autenticada(repo_url, token_ingresado)

    ejecutar_git_cmd(git_exe, ["remote", "remove", "origin"])
    ejecutar_git_cmd(git_exe, ["remote", "add", "origin", url_remoto_final])

    safe_print("[INFO] Regenerando plataforma web estatica para el primer despliegue...")
    try:
        import route_builder
        route_builder.generar_tablero_rutas(auto_deploy=False)
    except Exception as e_gen:
        safe_print(f"[AVISO] Generacion web: {e_gen}")

    safe_print("[INFO] Empaquetando archivos de la App Web en el commit inicial...")
    archivos_web = [
        "index.html",
        "app_web",
        "Mis_Rutas_80_20_UniversidadOnline.html",
        "sw.js",
        ".gitignore",
        "manifest.json",
        "icon-192.png",
        "icon-512.png",
    ]
    ejecutar_git_cmd(git_exe, ["add"] + archivos_web)
    ejecutar_git_cmd(git_exe, ["commit", "-m", "Despliegue automatico App Web a GitHub Pages"])

    safe_print()
    safe_print("================================================================================")
    safe_print("[INFO] Enviando cambios a GitHub (git push origin main)...")
    safe_print("================================================================================")

    res_push = ejecutar_git_cmd(git_exe, ["push", "-u", "origin", "main"])

    safe_print()
    salida_push = ((res_push.stdout or "") + "\n" + (res_push.stderr or "")).strip()

    if res_push.returncode == 0:
        safe_print("================================================================================")
        safe_print("✅ [EXITO TOTAL] ¡CONEXION CON GITHUB PAGES COMPLETADA EXITOSAMENTE!")
        safe_print("================================================================================")
        safe_print()
        safe_print("Los archivos de tu App Web ya estan alojados en tu repositorio de GitHub.")
        safe_print()
        safe_print("PASO FINAL (Activar GitHub Pages una sola vez):")
        safe_print(f"1. Entra a tu repositorio: {repo_url}")
        safe_print("2. Ve a 'Settings' (pestaña arriba) -> 'Pages' (menu lateral izquierdo).")
        safe_print("3. En 'Build and deployment' -> 'Branch', selecciona 'main' y carpeta '/ (root)' -> clic en 'Save'.")
        safe_print()
        safe_print("¡Listo! En 1 minuto tu App Web estara en vivo para tu celular.")
        safe_print("A partir de ahora, cada clase grabada se sincronizara y subira SOLA.")
        safe_print("================================================================================")
    else:
        safe_print("================================================================================")
        safe_print("⚠️ [AVISO] Git Push reporto un error:")
        safe_print(salida_push)
        safe_print("================================================================================")
        if "Authentication failed" in salida_push or "403" in salida_push or "could not read Username" in salida_push:
            safe_print()
            safe_print("El error se debe a que GitHub requiere un Personal Access Token (PAT).")
            safe_print("Genera tu token en: https://github.com/settings/tokens (permiso 'repo')")
            safe_print("Luego abre config.json y pegalo en 'github_token', o vuelve a ejecutar este asistente.")
        safe_print()

    try:
        input("Presiona Enter para cerrar...")
    except Exception:
        pass


if __name__ == "__main__":
    main()
