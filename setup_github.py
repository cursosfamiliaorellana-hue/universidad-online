"""
setup_github.py - Asistente Interactivo de Configuración de GitHub y Disaster Recovery
Solicita de forma interactiva la URL del Repositorio Privado y el Personal Access Token (PAT).
Guarda las credenciales de forma segura en '.env' (100% excluido por .gitignore).
Configura Git local con safe.directory "*" y verifica la conexión remota.
Compatible con Windows 8 / 10 / 11 y Python 3.8+.
"""

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
ENV_FILE = os.path.join(BASE_DIR, ".env")
GITIGNORE_FILE = os.path.join(BASE_DIR, ".gitignore")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def safe_print(texto: str = ""):
    try:
        print(texto)
    except Exception:
        try:
            print(texto.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


def leer_env() -> dict:
    env_vars = {}
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass
    return env_vars


def guardar_env(datos: dict):
    env_vars = leer_env()
    env_vars.update(datos)
    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write("# Credenciales y Configuracion Segura - Bot Universidad Online\n")
            f.write("# ATENCION: Archivo privado. Excluido por .gitignore.\n\n")
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        safe_print(f"[!] Error guardando .env: {e}")


def asegurar_gitignore():
    """Garantiza que .env y *.env estén registrados en .gitignore para evitar fugas."""
    if os.path.exists(GITIGNORE_FILE):
        try:
            with open(GITIGNORE_FILE, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if ".env" not in content:
                with open(GITIGNORE_FILE, "a", encoding="utf-8") as f:
                    f.write("\n# Credenciales privadas\n.env\n*.env\n.env.*\n")
        except Exception:
            pass


def localizar_git_exe() -> str:
    local_git = os.path.join(BASE_DIR, "git", "cmd", "git.exe")
    if os.path.exists(local_git):
        dir_git = os.path.dirname(local_git)
        if dir_git not in os.environ.get("PATH", ""):
            os.environ["PATH"] = dir_git + os.pathsep + os.environ.get("PATH", "")
        return local_git

    try:
        res = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if res.returncode == 0:
            return "git"
    except Exception:
        pass

    rutas_candidatas = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        r"C:\Git\cmd\git.exe",
    ]
    for ruta in rutas_candidatas:
        if os.path.exists(ruta):
            dir_git = os.path.dirname(ruta)
            if dir_git not in os.environ.get("PATH", ""):
                os.environ["PATH"] = dir_git + os.pathsep + os.environ.get("PATH", "")
            return ruta
    return ""


def ejecutar_git_cmd(git_exe: str, args: list) -> subprocess.CompletedProcess:
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
    if not token:
        return repo_url
    url_limpia = re.sub(r"https?://(?:[^@]+@)?", "https://", repo_url.strip())
    if "https://" in url_limpia:
        return url_limpia.replace("https://", f"https://{token.strip()}@")
    return repo_url


def main():
    safe_print("=" * 80)
    safe_print("   ASISTENTE DE CONFIGURACION GITHUB & DISASTER RECOVERY")
    safe_print("=" * 80)
    safe_print()
    safe_print("Este asistente vinculara tu laptop con tu repositorio privado de GitHub.")
    safe_print("Permite que 'backup_cerebro.bat' respalde el código y la base de datos (clases.db)")
    safe_print("de forma 100% automatizada y desatendida sin solicitar contraseñas.")
    safe_print()

    asegurar_gitignore()

    git_exe = localizar_git_exe()
    if not git_exe:
        safe_print("❌ ERROR: No se encontró Git en el sistema ni en z:\\git\\cmd\\git.exe.")
        safe_print("Verifica la instalación de Git o la carpeta 'git' portable.")
        input("\nPresiona Enter para salir...")
        return

    safe_print(f"✅ Git detectado correctamente: {git_exe}")
    safe_print()

    # Resolver ownership en Windows 8
    ejecutar_git_cmd(git_exe, ["config", "--global", "--add", "safe.directory", "*"])
    ejecutar_git_cmd(git_exe, ["config", "--global", "--add", "safe.directory", BASE_DIR])
    ejecutar_git_cmd(git_exe, ["config", "--global", "--add", "safe.directory", BASE_DIR.replace("\\", "/")])

    env_data = leer_env()

    # 1. Solicitar URL del Repositorio
    repo_actual = env_data.get("GITHUB_REPO_URL") or "https://github.com/cursosfamiliaorellana-hue/universidad-online.git"
    safe_print(f"URL de Repositorio actual: {repo_actual}")
    try:
        repo_input = input(f"-> Presiona Enter para usarla o pega la URL de tu repositorio privado:\n> ").strip()
    except Exception:
        repo_input = ""
    repo_url = repo_input if repo_input else repo_actual

    # 2. Solicitar Token de Acceso Personal (PAT)
    token_actual = env_data.get("GITHUB_TOKEN", "").strip()
    token_input = ""
    if token_actual:
        safe_print(f"\n✅ Se detectó un Token guardado previamente ({token_actual[:4]}...{token_actual[-4:]}).")
        try:
            cambio = input("-> Presiona Enter para conservarlo o escribe uno nuevo (o 'borrar'):\n> ").strip()
            if not cambio:
                token_input = token_actual
            elif cambio.lower() == "borrar":
                token_input = ""
            else:
                token_input = cambio
        except Exception:
            token_input = token_actual
    else:
        safe_print("\n📌 INSTRUCCIONES PARA OBTENER TU TOKEN (PAT):")
        safe_print("1. Entra en GitHub: Settings ➔ Developer settings ➔ Personal access tokens ➔ Tokens (classic)")
        safe_print("2. Clic en 'Generate new token (classic)'")
        safe_print("3. Asigna nombre (ej. 'Laptop-Bot') y marca la casilla con permiso 'repo'")
        safe_print("4. Copia el token generado (empieza por ghp_ o github_pat_)\n")
        try:
            token_input = input("-> Pega tu GitHub Personal Access Token (PAT):\n> ").strip()
        except Exception:
            token_input = ""

    # Guardar en .env de forma segura
    guardar_env({
        "GITHUB_REPO_URL": repo_url,
        "GITHUB_TOKEN": token_input,
    })
    safe_print("\n💾 Credenciales guardadas exitosamente en '.env' (Protegido por .gitignore).")

    # 3. Datos de Commit
    nombre_git = env_data.get("GIT_USER_NAME") or "David Herbas Orellana"
    email_git = env_data.get("GIT_USER_EMAIL") or "cursosfamiliaorellana@gmail.com"
    try:
        n_in = input(f"\n-> Nombre para commits de autor [{nombre_git}]: ").strip()
        if n_in:
            nombre_git = n_in
        e_in = input(f"-> Email para commits [{email_git}]: ").strip()
        if e_in:
            email_git = e_in
    except Exception:
        pass

    guardar_env({
        "GIT_USER_NAME": nombre_git,
        "GIT_USER_EMAIL": email_git,
    })

    # Configurar Git local
    safe_print("\n⚙️ Configurando repositorio Git local...")
    ejecutar_git_cmd(git_exe, ["init"])
    ejecutar_git_cmd(git_exe, ["config", "user.name", nombre_git])
    ejecutar_git_cmd(git_exe, ["config", "user.email", email_git])
    ejecutar_git_cmd(git_exe, ["branch", "-M", "main"])

    url_autenticada = construir_url_autenticada(repo_url, token_input)

    # Configurar remoto 'origin'
    res_remotes = ejecutar_git_cmd(git_exe, ["remote", "-v"])
    if "origin" in (res_remotes.stdout or ""):
        ejecutar_git_cmd(git_exe, ["remote", "set-url", "origin", url_autenticada])
    else:
        ejecutar_git_cmd(git_exe, ["remote", "add", "origin", url_autenticada])

    safe_print("\n🔍 Verificando configuración del remoto 'origin':")
    res_v = ejecutar_git_cmd(git_exe, ["remote", "-v"])
    for linea in (res_v.stdout or "").splitlines():
        # Ocultar token al mostrar en pantalla por seguridad
        linea_segura = re.sub(r":[^@]+@", ":****@", linea)
        safe_print(f"   {linea_segura}")

    # Probar conexión con git ls-remote
    safe_print("\n🚀 Probando autenticación con el servidor de GitHub...")
    res_test = ejecutar_git_cmd(git_exe, ["ls-remote", "--heads", "origin"])
    if res_test.returncode == 0:
        safe_print("\n" + "=" * 80)
        safe_print("✅ ¡CONEXION Y AUTENTICACION CON GITHUB VERIFICADAS CON EXITO!")
        safe_print("=" * 80)
        safe_print("Tu laptop ahora puede enviar respaldos automáticos con 'backup_cerebro.bat'.")
        safe_print("El archivo 'clases.db' y todo el código fuente están protegidos.")
        safe_print("=" * 80)
    else:
        safe_print("\n" + "=" * 80)
        safe_print("⚠️ AVISO EN PRUEBA DE CONEXION:")
        err_msg = ((res_test.stderr or "") + "\n" + (res_test.stdout or "")).strip()
        safe_print(re.sub(r":[^@]+@", ":****@", err_msg))
        safe_print("=" * 80)
        safe_print("Si el token es nuevo, asegúrate de haber marcado el permiso 'repo' en GitHub.")

    safe_print()
    try:
        input("Presiona Enter para finalizar...")
    except Exception:
        pass


if __name__ == "__main__":
    main()
