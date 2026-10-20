"""

main.py - Orquestador Principal del Sistema Automatizado de Grabación y Sincronización

Incluye:

- Sala de Espera (Queue) dinámica para Python 3.8.

- Margen Inteligente para clases seguidas.

- Lectura automática de Mentorías agendadas por el Vigía o el Programador Manual.

- Detector de Mentor con IA analizando los primeros 3 minutos de audio.

"""

import asyncio

import base64

import datetime

import glob

import functools

import json

import os

import re

import sqlite3

import subprocess

import sys

import time

from typing import Optional, Dict, Any, List, Tuple

if sys.platform == "win32":

    try:

        sys.stdout.reconfigure(encoding="utf-8")

        sys.stderr.reconfigure(encoding="utf-8")

    except Exception:

        pass

import pytz

import requests

import schedule

import ai_analyzer

import calendar_sync

import database

import notebooklm_bot

import recorder

import route_builder

import scraper

import telegram_uploader

import visual_generator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")

DB_FILE = getattr(database, "DB_FILE", getattr(database, "DB_PATH", os.path.join(BASE_DIR, "clases.db")))

COLA_POST_PROCESO = None

CLASES_EN_EJECUCION = set()

COOLDOWN_REINTENTOS: Dict[str, float] = {}

DELAY_REINTENTO_FALLO_SEGUNDOS: int = 600  # 10 minutos de delay de seguridad anti-inundación de RAM

# ==============================================================================

# SEMÁFORO DE RED Y CPU (Protección de Grabaciones en Vivo contra Congestión)

# ==============================================================================

TOTAL_GRABACIONES_ACTIVAS: int = 0

GRABACION_EN_CURSO: bool = False

def registrar_inicio_grabacion(titulo: str = ""):

    global TOTAL_GRABACIONES_ACTIVAS, GRABACION_EN_CURSO

    TOTAL_GRABACIONES_ACTIVAS += 1

    GRABACION_EN_CURSO = True

    print(f"\n[Semáforo Red/CPU] 🔴 Grabación en curso ('{titulo}'). Semáforo en ROJO.")

    print("[Semáforo Red/CPU] ⏸️ Subidas pesadas y tareas intensivas en pausa para garantizar 0% buffering y CPU baja.")

def registrar_fin_grabacion(titulo: str = ""):

    global TOTAL_GRABACIONES_ACTIVAS, GRABACION_EN_CURSO

    TOTAL_GRABACIONES_ACTIVAS = max(0, TOTAL_GRABACIONES_ACTIVAS - 1)

    GRABACION_EN_CURSO = (TOTAL_GRABACIONES_ACTIVAS > 0)

    if not GRABACION_EN_CURSO:

        print(f"\n[Semáforo Red/CPU] 🟢 Grabaciones finalizadas ('{titulo}'). Semáforo en VERDE.")

        print("[Semáforo Red/CPU] ▶️ Cola de post-proceso y subidas pesadas reanudadas.")

async def esperar_semaforo_red(contexto: str = ""):

    """Bloquea subidas pesadas a Telegram y procesamiento mientras haya grabaciones activas."""

    if GRABACION_EN_CURSO:

        print(f"\n[Semáforo Red/CPU] 🟡 '{contexto}' esperando en cola (Grabación en curso protegiendo Red/CPU)...")

        while GRABACION_EN_CURSO:

            await asyncio.sleep(10)

        print(f"[Semáforo Red/CPU] 🟢 Vía libre para '{contexto}'. Iniciando operación...")

def get_cola():

    global COLA_POST_PROCESO

    if COLA_POST_PROCESO is None:

        COLA_POST_PROCESO = asyncio.Queue()

    return COLA_POST_PROCESO

def cargar_config() -> Dict[str, Any]:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:

        return json.load(f)

async def ejecutar_en_segundo_plano_bloqueante(func, *args, **kwargs):

    loop = asyncio.get_running_loop()

    pfunc = functools.partial(func, *args, **kwargs)

    return await loop.run_in_executor(None, pfunc)

