"""

recorder.py - Grabador de Masterclasses (Hotmart) y Mentorías (Zoom Web / Telegram Voz)

Soporta:

- Grabación concurrente (múltiples clases al mismo tiempo) con Aislamiento de Pestañas.

- Espera "Francotirador" en una sola pestaña (hasta 15 min) sin abrir múltiples ventanas.

- Grabación inmediata desde el primer fotograma de Hotmart.

- Inteligencia anti-buffering y despausa automática.

- Grabación de Zoom Web como 'David Herbas'.

"""

import asyncio

import base64

import ctypes

import datetime

import glob

import gc
try:
    import ujson as json
except ImportError:
    try:
        import orjson as json
    except ImportError:
        import json

import os

import re

import subprocess

import sys

import time

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

FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")

DIR_GRABACIONES = os.path.join(BASE_DIR, "grabaciones")

ARCHIVO_FRENO_MANUAL = os.path.join(BASE_DIR, "DETENER_GRABACION.txt")
LOG_FFMPEG_FILE = os.path.join(BASE_DIR, "logs_ffmpeg.txt")

_ENCODER_CACHE = None


def obtener_startupinfo_y_flags():
    """Configura banderas de proceso para ejecución 100% invisible en Windows sin suprimir I/O."""
    si = None
    flags = 0
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
    return si, flags


def registrar_log_ffmpeg(mensaje: str):
    """Escribe eventos y errores de FFmpeg en logs_ffmpeg.txt sin bloquear I/O."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FFMPEG_FILE, "a", encoding="utf-8", errors="replace") as f_log:
            f_log.write(f"[{ts}] {mensaje}\n")
    except Exception:
        pass


def detectar_encoder_video_optimo(forzar: bool = False):
    """
    FASE 1: ACELERACIÓN DE HARDWARE EN FFMPEG CON RED DE SEGURIDAD
    Evalúa en tiempo real si el sistema soporta encoders por hardware (h264_qsv, h264_amf, h264_nvenc)
    mediante un dry-run atómico y rápido (1 frame a null).

    INSTRUCCIÓN ANTI-CRASH / PLAN B:
    Si la aceleración por hardware falla o los controladores de Windows 8 Pro no la soportan,
    cae instantáneamente al PLAN B garantizado:
    libx264 por software usando estrictamente '-preset ultrafast' y '-threads 2' para no ahogar la CPU.
    """
    global _ENCODER_CACHE
    if _ENCODER_CACHE and not forzar:
        return _ENCODER_CACHE

    if not os.path.exists(FFMPEG_EXE):
        _ENCODER_CACHE = ("libx264", ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-crf", "26"])
        return _ENCODER_CACHE

    candidatos_hardware = [
        ("h264_qsv", ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "25"]),
        ("h264_amf", ["-c:v", "h264_amf", "-usage", "ultralowlatency", "-quality", "speed"]),
        ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ull", "-rc", "constqp", "-qp", "26"]),
    ]

    si, flags = obtener_startupinfo_y_flags()

    for nombre_enc, flags_enc in candidatos_hardware:
        try:
            cmd_test = [
                FFMPEG_EXE, "-y",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.05",
                "-c:v", nombre_enc,
                "-frames:v", "1",
                "-f", "null", "-"
            ]
            res = subprocess.run(
                cmd_test,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                startupinfo=si,
                creationflags=flags
            )
            if res.returncode == 0:
                print(f"[FFmpeg Hardware] 🚀 Aceleración por Hardware DETECTADA Y ACTIVA: '{nombre_enc}'. Descargando CPU al máximo.")
                registrar_log_ffmpeg(f"Encoder por Hardware verificado y activo: {nombre_enc}")
                _ENCODER_CACHE = (nombre_enc, flags_enc)
                return _ENCODER_CACHE
        except Exception as e_test:
            registrar_log_ffmpeg(f"Dry-run hardware {nombre_enc} descartado: {e_test}")
            continue

    print("[FFmpeg Hardware] 🛡️ [PLAN B ACTIVO] Aceleración por hardware no disponible. Usando software: libx264 (-preset ultrafast, -threads 2).")
    registrar_log_ffmpeg("Plan B activo: libx264 software ultrafast con 2 threads.")
    _ENCODER_CACHE = ("libx264", ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-crf", "26"])
    return _ENCODER_CACHE


SALAS_ZOOM_ACTIVAS = set()

ES_CONTINUOUS = 0x80000000

ES_SYSTEM_REQUIRED = 0x00000001

ES_DISPLAY_REQUIRED = 0x00000002

ES_AWAYMODE_REQUIRED = 0x00000040

def prevenir_suspension_sistema(activar: bool = True):

    if sys.platform != "win32":

        return

    try:

        if activar:

            ctypes.windll.kernel32.SetThreadExecutionState(

                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED | ES_AWAYMODE_REQUIRED

            )

        else:

            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    except Exception:

        pass

def cargar_config() -> Dict[str, Any]:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:

        return json.load(f)

def detectar_dispositivos_audio() -> List[str]:

    if not os.path.exists(FFMPEG_EXE):

        return []

    cmd = [FFMPEG_EXE, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]

    try:

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

        salida = res.stderr or ""

    except Exception:

        return []

    dispositivos_audio = []

    for linea in salida.splitlines():

        if "(audio)" in linea:

            m = re.search(r'"([^"]+)"\s+\(audio\)', linea)

            if m:

                dispositivos_audio.append(m.group(1))

    estereo = [d for d in dispositivos_audio if "mezcla" in d.lower() or "stereo" in d.lower()]

    otros = [d for d in dispositivos_audio if d not in estereo]

    return estereo + otros

def enfocar_y_maximizar_chrome() -> bool:

    if sys.platform != "win32":

        return False

    try:

        user32 = ctypes.windll.user32

        kernel32 = ctypes.windll.kernel32

        h_desk = user32.OpenDesktopA(b"Default", 0, False, 0x01FF)

        if h_desk:

            user32.SetThreadDesktop(h_desk)

        hwnd_console = kernel32.GetConsoleWindow()

        if hwnd_console:

            user32.ShowWindow(hwnd_console, 6)

        chrome_hwnd = None

        ventanas_a_minimizar = []

        def enum_cb(hwnd, lparam):

            if user32.IsWindowVisible(hwnd):

                length = user32.GetWindowTextLengthW(hwnd)

                if length > 0:

                    buff = ctypes.create_unicode_buffer(length + 1)

                    user32.GetWindowTextW(hwnd, buff, length + 1)

                    t = buff.value

                    if "program manager" not in t.lower() and "shell_traywnd" not in t.lower():

                        if ("hotmart" in t.lower() or "universidad.online" in t.lower() or "zoom" in t.lower()) and "chrome" in t.lower():

                            nonlocal chrome_hwnd

                            chrome_hwnd = hwnd

                        elif any(k in t.lower() for k in ["explorador de archivos", "bot_universidadonline", "prueba en vivo", "cmd.exe"]):

                            ventanas_a_minimizar.append(hwnd)

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        for h in ventanas_a_minimizar:

            user32.ShowWindow(h, 6)

        if chrome_hwnd:

            user32.ShowWindow(chrome_hwnd, 3)

            user32.SwitchToThisWindow(chrome_hwnd, True)

            user32.SetForegroundWindow(chrome_hwnd)

            user32.BringWindowToTop(chrome_hwnd)

            return True

    except Exception:

        pass

    return False

def restaurar_consola():

    if sys.platform != "win32":

        return

    try:

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        if hwnd:

            ctypes.windll.user32.ShowWindow(hwnd, 9)

            ctypes.windll.user32.SetForegroundWindow(hwnd)

    except Exception:

        pass

def convertir_url_zoom_a_web(url_zoom: str) -> str:

    if not url_zoom:

        return ""

    if "/wc/join/" in url_zoom:

        return url_zoom

    return re.sub(r"/j/(\d+)", r"/wc/join/\1", url_zoom)

async def buscar_clase_en_hotmart(page: Any, titulo_clase: str) -> Optional[str]:

    if not titulo_clase:

        return None

    try:

        lecciones = await page.evaluate("""() => {

            return Array.from(document.querySelectorAll('a[href*="/content/"]')).map(a => ({

                text: a.innerText ? a.innerText.replace(/\\s+/g, ' ').trim() : '',

                href: a.href

            })).filter(x => x.text.length > 3);

        }""")

        if not lecciones:

            return None

        norm_buscado = database.normalizar_id(titulo_clase)

        stopwords = {"gana", "dinero", "como", "para", "este", "esta", "clase", "masterclass", "con", "por", "sobre", "del", "las"}

        palabras_clave = [p for p in norm_buscado.split() if len(p) > 2 and p not in stopwords]

        candidatos_vivo = []

        for l in lecciones:

            norm_l = database.normalizar_id(l["text"])

            es_vivo = "vivo" in norm_l or "live" in norm_l or "🔴" in l["text"]

            coincidencias = sum(1 for w in palabras_clave if w in norm_l)

            if es_vivo and coincidencias > 0:

                candidatos_vivo.append((coincidencias, l))

        if candidatos_vivo:

            candidatos_vivo.sort(key=lambda x: x[0], reverse=True)

            return candidatos_vivo[0][1]["href"]

        candidatos_gen = []

        for l in lecciones:

            norm_l = database.normalizar_id(l["text"])

            coincidencias = sum(1 for w in palabras_clave if w in norm_l)

            if coincidencias > 0:

                candidatos_gen.append((coincidencias, l))

        if candidatos_gen:

            candidatos_gen.sort(key=lambda x: x[0], reverse=True)

            return candidatos_gen[0][1]["href"]

    except Exception:

        pass

    return None

async def cerrar_pestana_clase(titulo_clase: str, cdp_url: str = "http://localhost:9222") -> bool:

    """Garantiza el cierre físico y limpio de cualquier pestaña asociada a la clase en Chrome vía CDP."""

    from playwright.async_api import async_playwright

    if not titulo_clase:

        return False

    try:

        async with async_playwright() as p:

            browser = None

            try:

                browser = await p.chromium.connect_over_cdp(cdp_url)

                if not browser.contexts:

                    return False

                for page in list(browser.contexts[0].pages):

                    try:

                        cid = await page.evaluate("() => window.__clase_id")

                        if cid == titulo_clase:

                            await page.close()

                            print(f"[Recorder] 🚪 Pestaña de '{titulo_clase}' cerrada limpiamente.")

                    except Exception:

                        pass

                return True

            finally:

                if browser:

                    try:

                        await browser.disconnect()

                    except Exception:

                        pass

    except Exception:

        return False

async def preparar_reproductor_hotmart(

    url_clase: Optional[str] = None,

    titulo_clase: Optional[str] = None,

    cdp_url: str = "http://localhost:9222",

    num_parte: int = 0,

) -> Any:

    from playwright.async_api import async_playwright

    

    enfocar_y_maximizar_chrome()

    async with async_playwright() as p:

        try:

            browser = await p.chromium.connect_over_cdp(cdp_url)

        except Exception:

            return False

        contexts = browser.contexts

        if not contexts:

            return False

        # 1. Buscar pestaña base de Hotmart (omitiendo pestañas de otras clases activas)

        base_page = None

        for page in contexts[0].pages:

            try:

                page_id = await page.evaluate("() => window.__clase_id")

                if page_id and titulo_clase and page_id != titulo_clase:

                    continue

            except Exception:

                pass

            if "hotmart" in page.url.lower():

                base_page = page

                break

        if not base_page:

            for page in contexts[0].pages:

                try:

                    page_id = await page.evaluate("() => window.__clase_id")

                    if not page_id:

                        base_page = page

                        break

                except Exception:

                    pass

            if not base_page:

                base_page = contexts[0].pages[0]

        url_destino = url_clase

        if not url_destino and titulo_clase:

            url_destino = await buscar_clase_en_hotmart(base_page, titulo_clase)

        # 2. AISLAMIENTO ESTRICTO DE PESTAÑAS (MÁXIMO UNA pestaña por clase)

        target_page = None

        paginas_existentes = []

        for page in list(contexts[0].pages):

            try:

                page_id = await page.evaluate("() => window.__clase_id")

                if titulo_clase and page_id == titulo_clase:

                    paginas_existentes.append(page)

                elif url_destino and page.url == url_destino:

                    paginas_existentes.append(page)

            except Exception:

                pass

        if paginas_existentes:

            target_page = paginas_existentes[0]

            # Si hubiese pestañas duplicadas de intentos anteriores, aniquilar clones

            for sobrante in paginas_existentes[1:]:

                try:

                    await sobrante.close()

                except Exception:

                    pass

            print(f"[Recorder] 🔄 Reutilizando pestaña única aislada para '{titulo_clase}'.")

        else:

            target_page = await contexts[0].new_page()

            print(f"[Recorder] 📑 Abriendo nueva pestaña dedicada y aislada para '{titulo_clase}'.")

        if url_destino and target_page.url != url_destino:

            try:

                await target_page.goto(url_destino, wait_until="domcontentloaded", timeout=30000)

                await asyncio.sleep(2)

            except Exception as e_nav:

                print(f"[Recorder] Aviso navegando a destino: {e_nav}")

        elif not url_destino and target_page.url != base_page.url:

            try:

                await target_page.goto(base_page.url, wait_until="domcontentloaded", timeout=30000)

                await asyncio.sleep(2)

            except Exception:

                pass

        try:

            btn_recup = target_page.locator('button:has-text("Continuar viendo"), a:has-text("Continuar viendo")').first

            if await btn_recup.count() > 0:

                await btn_recup.click()

                await asyncio.sleep(2)

        except Exception:

            pass

        if num_parte > 0:

            print(f"[Recorder] 🔍 Buscando parte {num_parte} en Hotmart...")

            try:

                await target_page.evaluate("""(num) => {

                    const numStr = String(num);

                    const btns = Array.from(document.querySelectorAll('a, button, div, li, span')).filter(el => 

                        el.innerText && (

                            el.innerText.toLowerCase().includes('parte ' + numStr) || 

                            el.innerText.toLowerCase().includes('part ' + numStr) ||

                            (el.innerText.trim() === numStr)

                        )

                    );

                    if (btns.length > 0) {

                        const visibleBtns = btns.filter(b => b.offsetParent !== null);

                        if (visibleBtns.length > 0) visibleBtns[0].click();

                        else btns[0].click();

                    }

                }""", num_parte)

                await asyncio.sleep(4)

            except Exception:

                pass

        # 3. Inyectar Sello de Identidad para que no se pierda la pestaña

        try:

            if titulo_clase:

                await target_page.evaluate("(t) => { window.__clase_id = t; }", titulo_clase)

        except Exception:

            pass

        try:

            client = await target_page.context.new_cdp_session(target_page)

            await client.send("Emulation.setFocusEmulationEnabled", {"enabled": True})

        except Exception:

            pass

        return target_page.url

async def grabar_stream_hotmart(

    segundos: int,

    ruta_salida_mp4: str,

    url_clase: Optional[str] = None,

    titulo_clase: Optional[str] = None,

    cdp_url: str = "http://localhost:9222",

    num_parte: int = 0,

    id_clase: Optional[str] = None,

) -> bool:

    from playwright.async_api import async_playwright

    titulo = titulo_clase or "Masterclass"

    if not id_clase:

        id_clase = database.normalizar_id(titulo or os.path.basename(ruta_salida_mp4))

    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida_mp4)), exist_ok=True)

    ts_uid = int(time.time() * 1000)

    ruta_webm = os.path.splitext(ruta_salida_mp4)[0] + f"_{ts_uid}.webm"

    if os.path.exists(ruta_webm):

        try:

            os.remove(ruta_webm)

        except Exception:

            pass

    async with async_playwright() as p:

        try:

            browser = await p.chromium.connect_over_cdp(cdp_url)

        except Exception:

            return False

        if not browser.contexts:

            return False

        # 1. Encontrar la pestaña correcta usando el Sello de Identidad

        target_page = None

        for page in browser.contexts[0].pages:

            try:

                page_id = await page.evaluate("() => window.__clase_id")

                if page_id == titulo_clase:

                    target_page = page

                    break

            except Exception:

                pass

        if not target_page:

            for page in browser.contexts[0].pages:

                if url_clase and page.url == url_clase:

                    target_page = page

                    break

        if not target_page:

            return False

        for f in [target_page] + target_page.frames:

            try:

                await f.evaluate("""() => {

                    Object.defineProperty(document, 'hidden', { value: false, writable: true });

                    Object.defineProperty(document, 'visibilityState', { value: 'visible', writable: true });

                    if (!window.__bgKeepAlive) {

                        window.__bgKeepAlive = setInterval(() => {

                            const v = document.querySelector('video');

                            if (v && v.paused && v.readyState >= 3) {

                                v.play().catch(()=>{});

                            }

                        }, 2000);

                    }

                }""")

            except Exception:

                pass

        video_locator = None

        

        # =========================================================================

        # PUNTO 1: MODO FRANCOTIRADOR (Espera Silenciosa en la MISMA pestaña)

        # Bucle de hasta 15 minutos (450 intentos * 2s) esperando que el flujo 

        # de video del profesor envíe su primer fotograma (tracks > 0).

        # =========================================================================

        print(f"\n[Recorder] ⏳ Pestaña reservada. Esperando a que el flujo de video inicie (Max 15 min)...")

        

        for intento in range(450):

            if target_page.is_closed() or os.path.exists(ARCHIVO_FRENO_MANUAL) or database.es_clase_cancelada(id_clase):

                if database.es_clase_cancelada(id_clase):

                    print(f"\n[Recorder] 🛑 Clase '{titulo}' cancelada por el usuario en base de datos. Abortando espera.")

                break

                

            for f in [target_page] + target_page.frames:

                try:

                    if await f.locator("video").count() > 0:

                        # Forzar Play apenas exista la etiqueta de video

                        await f.locator("body").evaluate("""() => {

                            const v = document.querySelector('video');

                            if (v) { v.muted = false; v.volume = 1.0; const p = v.play(); if (p) p.catch(()=>{}); }

                            const pb = document.querySelector('button[aria-label*="Play"]') || document.querySelector('.vjs-big-play-button') || document.querySelector('.vjs-play-control');

                            if (pb) pb.click();

                            const ub = document.querySelector('button[aria-label*="Unmute"]') || document.querySelector('.vjs-mute-control');

                            if (ub) ub.click();

                        }""")

                        

                        # Comprobar si el video ya está emitiendo señal (tracks)

                        ok_tr = await f.locator("video").first.evaluate("""v => {

                            const st = v.captureStream ? v.captureStream() : (v.mozCaptureStream ? v.mozCaptureStream() : null);

                            return st && st.getTracks().length > 0;

                        }""")

                        if ok_tr:

                            video_locator = f.locator("video").first

                            break

                except Exception:

                    pass

                    

            if video_locator:

                break

            await asyncio.sleep(2)

        if not video_locator:

            print(f"\n[Recorder] ❌ El video nunca inició tras 15 minutos de espera en la pestaña. Abortando clase.")

            try:

                if not target_page.is_closed():

                    await target_page.close()

                    print(f"[Recorder] 🚪 Pestaña aislada de '{titulo_clase}' cerrada tras timeout del Francotirador.")

            except Exception:

                pass

            return False

        # Inicia la captura desde el MS 0 del flujo de video

        res_init = await video_locator.evaluate("""v => {

            try {

                window.__chunks = [];

                const stream = v.captureStream ? v.captureStream() : v.mozCaptureStream();

                const preferedMimes = [
                    'video/webm;codecs=h264,opus',
                    'video/webm;codecs=h264',
                    'video/mp4;codecs=avc1',
                    'video/webm;codecs=vp9,opus',
                    'video/webm;codecs=vp8,opus',
                    'video/webm'
                ];
                let mrOptions = {};
                for (const m of preferedMimes) {
                    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) {
                        mrOptions = { mimeType: m };
                        break;
                    }
                }
                const mr = new MediaRecorder(stream, mrOptions);

                mr.ondataavailable = e => { if (e.data.size > 0) window.__chunks.push(e.data); };

                mr.start(500);

                window.__mr = mr;

                return { ok: true, tracks: stream.getTracks().length, mimeType: mr.mimeType };

            } catch(e) { return { ok: false, error: e.message }; }

        }""")

        if not res_init.get("ok"):

            print(f"\n[Recorder] ❌ Error inicializando MediaRecorder: {res_init.get('error')}. Abortando clase.")

            try:

                if not target_page.is_closed():

                    await target_page.close()

                    print(f"[Recorder] 🚪 Pestaña aislada de '{titulo_clase}' cerrada.")

            except Exception:

                pass

            return False

        print(f"[Recorder] ✅ ¡Flujo de video detectado para '{titulo}'! Grabación digital iniciada ({segundos} segundos).")

        print(f"[Recorder] 🛡️ [Aislamiento Concurrente] Captura Tab-Level (v.captureStream). Audio/Video 100% aislados a nivel DOM.")

        t_inicio = time.time()

        ultimo_drenado = 0

        segundos_congelado = 0

        ultimo_curr_time = -1.0

        t_ultimo_avance = time.time()

        t_ultimo_chunk = time.time()

        

        try:

            while True:

                if os.path.exists(ARCHIVO_FRENO_MANUAL) or database.es_clase_cancelada(id_clase):

                    print("\n[Recorder] 🛑 Señal de parada o cancelación detectada. Finalizando grabación...")

                    try:

                        if os.path.exists(ARCHIVO_FRENO_MANUAL):

                            os.remove(ARCHIVO_FRENO_MANUAL)

                    except Exception:

                        pass

                    break

                t_actual = time.time()

                transcurrido = int(t_actual - t_inicio)

                if transcurrido >= segundos:

                    break

                sys.stdout.write(f"\r   Grabando video digital (Aislado) ['{titulo[:25]}']... {min(transcurrido + 1, segundos)}/{segundos} segundos")

                sys.stdout.flush()

                # =========================================================================

                # AUTO-RECUPERACIÓN INTELIGENTE DEL REPRODUCTOR EN VIVO (HOTMART)

                # Monitorea: readyState, pausas no deseadas, errores DOM de Hotmart y cuelgues

                # =========================================================================

                if transcurrido > 0 and transcurrido % 3 == 0:

                    try:

                        # -------------------------------------------------------------
                        # SALUD DEL STREAM (DIRECTO EN EL FRAME DEL REPRODUCTOR)
                        # Evita bloqueos cross-origin en Hotmart ejecutando en video_locator
                        # -------------------------------------------------------------
                        estado_stream = None

                        if video_locator:

                            try:

                                estado_stream = await video_locator.evaluate("""v => {

                                    const errSelectors = [

                                        '.player-error', '.hotmart-player-error', '[class*="error-container"]',

                                        '[class*="error-screen"]', '[class*="offline"]', '[class*="player-offline"]',

                                        '[class*="reload-player"]', '[class*="connection-error"]', '.vjs-error-display',

                                        '.no-connection', '[aria-label*="error" i]'

                                    ];

                                    let hasErrorUI = false;

                                    for (const sel of errSelectors) {

                                        const el = document.querySelector(sel);

                                        if (el && el.offsetParent !== null && (el.innerText.trim().length > 0 || el.querySelector('svg, img'))) {

                                            hasErrorUI = true;

                                            break;

                                        }

                                    }

                                    if (v.error) return { ok: false, motivo: 'MEDIA_ERROR', code: v.error.code, hasErrorUI: true };

                                    let tracksEnded = false;

                                    try {

                                        const mr = window.__mr;

                                        if (mr && mr.stream) {

                                            const trs = mr.stream.getTracks();

                                            if (trs.length > 0 && trs.every(t => t.readyState === 'ended')) {

                                                tracksEnded = true;

                                            }

                                        }

                                    } catch(e) {}

                                    // Despausa automatica si tiene buffer pero se pauso

                                    if (v.paused && v.readyState >= 3) {

                                        const p = v.play();

                                        if (p) p.catch(()=>{});

                                    }

                                    return {

                                        ok: !tracksEnded && !hasErrorUI,

                                        motivo: tracksEnded ? 'TRACKS_ENDED' : (hasErrorUI ? 'ERROR_UI' : 'OK'),

                                        paused: v.paused,

                                        readyState: v.readyState,

                                        currentTime: v.currentTime,

                                        hasErrorUI: hasErrorUI

                                    };

                                }""")

                            except Exception:

                                # Si video_locator se desconecto, intentar reengancharlo entre los frames

                                video_locator = None

                                for f in [target_page] + target_page.frames:

                                    try:

                                        if await f.locator("video").count() > 0:

                                            video_locator = f.locator("video").first

                                            break

                                    except Exception:

                                        pass

                                if video_locator:

                                    try:

                                        estado_stream = await video_locator.evaluate("""v => ({

                                            ok: true,

                                            motivo: 'REENGANCHADO',

                                            paused: v.paused,

                                            readyState: v.readyState,

                                            currentTime: v.currentTime,

                                            hasErrorUI: false

                                        })""")

                                    except Exception:

                                        estado_stream = None

                        if not estado_stream:

                            estado_stream = {"ok": False, "motivo": "NO_VIDEO", "hasErrorUI": False, "readyState": 0}

                        # Verificar si en la ventana principal hay pantalla explicita de error/desconexion
                        has_top_error = False

                        try:

                            has_top_error = await target_page.evaluate("""() => {

                                const sel = ['.error-screen', '.hotmart-player-error', '[class*="connection-error"]', '.offline-screen', '.no-connection'];

                                for (const s of sel) {

                                    const el = document.querySelector(s);

                                    if (el && el.offsetParent !== null && (el.innerText.trim().length > 0 || el.querySelector('svg, img'))) return true;

                                }

                                return false;

                            }""")

                        except Exception:

                            pass

                        # Indicador de flujo activo (si llegaron chunks WebM en los ultimos 6s)
                        grabando_activo = (time.time() - t_ultimo_chunk <= 6)

                        # Analisis de estabilidad
                        if has_top_error or estado_stream.get("hasErrorUI") or estado_stream.get("motivo") in ('MEDIA_ERROR', 'TRACKS_ENDED'):

                            segundos_congelado += 3

                        elif estado_stream.get("motivo") == "NO_VIDEO":

                            if not grabando_activo:

                                segundos_congelado += 3

                        else:

                            curr_time = estado_stream.get("currentTime", 0.0)

                            if curr_time != ultimo_curr_time:

                                ultimo_curr_time = curr_time

                                t_ultimo_avance = time.time()

                                segundos_congelado = 0

                            elif grabando_activo:

                                # Chunks WebM estan fluyendo activamente a disco: el stream esta 100% vivo
                                segundos_congelado = 0

                            elif estado_stream.get("paused") or estado_stream.get("readyState", 0) < 2:

                                if time.time() - t_ultimo_avance > 20:

                                    segundos_congelado += 3

                            else:

                                segundos_congelado = max(0, segundos_congelado - 3)

                        # Si el cuelgue persiste por mas de 30 segundos continuos: Auto-recuperacion via page.reload()
                        if segundos_congelado >= 30:

                            print(f"\n[Recorder] ⚠️ ¡Cuelgue del stream de Hotmart detectado ({estado_stream.get('motivo', 'Freeze')})! Ejecutando page.reload() automático...")

                            

                            # 1. Drenar fragmentos capturados hasta ahora

                            try:

                                b64_list = await video_locator.evaluate("""async () => {

                                    const chunks = window.__chunks || []; window.__chunks = [];

                                    const results = [];

                                    for (const c of chunks) {

                                        const buf = await c.arrayBuffer(); let binary = ''; const bytes = new Uint8Array(buf);

                                        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);

                                        results.push(btoa(binary));

                                    }

                                    return results;

                                }""")

                                if b64_list:

                                    with open(ruta_webm, "ab") as f:

                                        for b64 in b64_list:

                                            f.write(base64.b64decode(b64))

                            except Exception:

                                pass

                            # 2. Recargar la pestaña y reinyectar Sello de Identidad

                            try:

                                await target_page.reload(wait_until="domcontentloaded", timeout=30000)

                                await asyncio.sleep(3)

                                await target_page.evaluate("(t) => { window.__clase_id = t; }", titulo_clase)

                                if num_parte > 0:

                                    await target_page.evaluate("""(num) => {

                                        const numStr = String(num);

                                        const btns = Array.from(document.querySelectorAll('a, button, div, li, span')).filter(el => 

                                            el.innerText && (

                                                el.innerText.toLowerCase().includes('parte ' + numStr) || 

                                                el.innerText.toLowerCase().includes('part ' + numStr) ||

                                                (el.innerText.trim() === numStr)

                                            )

                                        );

                                        if (btns.length > 0) {

                                            const visibleBtns = btns.filter(b => b.offsetParent !== null);

                                            if (visibleBtns.length > 0) visibleBtns[0].click();

                                            else btns[0].click();

                                        }

                                    }""", num_parte)

                                    await asyncio.sleep(3)

                            except Exception as e_rel:

                                print(f"[Recorder] Aviso al recargar página: {e_rel}")

                            # 3. Esperar que el video reviva y recomenzar MediaRecorder

                            video_locator = None

                            for _ in range(30):

                                for f in [target_page] + target_page.frames:

                                    try:

                                        if await f.locator("video").count() > 0:

                                            await f.locator("body").evaluate("""() => {

                                                const v = document.querySelector('video');

                                                if (v) { v.muted = false; v.volume = 1.0; const p = v.play(); if (p) p.catch(()=>{}); }

                                                const pb = document.querySelector('button[aria-label*="Play"]') || document.querySelector('.vjs-big-play-button') || document.querySelector('.vjs-play-control');

                                                if (pb) pb.click();

                                                const ub = document.querySelector('button[aria-label*="Unmute"]') || document.querySelector('.vjs-mute-control');

                                                if (ub) ub.click();

                                            }""")

                                            ok_tr = await f.locator("video").first.evaluate("""v => {

                                                const st = v.captureStream ? v.captureStream() : (v.mozCaptureStream ? v.mozCaptureStream() : null);

                                                return st && st.getTracks().length > 0;

                                            }""")

                                            if ok_tr:

                                                video_locator = f.locator("video").first

                                                break

                                    except Exception:

                                        pass

                                if video_locator:

                                    break

                                await asyncio.sleep(2)

                            if video_locator:

                                await video_locator.evaluate("""v => {

                                    try {

                                        window.__chunks = [];

                                        const stream = v.captureStream ? v.captureStream() : v.mozCaptureStream();

                                        const preferedMimes = [
                                            'video/webm;codecs=h264,opus',
                                            'video/webm;codecs=h264',
                                            'video/mp4;codecs=avc1',
                                            'video/webm;codecs=vp9,opus',
                                            'video/webm;codecs=vp8,opus',
                                            'video/webm'
                                        ];
                                        let mrOptions = {};
                                        for (const m of preferedMimes) {
                                            if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) {
                                                mrOptions = { mimeType: m };
                                                break;
                                            }
                                        }
                                        const mr = new MediaRecorder(stream, mrOptions);

                                        mr.ondataavailable = e => { if (e.data.size > 0) window.__chunks.push(e.data); };

                                        mr.start(500);

                                        window.__mr = mr;

                                    } catch(e) {}

                                }""")

                                print(f"\n[Recorder] 🟢 ¡Video reanudado y captura reconectada exitosamente sin intervención humana!")

                                segundos_congelado = 0

                                t_ultimo_avance = time.time()

                                t_ultimo_chunk = time.time()

                    except Exception:

                        pass

                # Drenaje de datos (extracción de video)

                if (transcurrido - ultimo_drenado >= 2) or (transcurrido >= segundos - 1):

                    ultimo_drenado = transcurrido

                    try:

                        b64_list = await video_locator.evaluate("""async () => {

                            const chunks = window.__chunks || []; window.__chunks = [];

                            const results = [];

                            for (const c of chunks) {

                                const buf = await c.arrayBuffer(); let binary = ''; const bytes = new Uint8Array(buf);

                                for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);

                                results.push(btoa(binary));

                            }

                            return results;

                        }""")

                        if b64_list:

                            t_ultimo_chunk = time.time()

                            with open(ruta_webm, "ab") as f:

                                for b64 in b64_list:

                                    f.write(base64.b64decode(b64))

                    except Exception:

                        pass

                

                await asyncio.sleep(0.5)

        finally:

            # Detener la grabación y cerrar SU pestaña aislada al terminar la hora y media o al salir

            try:

                if video_locator:

                    await video_locator.evaluate("v => { if (window.__mr) window.__mr.stop(); v.pause(); }")

            except Exception:

                pass

            await asyncio.sleep(1)

            try:

                if target_page and not target_page.is_closed():

                    await target_page.close()

                    print(f"\n[Recorder] 🚪 Pestaña aislada de '{titulo_clase}' cerrada exitosamente.")

            except Exception:

                pass

            try:

                if browser:

                    await browser.disconnect()

            except Exception:

                pass

    print("\n[Recorder] Finalizando captura y procesando video a MP4...")

    # -------------------------------------------------------------------------
    # FASE 1: DIRECT STREAM COPY (Remuxing ultrarrápido en 2-5 segundos, ~0% CPU)
    # Si Chrome grabó en H.264, copiamos los paquetes de video directamente sin re-codificar.
    # -------------------------------------------------------------------------
    si, flags = obtener_startupinfo_y_flags()
    log_f = open(LOG_FFMPEG_FILE, "a", encoding="utf-8", errors="replace")

    cmd_fast = [
        FFMPEG_EXE, "-y", "-i", ruta_webm,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        ruta_salida_mp4
    ]
    exito_remux = False
    print("[Recorder] ⚡ Intentando remuxing ultrarrápido (Direct Stream Copy, 0% CPU)...")
    try:
        log_f.write(f"\n--- [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] REMUX FAST: {ruta_webm} ---\n")
        log_f.flush()
        res_fast = await asyncio.to_thread(
            subprocess.run, cmd_fast, stdout=log_f, stderr=subprocess.STDOUT, timeout=180, startupinfo=si, creationflags=flags
        )
        if res_fast.returncode == 0 and os.path.exists(ruta_salida_mp4) and verificar_integridad_video(ruta_salida_mp4):
            exito_remux = True
            print("[Recorder] ⚡ ¡Remuxing ultrarrápido completado exitosamente en segundos!")
    except Exception as e_fast:
        print(f"[Recorder] Aviso en Direct Stream Copy: {e_fast}")

    # -------------------------------------------------------------------------
    # FASE 2: TRANSCODIFICACIÓN CON ACELERACIÓN POR HARDWARE Y PLAN B ULTRAFAST
    # Si la copia directa no aplicó, intenta primero hardware; si falla, cae a Plan B software libx264 (-preset ultrafast, -threads 2).
    # -------------------------------------------------------------------------
    if not exito_remux:
        enc_nombre, enc_flags = detectar_encoder_video_optimo()

        # Si hay encoder hardware disponible (ej. h264_qsv), intentarlo primero
        if enc_nombre != "libx264":
            print(f"[Recorder] 🚀 Intentando transcodificación por Hardware ({enc_nombre})...")
            cmd_hw = [
                FFMPEG_EXE, "-y", "-i", ruta_webm,
                "-c:v", enc_nombre, "-global_quality", "23",
                "-r", "24",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                ruta_salida_mp4
            ]
            try:
                log_f.write(f"\n--- [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TRANSCODE HW ({enc_nombre}) ---\n")
                log_f.flush()
                res_hw = await asyncio.to_thread(
                    subprocess.run, cmd_hw, stdout=log_f, stderr=subprocess.STDOUT, timeout=None, startupinfo=si, creationflags=flags
                )
                if res_hw.returncode == 0 and os.path.exists(ruta_salida_mp4) and verificar_integridad_video(ruta_salida_mp4):
                    exito_remux = True
                    print(f"[Recorder] ✅ Transcodificación por hardware ({enc_nombre}) completada exitosamente.")
            except Exception as e_hw:
                print(f"[Recorder] Aviso transcodificación hardware: {e_hw}")

        # PLAN B (Software ultrafast libx264 con threads 2) si Direct Stream Copy y Hardware fallaron
        if not exito_remux:
            print("[Recorder] 🛡️ [PLAN B ACTIVO] Transcodificando por software: libx264 (-preset ultrafast, -threads 2)...")
            cmd_transcode = [
                FFMPEG_EXE, "-y", "-i", ruta_webm,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-r", "24",
                "-threads", "2",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                ruta_salida_mp4
            ]
            try:
                log_f.write(f"\n--- [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TRANSCODE PLAN B (libx264 threads=2) ---\n")
                log_f.flush()
                res_trans = await asyncio.to_thread(
                    subprocess.run, cmd_transcode, stdout=log_f, stderr=subprocess.STDOUT, timeout=None, startupinfo=si, creationflags=flags
                )
                if res_trans.returncode == 0 and os.path.exists(ruta_salida_mp4) and verificar_integridad_video(ruta_salida_mp4):
                    exito_remux = True
                    print("[Recorder] ✅ Transcodificación ultrafast Plan B completada y verificada.")
            except Exception as e_conv:
                print(f"\n[Recorder] Error durante transcodificación FFmpeg: {e_conv}")

    try:
        log_f.close()
    except Exception:
        pass

    # Liberación de memoria en tiempo muerto post-procesamiento de video
    gc.collect()

    # -------------------------------------------------------------------------
    # SALVAGUARDA ANTI-DESTRUCCIÓN (REGLA DE ORO)
    # NUNCA borrar ruta_webm si el remuxing falló o el MP4 no verificó.
    # -------------------------------------------------------------------------
    if exito_remux and os.path.exists(ruta_salida_mp4) and verificar_integridad_video(ruta_salida_mp4) and os.path.getsize(ruta_salida_mp4) > 5 * 1024 * 1024:
        try:
            os.remove(ruta_webm)
        except Exception:
            pass
        return True
    else:
        if os.path.exists(ruta_webm) and os.path.getsize(ruta_webm) > 1024 * 1024:
            tam_mb = os.path.getsize(ruta_webm) / (1024 * 1024)
            print(f"\n[Recorder] 🛡️ [SALVAGUARDA ANTI-DESTRUCCIÓN] Remuxing no verificado. Video crudo PRESERVADO intacto: '{ruta_webm}' ({tam_mb:.1f} MB).")
            if id_clase:
                try:
                    database.guardar_o_actualizar_clase(
                        id_clase=id_clase,
                        titulo_original=titulo,
                        estado="ERROR_REMUXING",
                        ruta_archivo=ruta_webm,
                    )
                    print(f"[Recorder] 💾 Base de datos actualizada: '{titulo}' -> Estado: 'ERROR_REMUXING'.")
                except Exception as e_db:
                    print(f"[Recorder] Aviso actualizando BD a ERROR_REMUXING: {e_db}")
        return False

async def grabar_mentoria_zoom_o_voz(

    url_objetivo: str,

    ruta_salida_mp4: str,

    nombre_participante: str = "David Herbas",

    max_horas: int = 5,

    cdp_url: str = "http://localhost:9222",

    id_clase: Optional[str] = None,

) -> bool:

    from playwright.async_api import async_playwright

    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida_mp4)), exist_ok=True)

    if os.path.exists(ARCHIVO_FRENO_MANUAL):

        try:

            os.remove(ARCHIVO_FRENO_MANUAL)

        except Exception:

            pass

    es_zoom = "zoom.us" in (url_objetivo or "").lower()

    url_web = convertir_url_zoom_a_web(url_objetivo) if es_zoom else url_objetivo

    zoom_id_room = extraer_id_sala_zoom(url_objetivo) if es_zoom else None

    if zoom_id_room and zoom_id_room in SALAS_ZOOM_ACTIVAS:

        print(f"\n[Recorder Zoom] 🛡️ [Anti-Colisión] Ya existe una pestaña/grabación activa para la sala {zoom_id_room}. Omitiendo duplicado.")

        return True

    if zoom_id_room:

        SALAS_ZOOM_ACTIVAS.add(zoom_id_room)

    print(f"\n[Recorder Zoom/Mentoría] 🛡️ Preparando entrada segura como '{nombre_participante}' (Mic/Cámara OFF)...")

    browser = None

    page = None

    proc_ffmpeg = None

    try:

        async with async_playwright() as p:

            try:

                browser = await p.chromium.connect_over_cdp(cdp_url)

                context = browser.contexts[0]

                page = await context.new_page()

                await page.add_init_script("""() => {

                    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {

                        const origGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);

                        navigator.mediaDevices.getUserMedia = async (constraints) => {

                            if (constraints && (constraints.audio || constraints.video)) {

                                throw new DOMException('Permission denied by Bot Privacy Guard', 'NotAllowedError');

                            }

                            return origGetUserMedia(constraints);

                        };

                    }

                }""")

                if es_zoom and url_web:

                    print(f"[Recorder Zoom] Navegando al cliente web de Zoom: {url_web}")

                    await page.goto(url_web, wait_until="domcontentloaded", timeout=30000)

                    await asyncio.sleep(4)

                    try:

                        campo_nombre = page.locator('input#input-for-name, input[name="inputname"], input[placeholder*="nombre" i], input[placeholder*="name" i]').first

                        if await campo_nombre.count() > 0:

                            await campo_nombre.fill(nombre_participante)

                            print(f"[Recorder Zoom] ✍️ Nombre '{nombre_participante}' ingresado correctamente.")

                    except Exception:

                        pass

                    try:

                        await page.evaluate("""() => {

                            const btns = Array.from(document.querySelectorAll('button[aria-label]'));

                            for (const b of btns) {

                                const lbl = (b.getAttribute('aria-label') || '').toLowerCase();

                                if ((lbl.includes('mute') && !lbl.includes('unmute')) || (lbl.includes('stop video') || lbl.includes('detener video'))) {

                                    b.click();

                                }

                            }

                        }""")

                    except Exception:

                        pass

                    try:

                        btn_join = page.locator('button.preview-join-button, button:has-text("Unirse"), button:has-text("Join"), button:has-text("Entrar")').first

                        if await btn_join.count() > 0:

                            await btn_join.click()

                            await asyncio.sleep(5)

                    except Exception:

                        pass

                    try:

                        btn_audio = page.locator('button:has-text("Audio por computadora"), button:has-text("Join Audio by Computer"), button:has-text("Entrar al audio por computadora")').first

                        if await btn_audio.count() > 0:

                            await btn_audio.click()

                    except Exception:

                        pass

                dispositivos = detectar_dispositivos_audio()

                disp_audio = dispositivos[0] if dispositivos else None

                is_voice_chat = "chat_voz" in (url_objetivo or "").lower() or not es_zoom

                if es_zoom:

                    try:

                        enfocar_y_maximizar_chrome()

                        await page.bring_to_front()

                    except Exception:

                        pass

                if is_voice_chat:

                    print("\n[Recorder Mentoría] 🎙️ Grabando sesión de voz directa en segundo plano (CPU < 3%)...")

                    cmd = [FFMPEG_EXE, "-y"]

                    if disp_audio:

                        cmd.extend(["-f", "dshow", "-i", f"audio={disp_audio}"])

                    else:

                        cmd.extend(["-f", "dshow", "-i", "audio=dummy"])

                    cmd.extend(["-vn", "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", ruta_salida_mp4])

                else:

                    enc_nombre, enc_flags = detectar_encoder_video_optimo()

                    cmd = [FFMPEG_EXE, "-y", "-f", "gdigrab", "-framerate", "24", "-i", "desktop"]

                    if disp_audio:
                        cmd.extend(["-f", "dshow", "-i", f"audio={disp_audio}"])

                    cmd.extend(["-vf", "scale=1280:720"])
                    cmd.extend(enc_flags)
                    cmd.extend(["-r", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])

                    if disp_audio:
                        cmd.extend(["-c:a", "aac", "-b:a", "128k"])

                    cmd.append(ruta_salida_mp4)

                si, flags = obtener_startupinfo_y_flags()
                log_mentor_f = open(LOG_FFMPEG_FILE, "a", encoding="utf-8", errors="replace")
                log_mentor_f.write(f"\n--- [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] GRABACION INICIADA: {titulo_limpio} ---\n")
                log_mentor_f.write(f"Comando: {' '.join(cmd)}\n")
                log_mentor_f.flush()

                proc_ffmpeg = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=log_mentor_f,
                    stderr=subprocess.STDOUT,
                    startupinfo=si,
                    creationflags=flags
                )

                # VALIDACIÓN DINÁMICA ANTI-CRASH:
                # Si el encoder por hardware falla al inicializar con el desktop,
                # detectamos la caída en los primeros 1.5s y activamos el PLAN B (Software libx264 ultrafast threads 2)
                if not is_voice_chat:
                    await asyncio.sleep(1.5)
                    if proc_ffmpeg.poll() is not None:
                        print(f"\n[Recorder Mentoría] ⚠️ El encoder '{enc_nombre}' falló al arrancar (código {proc_ffmpeg.returncode}).")
                        print("[Recorder Mentoría] 🛡️ [ACTIVANDO PLAN B] Cayendo a codificación segura libx264 (-preset ultrafast, -threads 2)...")

                        cmd_fallback = [FFMPEG_EXE, "-y", "-f", "gdigrab", "-framerate", "24", "-i", "desktop"]
                        if disp_audio:
                            cmd_fallback.extend(["-f", "dshow", "-i", f"audio={disp_audio}"])
                        cmd_fallback.extend([
                            "-vf", "scale=1280:720",
                            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-crf", "26",
                            "-r", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart"
                        ])
                        if disp_audio:
                            cmd_fallback.extend(["-c:a", "aac", "-b:a", "128k"])
                        cmd_fallback.append(ruta_salida_mp4)

                        log_mentor_f.write(f"\n--- [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FALLBACK A PLAN B SOFTWARE (libx264 threads=2) ---\n")
                        log_mentor_f.write(f"Comando: {' '.join(cmd_fallback)}\n")
                        log_mentor_f.flush()

                        proc_ffmpeg = subprocess.Popen(
                            cmd_fallback,
                            stdin=subprocess.PIPE,
                            stdout=log_mentor_f,
                            stderr=subprocess.STDOUT,
                            startupinfo=si,
                            creationflags=flags
                        )
                        await asyncio.sleep(1.0)
                        if proc_ffmpeg.poll() is None:
                            print("[Recorder Mentoría] ✅ [PLAN B ACTIVO] Grabación de emergencia por software estabilizada.")

                print("[Recorder Mentoría] 🔴 Grabando mentoría (Autocorte inteligente activado)...")

                t_inicio = time.time()

                max_segundos = max_horas * 3600

                while True:

                    transcurrido = int(time.time() - t_inicio)

                    sys.stdout.write(f"\r   Grabando Mentoría en vivo... {transcurrido // 60}m {transcurrido % 60}s transcurridos (Mic/Cámara: OFF)")

                    sys.stdout.flush()

                    if transcurrido >= max_segundos:

                        print("\n[Recorder Mentoría] ⏱️ Límite máximo de seguridad alcanzado (5h). Cerrando grabación...")

                        break

                    if os.path.exists(ARCHIVO_FRENO_MANUAL) or (id_clase and database.es_clase_cancelada(id_clase)):

                        print("\n[Recorder Mentoría] 🛑 Parada o cancelación manual solicitada por el usuario. Cortando grabación...")

                        try:

                            if os.path.exists(ARCHIVO_FRENO_MANUAL):

                                os.remove(ARCHIVO_FRENO_MANUAL)

                        except Exception:

                            pass

                        break

                    if transcurrido > 30 and transcurrido % 10 == 0:

                        try:

                            if page.is_closed():

                                print("\n[Recorder Mentoría] 🏁 Pestaña de la reunión cerrada. Finalizando grabación...")

                                break

                            texto_pag = (await page.evaluate("() => document.body ? document.body.innerText : ''")).lower()

                            frases_fin = [

                                "el anfitrión ha finalizado esta reunión",

                                "the host has ended this meeting",

                                "esta reunión ha sido finalizada por el anfitrión",

                                "meeting has been ended by host",

                                "thank you for attending",

                                "gracias por asistir",

                            ]

                            if any(f in texto_pag for f in frases_fin):

                                print("\n[Recorder Mentoría] 🏁 ¡El mentor ha finalizado la reunión de Zoom! Cortando grabación automáticamente...")

                                break

                        except Exception:

                            pass

                    await asyncio.sleep(2)

            finally:

                # a) Caza de FFmpeg zombi: verificación y terminación forzosa en 5s si no responde

                if proc_ffmpeg and proc_ffmpeg.poll() is None:

                    print("\n[Recorder Mentoría] 🛑 Finalizando proceso de FFmpeg...")

                    try:

                        if proc_ffmpeg.stdin:

                            proc_ffmpeg.stdin.write(b"q\n")

                            proc_ffmpeg.stdin.flush()

                        proc_ffmpeg.wait(timeout=5)

                    except Exception:

                        pass

                    if proc_ffmpeg.poll() is None:

                        try:

                            proc_ffmpeg.terminate()

                            proc_ffmpeg.wait(timeout=5)

                        except Exception:

                            pass

                    if proc_ffmpeg.poll() is None:

                        try:

                            proc_ffmpeg.kill()

                        except Exception:

                            pass

                # b) Cierre explícito de la pestaña de Chrome

                try:

                    if page and not page.is_closed():

                        await page.close()

                        print("[Recorder Mentoría] 🚪 Pestaña de reunión cerrada limpiamente.")

                except Exception:

                    pass

                # c) Cierre explícito de la conexión de Playwright con el CDP

                try:

                    if browser:

                        await browser.disconnect()

                except Exception:

                    pass

    except Exception as e:

        print(f"\n[!] Error durante la grabación de la mentoría: {e}")

        return False

    finally:

        if zoom_id_room:

            SALAS_ZOOM_ACTIVAS.discard(zoom_id_room)

        gc.collect()

    return verificar_integridad_video(ruta_salida_mp4)

async def grabar_llamada_telegram_web(

    chat_title: str,

    ruta_salida_mp4: str,

    chat_id: Optional[int] = None,

    mentor: str = "Mentor",

    max_horas: int = 5,

    cdp_url: str = "http://localhost:9222",

    id_clase: Optional[str] = None,

) -> bool:

    """

    Se une a una llamada de voz/video en Telegram Web de forma autónoma:

    - Abre o reutiliza pestaña de Telegram Web (web.telegram.org) vía CDP en Chrome.

    - Bloquea micrófono y cámara a nivel DOM (Micrófono/Cámara estrictamente OFF).

    - Localiza el grupo o canal y pulsa 'Unirse' / 'Join' en la barra de Voice Chat.

    - Inicia grabación digital limpia con FFmpeg.

    - Monitorea constantemente el DOM de Telegram Web en busca de 'Llamada finalizada' o cierre de la llamada.

    - Cierra limpiamente la pestaña y los subprocesos en un bloque finally infalible.

    """

    from playwright.async_api import async_playwright

    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida_mp4)), exist_ok=True)

    if os.path.exists(ARCHIVO_FRENO_MANUAL):

        try:

            os.remove(ARCHIVO_FRENO_MANUAL)

        except Exception:

            pass

    print(f"\n[Recorder Telegram Web] 🎙️ Conectando a Telegram Web para capturar llamada en '{chat_title}' (Mentor: {mentor})...")

    browser = None

    page = None

    proc_ffmpeg = None

    try:

        async with async_playwright() as p:

            try:

                browser = await p.chromium.connect_over_cdp(cdp_url)

                context = browser.contexts[0]

                # Buscar si ya hay una pestaña de Telegram Web abierta

                tg_page = None

                for pg in context.pages:

                    if "web.telegram.org" in pg.url.lower():

                        tg_page = pg

                        break

                if not tg_page:

                    tg_page = await context.new_page()

                    print("[Recorder Telegram Web] Navegando a Telegram Web...")

                    await tg_page.goto("https://web.telegram.org/k/", wait_until="domcontentloaded", timeout=30000)

                    await asyncio.sleep(4)

                else:

                    print("[Recorder Telegram Web] Reutilizando pestaña existente de Telegram Web.")

                    await tg_page.bring_to_front()

                page = tg_page

                # 1. Blindar privacidad: Micrófono y cámara estrictamente OFF

                await page.add_init_script("""() => {

                    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {

                        const orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);

                        navigator.mediaDevices.getUserMedia = async (c) => {

                            if (c && (c.audio || c.video)) {

                                throw new DOMException('Permission denied by Bot Privacy Guard', 'NotAllowedError');

                            }

                            return orig(c);

                        };

                    }

                }""")

                # 2. Localizar el chat en la interfaz de Telegram Web

                print(f"[Recorder Telegram Web] Buscando chat '{chat_title}' en la lista...")

                chat_encontrado = False

                try:

                    chat_elem = page.locator(f"text='{chat_title}'").first

                    if await chat_elem.count() > 0:

                        await chat_elem.click()

                        chat_encontrado = True

                        await asyncio.sleep(2)

                except Exception:

                    pass

                if not chat_encontrado:

                    try:

                        search_input = page.locator("input.input-field-input, input[placeholder*='Search' i], input[placeholder*='Buscar' i]").first

                        if await search_input.count() > 0:

                            await search_input.fill(chat_title)

                            await asyncio.sleep(2)

                            first_result = page.locator(f".chatlist text='{chat_title}', .search-group text='{chat_title}'").first

                            if await first_result.count() > 0:

                                await first_result.click()

                                chat_encontrado = True

                                await asyncio.sleep(2)

                    except Exception:

                        pass

                # 3. Detectar barra o botón de llamada grupal (Voice Chat)

                print("[Recorder Telegram Web] Buscando barra de Voice Chat activa...")

                btn_unirse = page.locator("button:has-text('Unirse'), button:has-text('Join'), .group-call-panel button, [class*='group-call'] button").first

                if await btn_unirse.count() > 0:

                    try:

                        await btn_unirse.click()

                        print("[Recorder Telegram Web] 🟢 Clic en 'Unirse' a la llamada grupal.")

                        await asyncio.sleep(3)

                        btn_confirm = page.locator("button:has-text('Unirme'), button:has-text('Join as'), .popup button:has-text('Join')").first

                        if await btn_confirm.count() > 0:

                            await btn_confirm.click()

                            await asyncio.sleep(2)

                    except Exception as e_join:

                        print(f"[Recorder Telegram Web] Aviso pulsando Unirse: {e_join}")

                # 4. Iniciar grabación de audio limpio con FFmpeg

                dispositivos = detectar_dispositivos_audio()

                disp_audio = dispositivos[0] if dispositivos else None

                cmd = [FFMPEG_EXE, "-y"]

                if disp_audio:

                    cmd.extend(["-f", "dshow", "-i", f"audio={disp_audio}"])

                else:

                    cmd.extend(["-f", "dshow", "-i", "audio=dummy"])

                cmd.extend(["-vn", "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", ruta_salida_mp4])

                si = subprocess.STARTUPINFO() if sys.platform == "win32" else None

                if si:

                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                    si.wShowWindow = 0

                proc_ffmpeg = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)

                print(f"[Recorder Telegram Web] 🔴 Grabando llamada en vivo de Telegram (Autocorte inteligente por DOM activado)...")

                t_inicio = time.time()

                max_segundos = max_horas * 3600

                while True:

                    transcurrido = int(time.time() - t_inicio)

                    sys.stdout.write(f"\r   Grabando Telegram Web... {transcurrido // 60}m {transcurrido % 60}s (Mic/Cámara: OFF)")

                    sys.stdout.flush()

                    if transcurrido >= max_segundos:

                        print("\n[Recorder Telegram Web] ⏱️ Límite máximo de seguridad alcanzado (5h).")

                        break

                    if os.path.exists(ARCHIVO_FRENO_MANUAL) or (id_clase and database.es_clase_cancelada(id_clase)):

                        print("\n[Recorder Telegram Web] 🛑 Cancelación o freno manual detectado.")

                        try:

                            if os.path.exists(ARCHIVO_FRENO_MANUAL):

                                os.remove(ARCHIVO_FRENO_MANUAL)

                        except Exception:

                            pass

                        break

                    # Monitor inteligente del DOM de Telegram Web

                    if transcurrido > 30 and transcurrido % 6 == 0:

                        try:

                            if page.is_closed():

                                print("\n[Recorder Telegram Web] 🏁 Pestaña de Telegram cerrada. Finalizando grabación...")

                                break

                            texto_dom = (await page.evaluate("() => document.body ? document.body.innerText : ''")).lower()

                            frases_fin = [

                                "llamada finalizada",

                                "voice chat ended",

                                "el chat de voz ha terminado",

                                "el chat de voz ha finalizado",

                                "la llamada ha finalizado",

                                "group call ended",

                                "call ended",

                                "has ended the group call",

                            ]

                            if any(f in texto_dom for f in frases_fin):

                                print("\n[Recorder Telegram Web] 🏁 ¡Llamada finalizada detectada en el DOM de Telegram Web! Cortando grabación automáticamente...")

                                break

                        except Exception:

                            pass

                    await asyncio.sleep(2)

            finally:

                if proc_ffmpeg and proc_ffmpeg.poll() is None:

                    print("\n[Recorder Telegram Web] 🛑 Finalizando proceso de FFmpeg...")

                    try:

                        if proc_ffmpeg.stdin:

                            proc_ffmpeg.stdin.write(b"q\n")

                            proc_ffmpeg.stdin.flush()

                        proc_ffmpeg.wait(timeout=5)

                    except Exception:

                        pass

                    if proc_ffmpeg.poll() is None:

                        try:

                            proc_ffmpeg.terminate()

                            proc_ffmpeg.wait(timeout=5)

                        except Exception:

                            pass

                    if proc_ffmpeg.poll() is None:

                        try:

                            proc_ffmpeg.kill()

                        except Exception:

                            pass

                try:

                    if browser:

                        await browser.disconnect()

                except Exception:

                    pass

    except Exception as e:

        print(f"\n[!] Error grabando llamada en Telegram Web: {e}")

        return False

    return verificar_integridad_video(ruta_salida_mp4)

def generar_ruta_grabacion(titulo_original: str, fecha_str: str, es_mentoria: bool = False) -> str:

    nombre_limpio = database.normalizar_id(titulo_original).replace(" ", "_")

    fecha_limpia = re.sub(r"[^0-9_-]", "", fecha_str.replace(":", "-"))

    if not fecha_limpia:

        fecha_limpia = datetime.datetime.now().strftime("%Y-%m-%d")

    base_destino = os.path.join(DIR_GRABACIONES, "mentorias") if es_mentoria else DIR_GRABACIONES

    carpeta_clase = os.path.join(base_destino, nombre_limpio)

    os.makedirs(carpeta_clase, exist_ok=True)

    return os.path.join(carpeta_clase, f"{nombre_limpio}_{fecha_limpia}.mp4")

def verificar_integridad_video(ruta_video: str) -> bool:

    if not os.path.exists(ruta_video) or os.path.getsize(ruta_video) < 2048:

        return False

    try:

        res = subprocess.run([FFMPEG_EXE, "-v", "error", "-t", "5", "-i", ruta_video, "-f", "null", "-"], capture_output=True, text=True, errors="replace", timeout=20)

        return res.returncode == 0

    except Exception:

        return False

async def grabar_clase_completa(

    clase_info: Dict[str, Any],

    margen_extra_minutos: int = 5,

    duracion_segundos: Optional[int] = None,

) -> Optional[str]:

    titulo = clase_info.get("titulo_original", "Masterclass")

    id_clase = clase_info.get("id_clase", database.normalizar_id(titulo))

    url_hotmart = clase_info.get("url_hotmart") or ""

    duracion_min = clase_info.get("duracion_min", 60)

    fecha_str = clase_info.get("fecha", datetime.date.today().strftime("%Y-%m-%d"))

    es_mentoria = (

        "zoom.us" in url_hotmart.lower()

        or "chat_voz_telegram" in url_hotmart.lower()

        or "mentoria" in id_clase.lower()

        or "mentoría" in titulo.lower()

        or clase_info.get("transversal") == "Mentorías"

    )

    num_parte = 0

    if clase_info.get("analisis_json"):

        try:

            num_parte = json.loads(clase_info["analisis_json"]).get("numero_parte_hotmart", 0)

        except Exception:

            pass

    database.guardar_o_actualizar_clase(id_clase=id_clase, titulo_original=titulo, estado="GRABANDO")

    ruta_video = generar_ruta_grabacion(titulo, fecha_str, es_mentoria=es_mentoria)

    prevenir_suspension_sistema(True)

    try:

        if es_mentoria and ("zoom.us" in url_hotmart.lower() or "chat_voz_telegram" in url_hotmart.lower()):

            ok_zoom = await grabar_mentoria_zoom_o_voz(

                url_objetivo=url_hotmart,

                ruta_salida_mp4=ruta_video,

                nombre_participante="David Herbas",

                id_clase=id_clase,

            )

            if ok_zoom and os.path.exists(ruta_video):

                print(f"\n[Recorder] ✅ Mentoría grabada con éxito en carpeta de mentorías: {ruta_video}")

                return ruta_video

            return None

        url_res = await preparar_reproductor_hotmart(url_clase=url_hotmart, titulo_clase=titulo, num_parte=num_parte)

        if url_res and isinstance(url_res, str):

            url_hotmart = url_res

            database.guardar_o_actualizar_clase(id_clase=id_clase, titulo_original=titulo, estado="GRABANDO", url_hotmart=url_hotmart)

        segundos_totales = duracion_segundos if duracion_segundos and duracion_segundos > 0 else (duracion_min + margen_extra_minutos) * 60

        ok_stream = await grabar_stream_hotmart(

            segundos=segundos_totales,

            ruta_salida_mp4=ruta_video,

            url_clase=url_hotmart,

            titulo_clase=titulo,

            num_parte=num_parte,

            id_clase=id_clase,

        )

        if ok_stream and os.path.exists(ruta_video) and verificar_integridad_video(ruta_video):

            print(f"\n[Recorder] ✅ Grabación finalizada y verificada con éxito: {ruta_video}")

            return ruta_video

        # SALVAGUARDA ANTI-DESTRUCCIÓN:
        # Si la conversión a MP4 falló pero el video crudo WebM fue preservado:
        patron_webm = os.path.splitext(ruta_video)[0] + "_*.webm"
        webms = glob.glob(patron_webm)
        if webms:
            webms.sort(key=os.path.getmtime, reverse=True)
            ultimo_webm = webms[0]
            if os.path.exists(ultimo_webm) and os.path.getsize(ultimo_webm) > 5 * 1024 * 1024:
                print(f"\n[Recorder] 🛡️ [SALVAGUARDA ANTI-DESTRUCCIÓN] Grabación preservada en formato crudo: {ultimo_webm}")
                database.guardar_o_actualizar_clase(id_clase=id_clase, titulo_original=titulo, estado="ERROR_REMUXING", ruta_archivo=ultimo_webm, duracion_min=duracion_min)
                return ultimo_webm

        print("\n[Recorder] ❌ El bot no pudo engancharse al video de Chrome o falló la grabación. Abortando y cerrando pestaña aislada...")

        await cerrar_pestana_clase(titulo)

        return None

    finally:

        prevenir_suspension_sistema(False)

        restaurar_consola()

        gc.collect()