def detectar_mentor_primeros_3_min(ruta_video: str, cfg: Dict[str, Any]) -> str:

    if not os.path.exists(ruta_video):

        return "Sin Identificar"

    api_key = cfg.get("gemini_api_key", "")

    modelo_cfg = cfg.get("gemini_model", "gemini-2.5-flash")

    if not api_key:

        return "Sin Identificar"

    ruta_clip = os.path.join(os.path.dirname(ruta_video), "temp_mentor_3min.mp3")

    cmd = [

        FFMPEG_EXE, "-y",

        "-t", "180",

        "-i", ruta_video,

        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",

        ruta_clip,

    ]

    try:

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)

        if not os.path.exists(ruta_clip) or os.path.getsize(ruta_clip) < 1024:

            return "Sin Identificar"

        # CLOUD OFFLOADING & STREAMING: Subir audio ligero a Gemini File API por streaming
        audio_part = None
        file_uri = ai_analyzer.subir_audio_gemini(ruta_clip, gemini_key)
        if file_uri:
            audio_part = {"file_data": {"file_uri": file_uri, "mime_type": "audio/mp3"}}
        else:
            with open(ruta_clip, "rb") as f:
                b64_audio = base64.b64encode(f.read()).decode("utf-8")
            audio_part = {"inline_data": {"mime_type": "audio/mp3", "data": b64_audio}}

        prompt = (

            "Escucha estos primeros 3 minutos de una mentoría de Universidad Online. "

            "Identifica el nombre del mentor, profesor o experto que imparte la clase (si se presenta o lo presentan). "

            "Responde ÚNICAMENTE en JSON válido con este formato exacto: "

            '{"mentor": "Nombre Apellido"} '

            'Si no se menciona ningún nombre con claridad, responde exactamente: {"mentor": "Sin Identificar"}'

        )

        payload = {

            "contents": [{

                "parts": [

                    {"text": prompt},

                    audio_part,

                ]

            }],

            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1},

        }

        for mod in dict.fromkeys([modelo_cfg, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]):

            if not mod:

                continue

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"

            try:

                r = requests.post(url, json=payload, timeout=45)

                if r.status_code == 200:

                    texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]

                    datos = json.loads(texto.replace("```json", "").replace("```", "").strip())

                    mentor = (datos.get("mentor") or "Sin Identificar").strip()

                    return mentor if mentor else "Sin Identificar"

            except Exception:

                continue

    except Exception as e:

        print(f"[!] Aviso al detectar mentor en primeros 3 min: {e}")

    finally:

        if os.path.exists(ruta_clip):

            try:

                os.remove(ruta_clip)

            except Exception:

                pass

    return "Sin Identificar"

async def worker_post_proceso():

    while True:

        tarea = await get_cola().get()

        titulo = tarea["clase_info"].get("titulo_original", "Desconocido")

        # Semáforo de Red y CPU: Pausar subidas pesadas mientras haya grabaciones en vivo activas

        await esperar_semaforo_red(f"Post-proceso y subida de '{titulo}'")

        print(f"\n[Sala de Espera] 🚦 Turno iniciado para procesar y subir: '{titulo}'")

        try:

            await tarea_post_procesamiento(**tarea)

        except Exception as e:

            print(f"[!] Error crítico en worker post-proceso para '{titulo}': {e}")

        finally:

            get_cola().task_done()

            print(f"[Sala de Espera] ✅ Turno finalizado para '{titulo}'.")

def sincronizar_calendario_y_bd() -> List[Dict[str, Any]]:

    if GRABACION_EN_CURSO:

        print(f"\n[Orquestador] ⚠️ Grabación activa en curso. Se omite scraper pesado para no sobrecargar CPU ni robar foco.")

        return []

    print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Orquestador] Sincronizando horarios...")

    try:

        return scraper.ejecutar_scraper_y_sincronizacion()

    except Exception as exc:

        print(f"[!] Error durante la sincronización: {exc}")

        return []

def obtener_pendientes_desde_sqlite() -> List[Dict[str, Any]]:

    lista = []

    if not os.path.exists(DB_FILE):

        return lista

    try:

        conn = sqlite3.connect(DB_FILE)

        conn.row_factory = sqlite3.Row

        cur = conn.cursor()

        cur.execute("SELECT * FROM clases_grabadas WHERE estado = 'PENDIENTE'")

        filas = cur.fetchall()

        conn.close()

        for r in filas:

            d = dict(r)

            ini = d.get("fecha_grabacion") or ""

            dur = int(d.get("duracion_min") or 60)

            if ini and "T" in ini:

                try:

                    dt_ini = datetime.datetime.fromisoformat(ini)

                    fin = (dt_ini + datetime.timedelta(minutes=dur)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

                except Exception:

                    fin = ini

                lista.append({

                    "id_clase": d["id_clase"],

                    "titulo_original": d["titulo_original"],

                    "inicio_iso": ini,

                    "fin_iso": fin,

                    "duracion_min": dur,

                    "url_hotmart": d.get("url_hotmart") or "",

                    "transversal": d.get("transversal") or "",

                    "analisis_json": d.get("analisis_json") or "",

                })

    except Exception:

        pass

    return lista

def seleccionar_clase_mas_proxima_hoy(config: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], str]:

    cfg = config or cargar_config()

    tz_local = pytz.timezone(cfg.get("timezone_local", "America/La_Paz"))

    ahora = datetime.datetime.now(tz_local)

    try:

        clases, _ = scraper.obtener_clases_inteligente(preferir_navegador=True, config=cfg)

    except Exception:

        clases = []

    clases_hoy = [c for c in clases if c.get("dia") == "HOY"]

    for c in clases_hoy:

        try:

            dt_ini = datetime.datetime.fromisoformat(c["inicio_iso"])

            dt_fin = datetime.datetime.fromisoformat(c["fin_iso"])

            if dt_ini <= ahora <= dt_fin:

                return c, "🔴 EN VIVO AHORA"

        except Exception:

            continue

    for c in clases_hoy:

        if "onboarding" in c.get("id_clase", "").lower() or "onboarding" in c.get("titulo_original", "").lower():

            c["url_hotmart"] = "https://hotmart.com/es/club/suscripcionuniversidadonline/products/7048143/content/a4RKyKMRen"

            return c, "🎬 CLASE PROGRAMADA HOY"

    if clases:

        return clases[0], "📅 CLASE DETECTADA"

    return {

        "id_clase": "onboarding",

        "titulo_original": "Onboarding",

        "dia": "HOY",

        "inicio_iso": ahora.strftime("%Y-%m-%dT%H:%M:%S-04:00"),

        "fin_iso": (ahora + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S-04:00"),

    }, "🛡️ RESPALDO"

async def tarea_post_procesamiento(

    clase_info: Dict[str, Any],

    ruta_video_final: str,

    duracion_min: int,

    cal_id: str,

    cal_titulo_base: str,

    cal_inicio_iso: str,

    cal_fin_iso: str,

    cfg: Dict[str, Any],

):

    id_clase = clase_info["id_clase"]

    titulo = clase_info["titulo_original"]

    url_hotmart = clase_info.get("url_hotmart") or ""

    fecha_formateada = datetime.date.today().strftime("%d/%m/%Y")

    es_mentoria = (

        "mentoria" in id_clase.lower()

        or "mentoría" in titulo.lower()

        or "zoom.us" in url_hotmart.lower()

        or clase_info.get("transversal") == "Mentorías"

    )

    mentor_identificado = ""

    if es_mentoria:

        print(f"\n[Post-Proceso] 🕵️‍♂️ Escuchando primeros 3 minutos para identificar al Mentor de '{titulo}'...")

        mentor_identificado = await ejecutar_en_segundo_plano_bloqueante(

            detectar_mentor_primeros_3_min, ruta_video_final, cfg

        )

        print(f"[Post-Proceso] 🎙️ Resultado identificación de Mentor: '{mentor_identificado}'")

        if "mentor:" not in titulo.lower():

            titulo = f"{titulo} (Mentor: {mentor_identificado})"

            cal_titulo_base = titulo

        try:

            carpeta_v = os.path.dirname(ruta_video_final)

            slug_mentor = database.normalizar_id(mentor_identificado).replace(" ", "_")

            base_actual = os.path.splitext(os.path.basename(ruta_video_final))[0]

            if slug_mentor and slug_mentor not in base_actual.lower():

                nueva_ruta_mp4 = os.path.join(carpeta_v, f"{base_actual}_mentor_{slug_mentor}.mp4")

                os.replace(ruta_video_final, nueva_ruta_mp4)

                ruta_video_final = nueva_ruta_mp4

                print(f"[Post-Proceso] 📁 Video renombrado a: {os.path.basename(ruta_video_final)}")

        except Exception as e_ren:

            print(f"[Aviso] No se pudo renombrar archivo local: {e_ren}")

    print(f"\n[Post-Proceso] ⚙️ Extrayendo audio completo ligero para IA de '{titulo}'...")

    ruta_mp3 = await ejecutar_en_segundo_plano_bloqueante(ai_analyzer.extraer_audio_ligero, ruta_video_final)

    print("[Post-Proceso] ⚙️ Analizando contenido con Gemini...")

    analisis = await ejecutar_en_segundo_plano_bloqueante(ai_analyzer.analizar_clase_con_gemini, titulo, ruta_mp3)

    if not analisis:

        analisis = {"transversal": "Mentorías" if es_mentoria else "General", "nivel": 1, "resumen_didactico": "Sesión completada."}

    if es_mentoria:

        analisis["transversal"] = "Mentorías"

        analisis["mentor_identificado"] = mentor_identificado or "Sin Identificar"

    await ejecutar_en_segundo_plano_bloqueante(database.guardar_analisis_clase, id_clase, analisis)

    carpeta_video = os.path.dirname(ruta_video_final)

    ruta_md = os.path.join(carpeta_video, f"Ficha_Didactica_{id_clase}.md")

    await ejecutar_en_segundo_plano_bloqueante(ai_analyzer.generar_ficha_markdown, analisis, titulo, fecha_formateada, ruta_md)

    print("[Post-Proceso] ⚙️ Sincronizando con NotebookLM...")

    res_nlm = await notebooklm_bot.procesar_clase_en_notebooklm(clase_info, analisis, ruta_mp3, ruta_md)

    notebook_url = res_nlm.get("notebook_url") if isinstance(res_nlm, dict) else None

    ruta_podcast = res_nlm.get("podcast_archivo") if isinstance(res_nlm, dict) else None

    print("[Post-Proceso] ⚙️ Generando Mapas Mentales visuales...")

    recursos_visuales = await visual_generator.generar_recursos_visuales(analisis, titulo, id_clase, carpeta_video)

    print("[Post-Proceso] ⚙️ Subiendo paquete a Telegram...")

    res_tg = await telegram_uploader.subir_entrega_completa_telegram(

        ruta_video=ruta_video_final,

        titulo_clase=titulo,

        fecha_clase=fecha_formateada,

        duracion_min=duracion_min,

        analisis=analisis,

        notebook_url=notebook_url,

        ruta_podcast=ruta_podcast,

        ruta_infografia_png=recursos_visuales.get("infografia_png") if isinstance(recursos_visuales, dict) else None,

        ruta_mapa_mental_png=recursos_visuales.get("mapa_mental_png") if isinstance(recursos_visuales, dict) else None,

        ruta_md_guia=ruta_md,

    )

    tg_url = res_tg.get("telegram_url") if isinstance(res_tg, dict) else ""

    tg_app_url = res_tg.get("telegram_app_url") if isinstance(res_tg, dict) else ""

    tg_web_url = res_tg.get("telegram_web_url") if isinstance(res_tg, dict) else ""

    await ejecutar_en_segundo_plano_bloqueante(

        database.guardar_o_actualizar_clase,

        id_clase, titulo, clase_info.get("inicio_iso"), "COMPLETADA", ruta_video_final,

        url_hotmart, tg_url, tg_app_url, tg_web_url,

    )

    await ejecutar_en_segundo_plano_bloqueante(database.guardar_analisis_clase, id_clase, analisis)

    print("[Post-Proceso] ⚙️ Actualizando App Web en GitHub Pages...")

    await ejecutar_en_segundo_plano_bloqueante(route_builder.generar_tablero_rutas, auto_deploy=True)

    await ejecutar_en_segundo_plano_bloqueante(

        calendar_sync.actualizar_estado_evento, cal_id, cal_titulo_base, "✅ [EN TELEGRAM]", cal_inicio_iso, cal_fin_iso, cfg

    )

    # =========================================================================

    # LIMPIEZA AUTOMÁTICA POST-PUBLICACIÓN (AUTO-BORRADO DE MULTIMEDIA PESADA)

    # 1) Subida a Telegram con éxito [OK]

    # 2) Procesada en NotebookLM [OK]

    # 3) Actualizada en la App Web [OK]

    # -> Purgar .mp4 y .m4a locales liberando RAM y Disco Duro

    # =========================================================================

    if tg_url:

        await ejecutar_en_segundo_plano_bloqueante(

            database.purgar_multimedia_local_clase, id_clase, ruta_video_final, ruta_podcast

        )

    print(f"\n🎉 [Post-Proceso] ¡TODAS LAS TAREAS DE '{titulo}' FUERON COMPLETADAS EXITOSAMENTE!")

async def procesar_flujo_clase(

    clase_info: Dict[str, Any],

    duracion_segundos: Optional[int] = None,

    config: Optional[Dict[str, Any]] = None,

    margen_extra_minutos: int = 5,

) -> bool:

    cfg = config or cargar_config()

    id_clase = clase_info["id_clase"]

    if id_clase in CLASES_EN_EJECUCION:

        return False

    CLASES_EN_EJECUCION.add(id_clase)

    try:

        titulo = clase_info["titulo_original"]

        inicio_iso = clase_info.get("inicio_iso") or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S-04:00")

        fin_iso = clase_info.get("fin_iso") or (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

        duracion_min = int(clase_info.get("duracion_min") or 60)

        # Validación cruzada de duración con inicio_iso y fin_iso

        try:

            dt_ini_c = datetime.datetime.fromisoformat(inicio_iso)

            dt_fin_c = datetime.datetime.fromisoformat(fin_iso)

            diff_min = int(round((dt_fin_c - dt_ini_c).total_seconds() / 60))

            if diff_min > 0 and diff_min != duracion_min:

                duracion_min = max(duracion_min, diff_min)

                clase_info["duracion_min"] = duracion_min

        except Exception:

            pass

        # -------------------------------------------------------------

        # HOT-CANCEL: RE-CONSULTA RÁPIDA ANTES DE LANZAR RECORDER

        # -------------------------------------------------------------

        clase_db = await ejecutar_en_segundo_plano_bloqueante(database.obtener_clase, id_clase)

        if clase_db and clase_db.get("estado") == "CANCELADO_MANUALMENTE":

            print(f"\n[Orquestador] 🛑 Grabación de '{titulo}' CANCELADA POR EL USUARIO (Estado: CANCELADO_MANUALMENTE).")

            print(f"[Orquestador] 🚪 Abortando tarea inmediatamente y liberando cola.")

            try:

                await recorder.cerrar_pestana_clase(titulo)

            except Exception:

                pass

            return False

        # -------------------------------------------------------------

        # ESCUDO ANTI-REPETICIÓN: Comprobar si ya existe grabación íntegra

        # -------------------------------------------------------------

        es_ment_check = (

            "mentoria" in id_clase.lower()

            or "mentoría" in titulo.lower()

            or "zoom.us" in (clase_info.get("url_hotmart") or "").lower()

            or clase_info.get("transversal") == "Mentorías"

        )

        ruta_previa = recorder.generar_ruta_grabacion(titulo, datetime.date.today().strftime("%Y-%m-%d"), es_mentoria=es_ment_check)

        reg_db = database.obtener_clase(id_clase)

        es_regrabacion = bool(reg_db and reg_db.get("regrabacion_activa") == 1)

        if not es_regrabacion and os.path.exists(ruta_previa) and recorder.verificar_integridad_video(ruta_previa) and os.path.getsize(ruta_previa) > 5 * 1024 * 1024:

            print(f"\n[Orquestador] 🛡️ Ya existe una grabación íntegra para '{titulo}' ({os.path.basename(ruta_previa)}).")

            print("[Orquestador] Evitando reinicio redundante de grabación. Derivando a post-proceso / Sala de Espera...")

            database.guardar_o_actualizar_clase(id_clase=id_clase, titulo_original=titulo, estado="COMPLETADA", ruta_archivo=ruta_previa, duracion_min=duracion_min)

            reg_db = database.obtener_clase(id_clase)

            if not reg_db or not reg_db.get("telegram_url"):

                ruta_video_final = await ejecutar_en_segundo_plano_bloqueante(telegram_uploader.asegurar_tamano_video, ruta_previa, duracion_min)

                await get_cola().put({

                    "clase_info": clase_info,

                    "ruta_video_final": ruta_video_final,

                    "duracion_min": duracion_min,

                    "cal_id": id_clase,

                    "cal_titulo_base": titulo,

                    "cal_inicio_iso": inicio_iso,

                    "cal_fin_iso": fin_iso,

                    "cfg": cfg,

                })

            return True

        if es_regrabacion:

            print(f"\n[Orquestador] 🔄 [Safe Overwrite] Re-grabación activa para '{titulo}'. Iniciando nueva captura...")

        print("\n" + "=" * 90)

        print(f"🎬 [Cerebro 1 - Grabador] INICIANDO CAPTURA: '{titulo}' ({duracion_min} min)")

        print("=" * 90)

        tz_local = pytz.timezone(cfg.get("timezone_local", "America/La_Paz"))

        ahora_local = datetime.datetime.now(tz_local)

        if duracion_segundos:

            cal_inicio_iso = ahora_local.strftime("%Y-%m-%dT%H:%M:%S-04:00")

            cal_fin_iso = (ahora_local + datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

            cal_id, cal_titulo_base = f"{id_clase}_prueba", f"{titulo} (Prueba)"

        else:

            cal_inicio_iso, cal_fin_iso = inicio_iso, fin_iso

            cal_id, cal_titulo_base = id_clase, titulo

        await ejecutar_en_segundo_plano_bloqueante(

            calendar_sync.actualizar_estado_evento, cal_id, cal_titulo_base, "🔴 [GRABANDO AHORA]", cal_inicio_iso, cal_fin_iso, cfg

        )

        registrar_inicio_grabacion(titulo)

        try:

            ruta_video = await recorder.grabar_clase_completa(clase_info, margen_extra_minutos, duracion_segundos)

        finally:

            registrar_fin_grabacion(titulo)

        if not ruta_video or not os.path.exists(ruta_video):

            # Salvaguarda Anti-Destrucción: Comprobar si existe el archivo crudo WebM preservado
            ruta_posible = recorder.generar_ruta_grabacion(titulo, datetime.date.today().strftime("%Y-%m-%d"), es_mentoria=es_ment_check)

            patron_webm = os.path.splitext(ruta_posible)[0] + "_*.webm"

            webms = glob.glob(patron_webm)

            if webms:

                webms.sort(key=os.path.getmtime, reverse=True)

                ultimo_webm = webms[0]

                if os.path.exists(ultimo_webm) and os.path.getsize(ultimo_webm) > 5 * 1024 * 1024:

                    print(f"\n[Orquestador] 🛡️ [Salvaguarda Anti-Destrucción] Video crudo preservado detectado: {ultimo_webm}")

                    print(f"[Orquestador] Salvando clase '{titulo}' en estado 'ERROR_REMUXING' sin activar delay destructivo.")

                    database.guardar_o_actualizar_clase(id_clase=id_clase, titulo_original=titulo, estado="ERROR_REMUXING", ruta_archivo=ultimo_webm, duracion_min=duracion_min)

                    ruta_video = ultimo_webm

        if not ruta_video or not os.path.exists(ruta_video):

            print(f"[!] Grabación fallida o abortada para '{titulo}'.")

            ahora_ts = time.time()

            COOLDOWN_REINTENTOS[id_clase] = ahora_ts + DELAY_REINTENTO_FALLO_SEGUNDOS

            dt_reintento = datetime.datetime.fromtimestamp(ahora_ts + DELAY_REINTENTO_FALLO_SEGUNDOS)

            print(

                f"[Orquestador] 🛡️ Delay de seguridad activado para '{titulo}': "

                f"Próximo reintento no antes de las {dt_reintento.strftime('%H:%M:%S')} (10 minutos) para evitar inundar RAM."

            )

            try:

                await recorder.cerrar_pestana_clase(titulo)

            except Exception:

                pass

            return False

        COOLDOWN_REINTENTOS.pop(id_clase, None)

        ruta_video_final = await ejecutar_en_segundo_plano_bloqueante(telegram_uploader.asegurar_tamano_video, ruta_video, duracion_min)

        print(f"\n[Orquestador] 🚀 Video de '{titulo}' guardado. Enviando a la SALA DE ESPERA...")

        await get_cola().put({

            "clase_info": clase_info,

            "ruta_video_final": ruta_video_final,

            "duracion_min": duracion_min,

            "cal_id": cal_id,

            "cal_titulo_base": cal_titulo_base,

            "cal_inicio_iso": cal_inicio_iso,

            "cal_fin_iso": cal_fin_iso,

            "cfg": cfg,

        })

        return True

    finally:

        CLASES_EN_EJECUCION.discard(id_clase)

async def procesar_ciclo_grabacion(clases_calendario: List[Dict[str, Any]]) -> None:

    cfg = cargar_config()

    tz_local = pytz.timezone(cfg.get("timezone_local", "America/La_Paz"))

    ahora = datetime.datetime.now(tz_local)

    clases_bd = obtener_pendientes_desde_sqlite()

    mapa_clases = {}

    for c_bd in clases_bd:

        mapa_clases[c_bd["id_clase"]] = c_bd

    for c_cal in clases_calendario:

        cid = c_cal["id_clase"]

        if cid in mapa_clases:

            # Preservar datos de BD pero actualizar inicio, fin, duracion y url con datos frescos del calendario

            mapa_clases[cid].update({

                "inicio_iso": c_cal.get("inicio_iso") or mapa_clases[cid].get("inicio_iso"),

                "fin_iso": c_cal.get("fin_iso") or mapa_clases[cid].get("fin_iso"),

                "duracion_min": c_cal.get("duracion_min") or mapa_clases[cid].get("duracion_min"),

                "url_hotmart": c_cal.get("url_hotmart") or mapa_clases[cid].get("url_hotmart"),

            })

        else:

            mapa_clases[cid] = c_cal

    todas_las_clases = list(mapa_clases.values())

    for c in todas_las_clases:

        id_clase = c["id_clase"]

        if id_clase in CLASES_EN_EJECUCION:

            continue

        if database.es_clase_completada(id_clase) or database.es_clase_cancelada(id_clase) or calendar_sync.debe_omitirse(c["titulo_original"], id_clase, cfg.get("palabras_ignorar", [])):

            continue

        # COMPROBACIÓN DE DELAY DE SEGURIDAD (Evita bucle infinito de pestañas si falla/aborta)

        ahora_ts = time.time()

        proximo_reintento = COOLDOWN_REINTENTOS.get(id_clase, 0)

        if ahora_ts < proximo_reintento:

            continue

        try:

            dt_inicio = datetime.datetime.fromisoformat(c["inicio_iso"])

            dt_fin = datetime.datetime.fromisoformat(c["fin_iso"])

        except Exception:

            continue

        tiempo_para_inicio = (dt_inicio - ahora).total_seconds()

        if -300 <= tiempo_para_inicio <= 300 or (dt_inicio <= ahora <= dt_fin):

            margen_dinamico = 5

            for otra in todas_las_clases:

                if otra["id_clase"] != id_clase and not database.es_clase_completada(otra["id_clase"]):

                    try:

                        otra_ini = datetime.datetime.fromisoformat(otra["inicio_iso"])

                        diff = (otra_ini - dt_fin).total_seconds()

                        if 0 <= diff < 300:

                            margen_dinamico = 0

                            print(f"\n⚠️ [Choque de Horarios] '{otra['titulo_original']}' empieza enseguida. Margen reducido a 0.")

                            break

                    except Exception:

                        pass

            print(f"\n🎯 [Orquestador] Horario alcanzado para: '{c['titulo_original']}'")

            asyncio.create_task(procesar_flujo_clase(c, duracion_segundos=None, config=cfg, margen_extra_minutos=margen_dinamico))

            await asyncio.sleep(2)

async def bucle_principal():

    print("=" * 100)

    print("       BOT UNIVERSIDAD ONLINE - ORQUESTADOR CONCURRENTE + DETECTOR DE MENTOR")

    print("=" * 100)

    print("✅ Multitarea y Sala de Espera (Queue) activa.")

    print("✅ Escucha activa de Mentorías de Zoom y Programador Manual cada 60s (Ultra-Bajo CPU).")

    print("✅ Identificación automática de Mentor en los primeros 3 minutos de audio.")

    print("=" * 100)

    asyncio.create_task(worker_post_proceso())

    clases_detectadas = sincronizar_calendario_y_bd()

    schedule.every(6).hours.do(sincronizar_calendario_y_bd)

    ts_ultimo_escaneo_vacio = 0

    while True:

        try:

            schedule.run_pending()

            ahora_ts = time.time()

            if not clases_detectadas and not GRABACION_EN_CURSO and (ahora_ts - ts_ultimo_escaneo_vacio >= 1800):

                ts_ultimo_escaneo_vacio = ahora_ts

                try:

                    res_sc = scraper.obtener_clases_inteligente(preferir_navegador=True)

                    if res_sc and len(res_sc) > 0:

                        clases_detectadas = res_sc[0]

                except Exception as e_sc:

                    print(f"[Aviso] No se pudo obtener clases del scraper: {e_sc}")

            await procesar_ciclo_grabacion(clases_detectadas)

            if get_cola().empty() and not GRABACION_EN_CURSO:

                for tarea in database.obtener_reintentos_notebooklm_listos():

                    print(f"\n🎯 [Orquestador] ⏳ Reanudando NotebookLM en cola para: '{tarea['titulo']}'...")

                    podcast_archivo = await notebooklm_bot.reintentar_tarea_encolada(tarea)

                    if podcast_archivo:

                        ruta_html = route_builder.generar_tablero_rutas()

                        analisis = json.loads(tarea["analisis_json"]) if tarea.get("analisis_json") else {}

                        asyncio.create_task(telegram_uploader.subir_entrega_completa_telegram(

                            titulo_clase=tarea["titulo"],

                            fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),

                            duracion_min=60,

                            analisis=analisis,

                            ruta_podcast=podcast_archivo,

                            ruta_html_rutas=ruta_html,

                        ))

        except KeyboardInterrupt:

            print("\n" + "=" * 80)

            print("⚠️ [SEGURIDAD BOT] ¿Seguro que quieres detener el bot de emergencia? (S/N): ", end="", flush=True)

            try:

                loop = asyncio.get_running_loop()

                resp = await loop.run_in_executor(None, input)

                if resp.strip().lower() == "s":

                    print("🛑 [Emergencia] Detención confirmada por el usuario. Limpiando tareas y saliendo...")

                    return

                else:

                    print("🛡️ [Seguridad] Falsa alarma (N). El bot continúa operando al 100% sin detenerse.\n")

            except Exception:

                print("🛡️ [Seguridad] Reanudando bot...\n")

        except Exception as e:

            print(f"[Aviso] Error en ciclo principal: {e}")

        try:

            await asyncio.sleep(60)

        except KeyboardInterrupt:

            print("\n" + "=" * 80)

            print("⚠️ [SEGURIDAD BOT] ¿Seguro que quieres detener el bot de emergencia? (S/N): ", end="", flush=True)

            try:

                loop = asyncio.get_running_loop()

                resp = await loop.run_in_executor(None, input)

                if resp.strip().lower() == "s":

                    print("🛑 [Emergencia] Detención confirmada por el usuario. Saliendo...")

                    return

                else:

                    print("🛡️ [Seguridad] Falsa alarma (N). El bot continúa operando al 100% sin detenerse.\n")

            except Exception:

                pass

async def ejecutar_prueba_60s():

    cfg = cargar_config()

    asyncio.create_task(worker_post_proceso())

    clase_sel, _ = seleccionar_clase_mas_proxima_hoy(cfg)

    await procesar_flujo_clase(clase_info=clase_sel, duracion_segundos=60, config=cfg)

    print("   🎉 ¡PRUEBA DEL BOT AUTOMÁTICO (60 SEGUNDOS) GRABADA CON ÉXITO! 🎉")

    await get_cola().join()

    return True

if __name__ == "__main__":

    database.init_db()

    while True:

        try:

            if len(sys.argv) > 1 and sys.argv[1] in ("--prueba-60s", "--test-60s"):

                asyncio.run(ejecutar_prueba_60s())

                break

            elif len(sys.argv) > 1 and sys.argv[1] == "--sync-now":

                sincronizar_calendario_y_bd()

                break

            else:

                asyncio.run(bucle_principal())

                break

        except KeyboardInterrupt:

            print("\n" + "=" * 80)

            print("⚠️ [SEGURIDAD BOT] ¿Seguro que quieres detener el bot de emergencia? (S/N): ", end="", flush=True)

            try:

                resp = input().strip().lower()

                if resp == "s":

                    print("🛑 [Emergencia] Proceso finalizado limpiamente por el usuario.")

                    sys.exit(0)

                else:

                    print("🛡️ [Seguridad] Reanudando orquestador...\n")

                    time.sleep(1)

            except Exception:

                sys.exit(0)