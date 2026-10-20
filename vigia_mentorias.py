"""

vigia_mentorias.py - Vigía Multimodal de Telegram y Detector de Llamadas de Voz (Voice Chats)

Monitorea canales y grupos de Universidad Online y Mentores:

- Reconoce automáticamente los canales clave (incluyendo 'Universidad.Online' y grupos privados).

- Captura en vivo llamadas vía Telegram Web con Playwright (aislado, mic/cam off, detección DOM) o audio loopback.

- Barrido histórico (Catch-Up) al iniciar para procesar todo lo enviado mientras el bot estuvo apagado.

- Deduplicación y reemplazo inteligente de audios oficiales de los mentores.

- Descarga y analiza contenido MULTIMODAL con Gemini AI (Flashcards, Quizzes, Infografías).

"""

import asyncio

import base64

import datetime

import json

import os

import re

import subprocess

import sys

import time

from typing import Optional, Dict, Any, List

if sys.platform == "win32":

    try:

        if hasattr(sys.stdout, "reconfigure"):

            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    except Exception:

        pass

import pytz

import requests

from telethon import TelegramClient, events

from telethon.tl import types, functions

from telethon.tl.types import MessageActionGroupCall

import calendar_sync

import database

import notebooklm_bot

import route_builder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

SESSION_FILE = os.path.join(BASE_DIR, "sesion_vigia.session")

FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")

# Registro en memoria de llamadas de voz activas {chat_id: info}

LLAMADAS_ACTIVAS: Dict[int, Dict[str, Any]] = {}

def cargar_config() -> dict:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:

        return json.load(f)

def safe_print(texto: str = ""):

    try:

        print(texto)

    except Exception:

        try:

            print(texto.encode("ascii", "replace").decode("ascii"))

        except Exception:

            pass

ZOOM_LINKS_PROCESADOS: Dict[str, float] = {}

def normalizar_chat_id(cid: Any) -> str:

    s = str(cid or "").strip()

    if s.startswith("-100"):

        return s[4:]

    if s.startswith("-"):

        return s[1:]

    return s

def extraer_urls_zoom(texto: str) -> List[str]:

    if not texto:

        return []

    patron = r"https?://(?:[\w-]+\.)?zoom\.us/(?:j/\d+|w/\d+|my/[\w.-]+|wc/join/\d+|meeting/register/[\w.-]+)[^\s<>'\"`)]*"

    return re.findall(patron, texto, flags=re.IGNORECASE)

def extraer_id_sala_zoom(url: str) -> str:

    """Extrae el ID numérico único de una sala de Zoom para comparar links."""

    if not url:

        return ""

    m = re.search(r"/(?:j|w|wc/join)/(\d{8,13})", url)

    if m:

        return m.group(1)

    m2 = re.search(r"/(\d{8,13})", url)

    if m2:

        return m2.group(1)

    m3 = re.search(r"/my/([\w.-]+)", url)

    if m3:

        return m3.group(1).lower()

    return url.strip().lower()

def buscar_mentoria_duplicada(enlace_zoom: str, dt_ini_nuevo: datetime.datetime) -> Optional[Dict[str, Any]]:

    """Revisa en la base de datos si ya existe una mentoría PENDIENTE o GRABANDO."""

    zoom_id_nuevo = extraer_id_sala_zoom(enlace_zoom)

    clases_existentes = database.listar_clases()

    for c in clases_existentes:

        if c.get("estado") not in ("PENDIENTE", "GRABANDO"):

            continue

        es_ment = (

            c.get("transversal") == "Mentorías"

            or "mentoria" in (c.get("id_clase") or "").lower()

            or "mentoría" in (c.get("titulo_original") or "").lower()

        )

        if not es_ment:

            continue

        url_existente = c.get("url_hotmart") or ""

        zoom_id_existente = extraer_id_sala_zoom(url_existente)

        fecha_existente_str = c.get("fecha_grabacion") or ""

        dt_existente = None

        if fecha_existente_str and "T" in fecha_existente_str:

            try:

                dt_existente = datetime.datetime.fromisoformat(fecha_existente_str)

            except Exception:

                dt_existente = None

        if zoom_id_nuevo and zoom_id_nuevo != "chat_voz_telegram" and zoom_id_nuevo == zoom_id_existente:

            if not dt_existente or abs((dt_ini_nuevo - dt_existente).total_seconds()) < 6 * 3600:

                return c

        if dt_existente and abs((dt_ini_nuevo - dt_existente).total_seconds()) <= 1800:

            if not zoom_id_nuevo or not zoom_id_existente or zoom_id_nuevo == zoom_id_existente:

                return c

    return None

def comprimir_audio_para_ia(ruta_origen: str, ruta_destino_mp3: str) -> bool:

    """Extrae audio ligero a 16kHz mono para enviar a Gemini sin superar límites de memoria."""

    if not os.path.exists(FFMPEG_EXE) or not os.path.exists(ruta_origen):

        return False

    cmd = [

        FFMPEG_EXE, "-y",

        "-i", ruta_origen,

        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",

        ruta_destino_mp3,

    ]

    try:

        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)

        return res.returncode == 0 and os.path.exists(ruta_destino_mp3) and os.path.getsize(ruta_destino_mp3) > 100

    except Exception:

        return False

def analizar_aporte_telegram_con_gemini(

    texto_mensaje: str,

    ruta_media: str,

    mime_type: str,

    mentor_asignado: str,

    api_key: str,

    modelo_cfg: str = "gemini-2.5-flash",

) -> dict:

    tz_local = pytz.timezone("America/La_Paz")

    ahora_bolivia = datetime.datetime.now(tz_local)

    fecha_actual_str = ahora_bolivia.strftime("%Y-%m-%d %H:%M")

    prompt = f"""

    Eres el cerebro pedagógico de Universidad Online. Analiza este mensaje de Telegram (y la imagen, audio o video adjunto si existe).

    Mentor asociado al grupo: "{mentor_asignado}".

    Fecha y hora actual en Bolivia (UTC-4): {fecha_actual_str}.

    CLASIFICA EL MENSAJE EN UNA DE ESTAS 4 CATEGORÍAS ("categoria"):

    1. "REUNION_VIVO": Si anuncia una mentoría por Zoom o llamada de voz de Telegram.

       - Si dice "Estamos en vivo", "Entra ya", "Clic aquí para participar ya", pon "iniciar_ahora": true.

       - Si da una hora de Colombia, súmale 1 hora para Bolivia.

    2. "CAPSULA_PROFUNDA": Si comparte una enseñanza amplia, explicación detallada, marco de trabajo, audio educativo largo o clase grabada que amerite infografía paso a paso, checklist, mapa mental, flashcards y quiz.

    3. "TIP": Si comparte un consejo corto, hack puntual, recomendación o reflexión breve de estudio.

    4. "NOTICIA": Si es un aviso importante, cambio de horario, anuncio de evento, actualización o comunicado para los alumnos.

    Si el contenido no tiene ninguna relación con aprendizaje o mentorías, responde con "es_relevante": false.

    Devuelve ÚNICAMENTE un JSON con:

    {{

      "es_relevante": true,

      "categoria": "REUNION_VIVO | CAPSULA_PROFUNDA | TIP | NOTICIA",

      "titulo": "Título conciso y profesional",

      "resumen_didactico": "Explicación clara de las ideas principales",

      "mentor_detectado": "{mentor_asignado}",

      "enlace_zoom": "URL de Zoom si la hay, o null",

      "inicio_iso": "YYYY-MM-DDTHH:MM:SS-04:00 si es reunión, o null",

      "iniciar_ahora": false,

      "duracion_estimada_minutos": 90,

      "es_grabacion_oficial": false,

      "infografia_pasos": [

        {{"icono": "📌", "titulo": "Paso 1", "explicacion": "Detalle"}}

      ],

      "checklist_15_min": ["Acción 1", "Acción 2"],

      "quiz_practico": [

        {{"pregunta": "¿...?", "opciones": ["A) ...", "B) ..."], "respuesta_correcta": "A", "explicacion": "..."}}

      ],

      "flashcards": [

        {{"pregunta": "¿Concepto clave?", "respuesta": "Explicación directa.", "dificultad": "Básica"}}

      ],

      "mapa_mental_mermaid": "graph TD\n A[Concepto] --> B[Acción]"

    }}

    """

    partes = [{"text": prompt}]

    if texto_mensaje:

        partes.append({"text": f"--- CONTENIDO DEL MENSAJE ---\n{texto_mensaje}"})

    archivo_temp_comprimido = None

    if ruta_media and os.path.exists(ruta_media):

        try:

            ruta_a_enviar = ruta_media

            mime_a_enviar = mime_type

            if "audio" in mime_type or "ogg" in mime_type or "mp4" in mime_type:

                temp_comp = os.path.join(BASE_DIR, f"temp_comp_{int(time.time()*1000)}.mp3")

                if comprimir_audio_para_ia(ruta_media, temp_comp):

                    archivo_temp_comprimido = temp_comp

                    ruta_a_enviar = temp_comp

                    mime_a_enviar = "audio/mp3"

            if os.path.getsize(ruta_a_enviar) <= 15 * 1024 * 1024:

                with open(ruta_a_enviar, "rb") as f_med:

                    data_b64 = base64.b64encode(f_med.read()).decode("utf-8")

                partes.append({"inline_data": {"mime_type": mime_a_enviar, "data": data_b64}})

        except Exception as e_b64:

            safe_print(f"[Vigía IA] Aviso preparando multimedia para Gemini: {e_b64}")

        finally:

            if archivo_temp_comprimido and os.path.exists(archivo_temp_comprimido):

                try:

                    os.remove(archivo_temp_comprimido)

                except Exception:

                    pass

    payload = {

        "contents": [{"parts": partes}],

        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1},

    }

    for mod in dict.fromkeys([modelo_cfg, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]):

        if not mod:

            continue

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"

        try:

            r = requests.post(url, json=payload, timeout=60)

            if r.status_code == 200:

                texto_resp = r.json()["candidates"][0]["content"]["parts"][0]["text"]

                return json.loads(texto_resp.replace("```json", "").replace("```", "").strip())

        except Exception:

            continue

    return {"es_relevante": False}

def analizar_lote_mensajes_con_gemini(
    lote_mensajes: List[Dict[str, Any]],
    nombre_mentor: str,
    chat_title: str,
    api_key: str,
    modelo_cfg: str = "gemini-2.5-flash",
) -> List[Dict[str, Any]]:
    """
    CLOUD OFFLOADING & BATCHING:
    Envía un lote de hasta 50-100 mensajes a Gemini en UNA SOLA llamada para que los
    servidores de Google procesen y filtren el contenido masivo en la nube,
    ahorrando tiempo de red y ciclos de CPU local.
    """
    if not lote_mensajes or not api_key:
        return []

    tz_local = pytz.timezone("America/La_Paz")
    ahora_bolivia = datetime.datetime.now(tz_local)
    fecha_actual_str = ahora_bolivia.strftime("%Y-%m-%d %H:%M")

    bloque_textos = []
    for item in lote_mensajes:
        mid = item["msg_id"]
        fecha = item["fecha_str"]
        txt = (item["texto"] or "").strip()
        adjunto = item["adjunto_tipo"]
        doc_nom = item.get("nombre_archivo", "")
        desc_adj = f"{adjunto} ({doc_nom})" if doc_nom else adjunto
        bloque_textos.append(f"[MENSAJE_ID: {mid}] [FECHA: {fecha}] [ADJUNTO: {desc_adj}]\nTEXTO: {txt}\n---")

    texto_completo_lote = "\n".join(bloque_textos)

    prompt = f"""
Eres el cerebro pedagógico y analista de Universidad Online.
A continuación tienes un bloque de {len(lote_mensajes)} mensajes históricos extraídos del canal '{chat_title}' (Mentor: "{nombre_mentor}").
Fecha y hora actual en Bolivia (UTC-4): {fecha_actual_str}.

TU MISIÓN (PROCESAMIENTO EN LOTE):
Analiza el bloque entero y extrae ÚNICAMENTE los mensajes que tengan ALTO VALOR educativo, estratégico o anuncios de sesiones en vivo.
Ignora completamente mensajes de saludo casual, memes, conversaciones sociales o agradecimientos ("gracias", "buen día", etc.).

Para cada mensaje valioso, clasifícalo en una de estas categorías:
1. "REUNION_VIVO": Si anuncia una mentoría por Zoom o llamada de voz de Telegram.
2. "PLAYBOOK_DOCUMENTO": Si comparte un PDF, guía, playbook o documento descargable educativo de alto valor (pon 'descargar_adjunto': true).
3. "CAPSULA_PROFUNDA": Explicación detallada, marco de trabajo o táctica de alto calibre.
4. "TIP": Consejo corto, hack puntual o reflexión de estudio.
5. "NOTICIA": Aviso importante, cambio de horario o actualización de eventos.

Devuelve ÚNICAMENTE un JSON con este formato exacto:
{{
  "aportes_valiosos": [
    {{
      "msg_id": 12345,
      "categoria": "REUNION_VIVO | PLAYBOOK_DOCUMENTO | CAPSULA_PROFUNDA | TIP | NOTICIA",
      "titulo": "Título profesional y conciso",
      "resumen_didactico": "Explicación clara de las ideas principales",
      "descargar_adjunto": true,
      "enlace_zoom": "URL de Zoom si la hay, o null",
      "inicio_iso": "YYYY-MM-DDTHH:MM:SS-04:00 si es reunión, o null",
      "iniciar_ahora": false,
      "duracion_estimada_minutos": 90,
      "infografia_pasos": [
        {{"icono": "📌", "titulo": "Paso 1", "explicacion": "Detalle"}}
      ],
      "checklist_15_min": ["Acción 1", "Acción 2"],
      "quiz_practico": [
        {{"pregunta": "¿...?", "opciones": ["A) ...", "B) ..."], "respuesta_correcta": "A", "explicacion": "..."}}
      ],
      "flashcards": [
        {{"pregunta": "¿Concepto clave?", "respuesta": "Explicación directa.", "dificultad": "Básica"}}
      ],
      "mapa_mental_mermaid": "graph TD\n A[Concepto] --> B[Acción]"
    }}
  ]
}}
Si ningún mensaje del bloque tiene valor educativo o estratégico, devuelve: {{"aportes_valiosos": []}}
"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"text": f"--- BLOQUE DE MENSAJES ---\n{texto_completo_lote}"}
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2
        }
    }

    modelos = dict.fromkeys([modelo_cfg, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"])
    for mod in modelos:
        if not mod:
            continue
        url_mod = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        try:
            resp = requests.post(url_mod, headers=headers, json=payload, timeout=90)
            if resp.status_code == 200:
                raw_json = resp.json()
                cands = raw_json.get("candidates", [])
                if cands:
                    part = cands[0].get("content", {}).get("parts", [{}])[0]
                    texto_resp = part.get("text", "{}")
                    parsed = json.loads(texto_resp)
                    return parsed.get("aportes_valiosos", [])
        except Exception as e_mod:
            safe_print(f"[Vigía Batch IA] Aviso con modelo {mod}: {e_mod}")

    return []

async def procesar_aporte_valioso_batch(
    analisis: Dict[str, Any],
    event_or_msg: Any,
    chat_title: str,
    nombre_mentor: str,
    cfg: Dict[str, Any],
    client: Optional[TelegramClient] = None,
):
    """Procesa y almacena un aporte de alto valor clasificado previamente por Gemini en lote."""
    tz_local = pytz.timezone("America/La_Paz")
    dt_msg = event_or_msg.date.astimezone(tz_local) if getattr(event_or_msg, "date", None) else datetime.datetime.now(tz_local)
    fecha_iso_msg = dt_msg.strftime("%Y-%m-%dT%H:%M:%S-04:00")
    fecha_legible = dt_msg.strftime("%d/%m/%Y")
    hora_legible = dt_msg.strftime("%H:%M")
    categoria = analisis.get("categoria", "TIP")
    titulo = analisis.get("titulo", "Aporte de Mentor")
    resumen = analisis.get("resumen_didactico") or getattr(event_or_msg, "raw_text", "") or ""
    es_gen = not nombre_mentor or nombre_mentor.lower() in ("general", "sin mentor", "canal general")
    id_cap = f"cap_{int(dt_msg.timestamp())}_{abs(hash(titulo)) % 1000}"

    ruta_adjunto_descargado = None
    if analisis.get("descargar_adjunto") or categoria == "PLAYBOOK_DOCUMENTO":
        doc = getattr(event_or_msg, "document", None)
        if doc:
            nom_archivo = ""
            for attr in getattr(doc, "attributes", []):
                if hasattr(attr, "file_name") and attr.file_name:
                    nom_archivo = attr.file_name
                    break
            carpeta_playbooks = os.path.join(BASE_DIR, "grabaciones", "playbooks_vigia")
            os.makedirs(carpeta_playbooks, exist_ok=True)
            nom_final = database.normalizar_id(nom_archivo or f"playbook_{id_cap}").replace(" ", "_") + ".pdf"
            ruta_destino = os.path.join(carpeta_playbooks, nom_final)
            safe_print(f"   📥 [Batch Descarga] Descargando documento verificado: '{nom_final}'...")
            try:
                await event_or_msg.download_media(file=ruta_destino)
                if os.path.exists(ruta_destino) and os.path.getsize(ruta_destino) > 1024:
                    ruta_adjunto_descargado = ruta_destino
            except Exception as e_dl:
                safe_print(f"   [!] Aviso descargando adjunto en batch: {e_dl}")

    # Guardar en base de datos
    database.guardar_capsula_o_noticia_mentor(
        id_capsula=id_cap,
        mentor=nombre_mentor,
        grupo_origen=chat_title,
        tipo=categoria,
        titulo=titulo,
        contenido_resumen=resumen,
        fecha_mensaje_iso=fecha_iso_msg,
        fecha_legible=fecha_legible,
        hora_legible=hora_legible,
        analisis=analisis,
    )

    if es_gen:
        safe_print(f"   ✅ [Batch {categoria}] Guardado de Canal General '{chat_title}': {titulo}")
    else:
        safe_print(f"   ✅ [Batch {categoria}] Guardado para '{nombre_mentor}': {titulo}")

    if client:
        try:
            await publicar_aporte_en_telegram_mentorias(
                client=client,
                titulo=titulo,
                mentor=nombre_mentor,
                tipo=categoria,
                resumen=resumen,
                ruta_adjunto=ruta_adjunto_descargado,
            )
        except Exception as e_pub:
            safe_print(f"   [!] Aviso publicando aporte en Telegram: {e_pub}")

async def resolver_dialogos_vigilados(client: TelegramClient, mentores_reg: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:

    """Descubre los IDs de chats exactos para escuchar sin fallos de nombres o caracteres especiales, con validación activa de grupos (Directiva 6)."""

    vigilados = {}

    cfg = cargar_config()

    safe_print("[Vigía] 🔍 Sincronizando y resolviendo chats y canales de Telegram...")

    dialogos_existentes = []

    try:

        async for dialog in client.iter_dialogs():

            if dialog.is_group or dialog.is_channel:

                dialogos_existentes.append(dialog)

    except Exception as e:

        safe_print(f"[Vigía] Aviso recuperando diálogos de Telegram: {e}")

    # 1. Asociar grupos y canales encontrados en los diálogos activos

    for dialog in dialogos_existentes:

        title_norm = database.normalizar_id(dialog.title or "")

        t_orig = dialog.title or ""

        mentor_encontrado = ""

        # Whitelist Estricto: Solo aceptar si coincide con un registro explícito en BD o con 'Universidad Online'
        item_encontrado = None

        for m in mentores_reg:

            p_norm = database.normalizar_id(m.get("palabra_clave_grupo", ""))

            raw_kw = m.get("palabra_clave_grupo", "").strip().lower()

            if p_norm and (p_norm in title_norm or raw_kw in t_orig.lower() or str(dialog.id) == raw_kw or str(normalizar_chat_id(dialog.id)) == raw_kw):

                item_encontrado = m

                break

        es_grupo_uo = ("universidad" in title_norm and "online" in title_norm)

        if item_encontrado or es_grupo_uo:

            es_gen = False

            if item_encontrado:

                tipo_grp = item_encontrado.get("tipo_grupo", "MENTOR")

                nom_m = item_encontrado.get("nombre_mentor", "")

                if tipo_grp == "GENERAL" or nom_m.lower() in ("general", "sin mentor", "canal general"):

                    es_gen = True

                    mentor_val = "General"

                else:

                    mentor_val = nom_m

            else:

                mentor_val = "Mentor Universidad Online"

                es_gen = False

            vigilados[dialog.id] = {

                "id": dialog.id,

                "title": t_orig,

                "title_norm": title_norm,

                "mentor": mentor_val,

                "es_general": es_gen,

                "entity": dialog.entity,

            }

    # 2. Canales manuales configurados por el usuario en config.json

    canales_manuales = cfg.get("canales_vigilados_manuales", [])

    for c_manual in canales_manuales:

        c_str = str(c_manual).strip()

        if not c_str:

            continue

        try:

            ent = await client.get_entity(c_str if not c_str.lstrip("-").isdigit() else int(c_str))

            if ent:

                c_id = getattr(ent, "id", 0)

                t_title = getattr(ent, "title", c_str) or c_str

                vigilados[c_id] = {

                    "id": c_id,

                    "title": t_title,

                    "title_norm": database.normalizar_id(t_title),

                    "mentor": "Mentor Configurado Manualmente",

                    "entity": ent,

                }

        except Exception as e_man:

            safe_print(

                f"\n========================================================================================\n"

                f"⚠️ ERROR CRÍTICO: No se pudo acceder al canal manual configurado: '{c_str}'.\n"

                f"   Razón: {e_man}\n"

                f"   Por favor verifica que el ID o username sea correcto y que la sesión tenga acceso.\n"

                f"========================================================================================"

            )

    # =========================================================================

    # VALIDACIÓN ACTIVA DE GRUPOS Y MANEJO DE ERRORES (DIRECTIVA 6)

    # =========================================================================

    # a) Validación del grupo principal de la comunidad "Universidad Online"

    grupo_uo_encontrado = any(

        ("universidad" in v["title_norm"] and "online" in v["title_norm"])

        for v in vigilados.values()

    )

    if not grupo_uo_encontrado:

        safe_print(

            f"\n========================================================================================\n"

            f"⚠️ ERROR CRÍTICO: No se pudo acceder al grupo 'Universidad Online'.\n"

            f"   Razón: No se encontró ningún grupo con ese nombre en la sesión actual de Telegram.\n"

            f"   Posibles causas: El nombre del grupo cambió o la cuenta ('sesion_vigia.session') no es miembro.\n"

            f"   Solución: Únete al grupo con tu cuenta de Telegram o ingresa el nombre o ID exacto\n"

            f"   en 'config.json' en la clave 'canales_vigilados_manuales' (ej: ['-1001700618007']).\n"

            f"========================================================================================"

        )

    # b) Validación de cada mentor registrado

    for m in mentores_reg:

        nombre_m = m.get("nombre_mentor", "Desconocido")

        kw_m = m.get("palabra_clave_grupo", "")

        norm_kw = database.normalizar_id(kw_m)

        hallado = any(

            (v["mentor"] == nombre_m or norm_kw in v["title_norm"])

            for v in vigilados.values()

        )

        if not hallado:

            # Intento de rescate directo por si es un ID o username de canal

            rescatado = False

            try:

                ent_res = await client.get_entity(kw_m if not kw_m.lstrip("-").isdigit() else int(kw_m))

                if ent_res:

                    vigilados[ent_res.id] = {

                        "id": ent_res.id,

                        "title": getattr(ent_res, "title", kw_m),

                        "title_norm": database.normalizar_id(getattr(ent_res, "title", kw_m)),

                        "mentor": nombre_m,

                        "entity": ent_res,

                    }

                    rescatado = True

            except Exception:

                rescatado = False

            if not rescatado:

                safe_print(

                    f"\n========================================================================================\n"

                    f"⚠️ ERROR CRÍTICO: No se pudo acceder al grupo del mentor '{nombre_m}' (Buscado como: '{kw_m}').\n"

                    f"   Razón: No se encontró en los diálogos activos ni tiene permisos de lectura.\n"

                    f"   Por favor verifica el nombre exacto del grupo o agrega su ID numérico (-100...)\n"

                    f"   en 'config.json' bajo 'canales_vigilados_manuales'.\n"

                    f"========================================================================================"

                )

    # c) Validación de los 3 Canales Oficiales de Destino (Directiva 7)

    import telegram_uploader

    canales_destino_requeridos = [

        ("Masterclasses", cfg.get("telegram_channel_title", "Masterclasses Universidad Online")),

        ("Mentorías / Zoom / Voz", cfg.get("telegram_mentorias_channel_title", "Mentorías - Universidad Online")),

        ("Playbooks / Documentos", cfg.get("telegram_playbooks_channel_title", "Playbooks - Universidad Online")),

    ]

    for tipo_c, nom_c in canales_destino_requeridos:

        ent_dest = await telegram_uploader.obtener_canal(client, nom_c)

        if not ent_dest:

            safe_print(

                f"\n⚠️ AVISO DE ENRUTAMIENTO: No se detectó acceso al canal oficial de {tipo_c}: '{nom_c}'.\n"

                f"   Asegúrate de haber creado el canal '{nom_c}' y de que tu cuenta de Telegram sea administradora."

            )

    safe_print(f"\n[Vigía] ✅ Se tienen {len(vigilados)} canales y grupos bajo vigilancia activa.")

    for d_id, info in vigilados.items():

        safe_print(f"   -> [{info['id']}] {info['title']} (Mentor: {info['mentor']})")

    return vigilados

async def iniciar_grabacion_voz_telegram(chat_id: int, chat_title: str, mentor: str):

    """Inicia la captura autónoma de una llamada de voz en Telegram (Vía Telegram Web o Loopback FFmpeg)."""

    if chat_id in LLAMADAS_ACTIVAS:

        return

    ts_now = int(time.time())

    id_clase = f"voz_tg_{abs(chat_id)}_{ts_now}"

    carpeta_destino = os.path.join(BASE_DIR, "grabaciones", "mentorias", f"voz_{ts_now}")

    os.makedirs(carpeta_destino, exist_ok=True)

    ruta_audio = os.path.join(carpeta_destino, f"Grabacion_Voz_{ts_now}.mp3")

    safe_print(f"\n🎙️ [Vigía Voice Chat] ¡Llamada de voz iniciada en '{chat_title}'!")

    safe_print(f"🎙️ [Vigía Voice Chat] Mentor: {mentor} | Guardando en: {os.path.basename(ruta_audio)}")

    # 1. Comprobar si Chrome con CDP está abierto para intentar grabación en Telegram Web

    usar_telegram_web = False

    try:

        import urllib.request

        with urllib.request.urlopen("http://localhost:9222/json/version", timeout=1.5) as r:

            if r.status == 200:

                usar_telegram_web = True

    except Exception:

        usar_telegram_web = False

    if usar_telegram_web:

        safe_print("🌐 [Vigía Voice Chat] Chrome CDP disponible. Lanzando captura inteligente vía Telegram Web...")

        import recorder

        task_web = asyncio.create_task(

            recorder.grabar_llamada_telegram_web(

                chat_title=chat_title,

                ruta_salida_mp4=ruta_audio,

                chat_id=chat_id,

                mentor=mentor,

                id_clase=id_clase,

            )

        )

        LLAMADAS_ACTIVAS[chat_id] = {

            "tipo": "web",

            "task": task_web,

            "id_clase": id_clase,

            "ruta_audio": ruta_audio,

            "chat_title": chat_title,

            "mentor": mentor,

            "t_inicio": time.time(),

        }

        return

    # 2. Fallback: Captura limpia por audio del sistema con FFmpeg

    dispositivos = []

    if os.path.exists(FFMPEG_EXE):

        try:

            res = subprocess.run([FFMPEG_EXE, "-list_devices", "true", "-f", "dshow", "-i", "dummy"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", timeout=10)

            for linea in (res.stderr or "").splitlines():

                if "(audio)" in linea:

                    m = re.search(r'"([^"]+)"\s+\(audio\)', linea)

                    if m: dispositivos.append(m.group(1))

        except Exception:

            pass

    disp_audio = dispositivos[0] if dispositivos else None

    cmd = [FFMPEG_EXE, "-y"]

    if disp_audio:

        cmd.extend(["-f", "dshow", "-i", f"audio={disp_audio}"])

    else:

        cmd.extend(["-f", "dshow", "-i", "audio=dummy"])

    cmd.extend(["-vn", "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "128k", ruta_audio])

    si = subprocess.STARTUPINFO() if sys.platform == "win32" else None

    if si:

        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        si.wShowWindow = 0

    try:

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)

        LLAMADAS_ACTIVAS[chat_id] = {

            "tipo": "ffmpeg",

            "proc": proc,

            "id_clase": id_clase,

            "ruta_audio": ruta_audio,

            "chat_title": chat_title,

            "mentor": mentor,

            "t_inicio": time.time(),

        }

    except Exception as e_proc:

        safe_print(f"[!] No se pudo iniciar captura de llamada de voz: {e_proc}")

async def publicar_aporte_en_telegram_mentorias(

    client: TelegramClient,

    titulo: str,

    mentor: str,

    tipo: str,

    resumen: str,

    ruta_adjunto: Optional[str] = None,

):

    try:

        cfg = cargar_config()

        canal_playbooks = cfg.get("telegram_playbooks_channel_title", "Playbooks - Universidad Online")

        canal_mentorias = cfg.get("telegram_mentorias_channel_title", "Mentorías - Universidad Online")

        

        # Enrutamiento exacto: PDFs y Playbooks a 'Playbooks - Universidad Online'

        es_playbook_doc = bool(

            (ruta_adjunto and ruta_adjunto.lower().endswith(".pdf"))

            or tipo == "PLAYBOOK"

            or "playbook" in titulo.lower()

        )

        canal_destino_nom = canal_playbooks if es_playbook_doc else canal_mentorias

        import telegram_uploader

        ent = await telegram_uploader.obtener_canal(client, canal_destino_nom)

        if not ent:

            safe_print(

                f"\n⚠️ ERROR CRÍTICO: No se pudo acceder al canal de destino '{canal_destino_nom}' para publicar '{titulo}'.\n"

                f"   Por favor, verifica el nombre exacto del canal o asegúrate de que la cuenta tenga acceso de publicación."

            )

            return

        icono = "📘" if es_playbook_doc else ("💡" if tipo == "TIP" else ("📢" if tipo == "NOTICIA" else "🧠"))

        es_gen = not mentor or mentor.lower() in ("general", "sin mentor", "canal general", "mentor universidad online")

        linea_mentor = f"👤 Mentor: {mentor}\n\n" if not es_gen else ""

        caption = (

            f"{icono} [{tipo}] {titulo}\n"

            f"{linea_mentor}"

            f"📝 Síntesis Didáctica:\n{resumen[:800]}\n\n"

            f"📱 Guía completa, flashcards y mapa mental actualizados en la App Web."

        )

        if ruta_adjunto and os.path.exists(ruta_adjunto) and os.path.getsize(ruta_adjunto) <= 45 * 1024 * 1024:

            await client.send_file(ent, file=ruta_adjunto, caption=caption)

        else:

            await client.send_message(ent, message=caption)

        safe_print(f"   📤 [Telegram] Publicado exitosamente en '{canal_destino_nom}': {titulo}")

    except Exception as e_pub:

        safe_print(f"   [!] Aviso publicando aporte en Telegram: {e_pub}")

async def finalizar_grabacion_voz_telegram(chat_id: int, duracion_seg: int = 0):

    """Detiene la grabación de la llamada y ejecuta el flujo autónomo: NotebookLM + Telegram + App Web."""

    info = LLAMADAS_ACTIVAS.pop(chat_id, None)

    if not info:

        return

    if info.get("tipo") == "web":

        task = info.get("task")

        if task and not task.done():

            task.cancel()

            try:

                await task

            except (Exception, asyncio.CancelledError):

                pass

    else:

        proc = info.get("proc")

        if proc:

            try:

                if proc.stdin:

                    proc.stdin.write(b"q\n")

                    proc.stdin.flush()

                proc.wait(timeout=5)

            except Exception:

                pass

            if proc.poll() is None:

                try:

                    proc.terminate()

                    proc.wait(timeout=5)

                except Exception:

                    pass

            if proc.poll() is None:

                try:

                    proc.kill()

                except Exception:

                    pass

    ruta_audio = info["ruta_audio"]

    chat_title = info["chat_title"]

    mentor = info["mentor"]

    segundos_reales = int(time.time() - info["t_inicio"])

    dur_min = max(1, segundos_reales // 60)

    safe_print(f"\n🏁 [Vigía Voice Chat] Llamada finalizada en '{chat_title}'.")

    safe_print(f"🏁 Duración grabada: {dur_min} minutos. Ejecutando flujo autónomo...")

    if not os.path.exists(ruta_audio) or os.path.getsize(ruta_audio) < 2048:

        safe_print("[AVISO] El archivo de audio de la llamada quedó vacío o no existe.")

        return

    id_clase = info["id_clase"]

    titulo = f"Mentoría en Vivo: {mentor} ({chat_title})"

    fecha_formateada = datetime.date.today().strftime("%d/%m/%Y")

    carpeta = os.path.dirname(ruta_audio)

    ruta_md = os.path.join(carpeta, f"Ficha_{id_clase}.md")

    analisis = {

        "transversal": "Mentorías",

        "nivel": 1,

        "mentor_identificado": mentor,

        "resumen_didactico": f"Sesión de mentoría en vivo vía llamada de voz de Telegram ({chat_title}).",

        "flashcards": [

            {"pregunta": f"¿De qué trató la sesión con {mentor}?", "respuesta": f"Sesión en vivo grabada desde el canal {chat_title}.", "dificultad": "Básica"}

        ]

    }

    try:

        with open(ruta_md, "w", encoding="utf-8") as f:

            f.write(f"# {titulo}\n\n**Mentor:** {mentor} | **Fecha:** {fecha_formateada}\n\n{analisis['resumen_didactico']}\n")

        notebook_url = ""

        res_nlm = await notebooklm_bot.procesar_clase_en_notebooklm(

            {"id_clase": id_clase, "titulo_original": titulo},

            analisis,

            ruta_audio,

            ruta_md,

        )

        if isinstance(res_nlm, dict):

            notebook_url = res_nlm.get("notebook_url") or ""

        import telegram_uploader

        await telegram_uploader.subir_entrega_completa_telegram(

            ruta_video="",

            titulo_clase=titulo,

            fecha_clase=fecha_formateada,

            duracion_min=dur_min,

            analisis=analisis,

            notebook_url=notebook_url,

            ruta_podcast=ruta_audio,

            ruta_md_guia=ruta_md,

        )

        database.guardar_o_actualizar_clase(

            id_clase=id_clase,

            titulo_original=titulo,

            fecha_grabacion=datetime.datetime.now().isoformat(),

            estado="COMPLETADA",

            ruta_archivo=ruta_audio,

            url_hotmart="chat_voz_telegram",

        )

        database.guardar_analisis_clase(id_clase, analisis)

        route_builder.generar_tablero_rutas(auto_deploy=True)

        database.purgar_multimedia_local_clase(id_clase, ruta_audio=ruta_audio)

        safe_print(f"🎉 [Vigía Voice Chat] ¡Llamada procesada, subida a Telegram y publicada en la App Web con éxito!")

    except Exception as e_flujo:

        safe_print(f"[!] Error en flujo autónomo de llamada de voz: {e_flujo}")

async def procesar_mensaje_vigia(event_or_msg, chat_title: str, nombre_mentor: str, cfg: dict, es_catchup: bool = False, client: Optional[TelegramClient] = None):

    """Procesa un mensaje de Telegram (en tiempo real o en barrido catch-up histórico) de forma integral."""

    gemini_key = cfg.get("gemini_api_key")

    modelo_cfg = cfg.get("gemini_model", "gemini-2.5-flash")

    prefix = "[Catch-Up]" if es_catchup else "[Vigía]"

    # Detección de Voice Chat

    action = getattr(event_or_msg, "action", None)

    if isinstance(action, MessageActionGroupCall):

        duracion = getattr(action, "duration", None)

        chat_id = getattr(event_or_msg, "chat_id", 0)

        if es_catchup:

            safe_print(f"   ℹ️ {prefix} Registro histórico de Voice Chat en '{chat_title}' (Duración: {duracion or 'En curso en ese momento'}). Omitiendo captura en vivo.")

            return

        if not duracion:

            await iniciar_grabacion_voz_telegram(chat_id, chat_title, nombre_mentor)

            return

        else:

            await finalizar_grabacion_voz_telegram(chat_id, duracion)

            return

    texto = getattr(event_or_msg, "raw_text", "") or ""

    # -------------------------------------------------------------------------

    # DETECCIÓN Y DEDUPLICACIÓN DE ENLACES ZOOM MULTI-CANAL

    # -------------------------------------------------------------------------

    urls_zoom = extraer_urls_zoom(texto)

    enlace_zoom_detectado = urls_zoom[0] if urls_zoom else None

    if enlace_zoom_detectado:

        zoom_id = extraer_id_sala_zoom(enlace_zoom_detectado)

        ahora_ts = time.time()

        # Verificar en cache de enlaces procesados y en SQLite

        ya_en_cache = (zoom_id in ZOOM_LINKS_PROCESADOS and (ahora_ts - ZOOM_LINKS_PROCESADOS[zoom_id] < 86400))

        ya_en_bd = database.es_zoom_ya_registrado_bd(zoom_id)

        if ya_en_cache or ya_en_bd:

            safe_print(f"\n{prefix} 🛡️ [Anti-Colisión Zoom] Enlace de sala Zoom {zoom_id} detectado en '{chat_title}' ya fue procesado/agendado. Deduplicando evento.")

            return

        ZOOM_LINKS_PROCESADOS[zoom_id] = ahora_ts

    # -------------------------------------------------------------------------

    # DEDUPLICACIÓN Y REEMPLAZO INTELIGENTE DE AUDIOS OFICIALES DEL MENTOR

    # -------------------------------------------------------------------------

    es_audio = getattr(event_or_msg, "voice", False) or getattr(event_or_msg, "audio", False)

    es_video = getattr(event_or_msg, "video", False) or getattr(event_or_msg, "video_note", False)

    tamano_doc = getattr(getattr(event_or_msg, "document", None), "size", 0)

    # Detección de Documentos PDF

    es_pdf = False

    doc = getattr(event_or_msg, "document", None)

    if doc:

        mime = getattr(doc, "mime_type", "") or ""

        nom_archivo = ""

        for attr in getattr(doc, "attributes", []):

            if hasattr(attr, "file_name"):

                nom_archivo = attr.file_name or ""

                break

        if "pdf" in mime.lower() or nom_archivo.lower().endswith(".pdf"):

            es_pdf = True

    # Si es un archivo de audio o video sustancial (> 8 MB o duración > 5 min)

    if (es_audio or es_video) and tamano_doc > 8 * 1024 * 1024:

        safe_print(f"\n{prefix} 📁 Archivo pesado de Mentor detectado en '{chat_title}' ({tamano_doc / (1024*1024):.1f} MB)...")

        tz_local = pytz.timezone("America/La_Paz")

        dt_msg = event_or_msg.date.astimezone(tz_local) if getattr(event_or_msg, "date", None) else datetime.datetime.now(tz_local)

        fecha_iso = dt_msg.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        # Buscar si ya se había grabado preliminarmente una sesión de este mentor hoy

        existente = database.buscar_mentoria_por_mentor_y_fecha(nombre_mentor, fecha_iso)

        if existente:

            safe_print(f"{prefix} ✨ [Deduplicación Inteligente] Se encontró una sesión preliminar: '{existente['titulo_original']}'.")

            safe_print(f"{prefix} 📥 Descargando archivo oficial para reemplazar y optimizar la biblioteca...")

            

            ts_uid = int(time.time())

            ext = ".mp4" if es_video else ".mp3"

            carpeta_dest = os.path.join(BASE_DIR, "grabaciones", "mentorias", database.normalizar_id(nombre_mentor).replace(" ", "_"))

            os.makedirs(carpeta_dest, exist_ok=True)

            ruta_oficial = os.path.join(carpeta_dest, f"Oficial_{nombre_mentor}_{ts_uid}{ext}")

            await event_or_msg.download_media(file=ruta_oficial)

            if os.path.exists(ruta_oficial) and os.path.getsize(ruta_oficial) > 1024:

                id_clase = existente["id_clase"]

                database.guardar_o_actualizar_clase(

                    id_clase=id_clase,

                    titulo_original=existente["titulo_original"],

                    estado="COMPLETADA",

                    ruta_archivo=ruta_oficial,

                )

                safe_print(f"{prefix} ✅ Archivo oficial del mentor vinculado a '{id_clase}'. Reprocesando en NotebookLM...")

                try:

                    await notebooklm_bot.procesar_clase_en_notebooklm(existente, {}, ruta_oficial)

                except Exception:

                    pass

                route_builder.generar_tablero_rutas(auto_deploy=True)

                database.purgar_multimedia_local_clase(id_clase, ruta_video=ruta_oficial)

                return

    # -------------------------------------------------------------------------

    # ANÁLISIS INTELIGENTE PREVIO CON GEMINI (CERO DESCARGAS CIEGAS)

    # -------------------------------------------------------------------------

    nom_doc = ""

    if doc:

        for attr in getattr(doc, "attributes", []):

            if hasattr(attr, "file_name") and attr.file_name:

                nom_doc = attr.file_name

                break

    desc_adj = ""

    if es_pdf:

        desc_adj = f"Documento PDF ({nom_doc}, {tamano_doc / (1024*1024):.1f} MB)" if nom_doc else "Documento PDF"

    elif es_audio:

        desc_adj = f"Audio ({tamano_doc / (1024*1024):.1f} MB)"

    elif es_video:

        desc_adj = f"Video ({tamano_doc / (1024*1024):.1f} MB)"

    elif getattr(event_or_msg, "photo", False):

        desc_adj = "Fotografía/Imagen"

    texto_para_evaluar = texto.strip()

    if desc_adj:

        texto_para_evaluar = f"{texto_para_evaluar}\n[ADJUNTO EN MENSAJE: {desc_adj}]".strip()

    if len(texto_para_evaluar) < 6:

        return

    # 1. Evaluación en Nube con Gemini ANTES de descargar archivos pesados

    analisis = analizar_aporte_telegram_con_gemini(

        texto_mensaje=texto_para_evaluar,

        ruta_media="",

        mime_type="",

        mentor_asignado=nombre_mentor,

        api_key=gemini_key,

        modelo_cfg=modelo_cfg,

    )

    if not analisis or not analisis.get("es_relevante"):

        return

    # 2. Descarga Condicional Autorizada ÚNICAMENTE para contenido de alto valor

    ruta_media = ""

    mime_type = ""

    ts_msg = int(time.time() * 1000)

    categoria = analisis.get("categoria", "TIP")

    debe_descargar = bool(

        analisis.get("descargar_adjunto")

        or categoria in ("PLAYBOOK_DOCUMENTO", "CAPSULA_PROFUNDA")

        or es_pdf

    )

    if debe_descargar and (es_pdf or es_audio or es_video or getattr(event_or_msg, "photo", False)):

        safe_print(f"\n{prefix} 📥 [Filtro Inteligente Aprobado] Gemini confirmó '{analisis.get('titulo', 'Aporte')}'. Descargando adjunto...")

        try:

            if es_pdf and tamano_doc <= 30 * 1024 * 1024:

                carpeta_playbooks = os.path.join(BASE_DIR, "grabaciones", "playbooks_vigia")

                os.makedirs(carpeta_playbooks, exist_ok=True)

                nom_final = database.normalizar_id(nom_doc or f"playbook_{ts_msg}").replace(" ", "_") + ".pdf"

                ruta_media = await event_or_msg.download_media(file=os.path.join(carpeta_playbooks, nom_final))

                mime_type = "application/pdf"

            elif es_audio:

                ext = ".ogg" if getattr(event_or_msg, "voice", False) else ".mp3"

                ruta_media = await event_or_msg.download_media(file=os.path.join(BASE_DIR, f"temp_vigia_{ts_msg}{ext}"))

                mime_type = "audio/ogg" if getattr(event_or_msg, "voice", False) else "audio/mp3"

            elif getattr(event_or_msg, "photo", False):

                ruta_media = await event_or_msg.download_media(file=os.path.join(BASE_DIR, f"temp_vigia_{ts_msg}.jpg"))

                mime_type = "image/jpeg"

            elif es_video and tamano_doc <= 50 * 1024 * 1024:

                ruta_media = await event_or_msg.download_media(file=os.path.join(BASE_DIR, f"temp_vigia_{ts_msg}.mp4"))

                mime_type = "video/mp4"

        except Exception as e_dl:

            safe_print(f"{prefix} Aviso descargando adjunto aprobado: {e_dl}")

            ruta_media = ""

    try:

        pass

    finally:

        if ruta_media and os.path.exists(ruta_media):

            try:

                os.remove(ruta_media)

            except Exception:

                pass

    if not analisis or not analisis.get("es_relevante"):

        return

    tz_local = pytz.timezone("America/La_Paz")

    dt_msg = event_or_msg.date.astimezone(tz_local) if getattr(event_or_msg, "date", None) else datetime.datetime.now(tz_local)

    fecha_iso_msg = dt_msg.strftime("%Y-%m-%dT%H:%M:%S-04:00")

    fecha_legible = dt_msg.strftime("%d/%m/%Y")

    hora_legible = dt_msg.strftime("%H:%M")

    categoria = analisis.get("categoria", "TIP")

    titulo = analisis.get("titulo", "Aporte de Mentor")

    if categoria == "REUNION_VIVO":

        ahora = datetime.datetime.now(tz_local)

        try:

            dt_ini = datetime.datetime.fromisoformat(analisis.get("inicio_iso", ""))

        except Exception:

            dt_ini = ahora + datetime.timedelta(minutes=1)

        if analisis.get("iniciar_ahora") or dt_ini < ahora + datetime.timedelta(minutes=2):

            dt_ini = ahora + datetime.timedelta(minutes=1)

            safe_print("🔥 ¡Reunión EN VIVO AHORA MISMO detectada!")

        enlace = analisis.get("enlace_zoom") or "chat_voz_telegram"

        duracion = int(analisis.get("duracion_estimada_minutos") or 120)

        # Escudo Anti-Duplicados

        duplicada = buscar_mentoria_duplicada(enlace, dt_ini)

        if duplicada:

            id_dup = duplicada["id_clase"]

            safe_print(f"🛡️ [Escudo Anti-Duplicados] Esta mentoría ya estaba agendada (ID: {id_dup}).")

            return

        inicio_iso = dt_ini.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        fin_iso = (dt_ini + datetime.timedelta(minutes=duracion)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

        id_clase = f"mentoria_{int(ahora.timestamp())}"

        es_gen = not nombre_mentor or nombre_mentor.lower() in ("general", "sin mentor", "canal general")

        titulo_agenda = f"Mentoría: {titulo}" if es_gen else f"Mentoría: {titulo} (Mentor: {nombre_mentor})"

        database.guardar_o_actualizar_clase(id_clase, titulo_agenda, inicio_iso, "PENDIENTE", "", enlace)

        database.ejecutar_query(

            "UPDATE clases_grabadas SET duracion_min = ?, transversal = 'Mentorías', mentor = ? WHERE id_clase = ?",

            (duracion, "" if es_gen else nombre_mentor, id_clase),

        )

        calendar_sync.actualizar_estado_evento(id_clase, titulo_agenda, "⏳ [Agendada]", inicio_iso, fin_iso, cfg)

        safe_print(f"✅ ¡Mentoría Agendada! {titulo_agenda} | Inicia: {dt_ini.strftime('%H:%M')}")

    else:

        id_cap = f"cap_{int(datetime.datetime.now().timestamp())}_{abs(hash(titulo)) % 1000}"

        resumen = analisis.get("resumen_didactico") or texto

        notebook_url = ""

        if categoria == "CAPSULA_PROFUNDA":

            carpeta_mentor = os.path.join(

                BASE_DIR, "grabaciones", "mentores_capsulas", database.normalizar_id(nombre_mentor).replace(" ", "_")

            )

            os.makedirs(carpeta_mentor, exist_ok=True)

            ruta_md = os.path.join(carpeta_mentor, f"Capsula_{id_cap}.md")

            with open(ruta_md, "w", encoding="utf-8") as f_md:

                f_md.write(f"# {titulo}\n**Mentor:** {nombre_mentor} | **Fecha:** {fecha_legible} {hora_legible}\n\n{resumen}\n")

            try:

                res_nlm = await notebooklm_bot.procesar_clase_en_notebooklm(

                    {"id_clase": id_cap, "titulo_original": f"{nombre_mentor}: {titulo}"},

                    {"transversal": f"Mentor {nombre_mentor}", **analisis},

                    None,

                    ruta_md,

                )

                if isinstance(res_nlm, dict):

                    notebook_url = res_nlm.get("notebook_url") or ""

            except Exception:

                pass

        database.guardar_capsula_o_noticia_mentor(

            id_capsula=id_cap,

            mentor=nombre_mentor,

            grupo_origen=chat_title,

            tipo=categoria,

            titulo=titulo,

            contenido_resumen=resumen,

            fecha_mensaje_iso=fecha_iso_msg,

            fecha_legible=fecha_legible,

            hora_legible=hora_legible,

            analisis=analisis,

            notebook_url=notebook_url,

        )

        if es_gen:

            safe_print(f"✅ [{categoria}] Guardado de Canal General '{chat_title}': {titulo} ({fecha_legible} {hora_legible})")

        else:

            safe_print(f"✅ [{categoria}] Guardado para '{nombre_mentor}': {titulo} ({fecha_legible} {hora_legible})")

        

        # Publicar aporte de valor en el canal de Telegram de Mentorías

        if client:

            try:

                await publicar_aporte_en_telegram_mentorias(

                    client=client,

                    titulo=titulo,

                    mentor=nombre_mentor,

                    tipo=categoria,

                    resumen=resumen,

                    ruta_adjunto=ruta_media if (ruta_media and os.path.exists(ruta_media)) else None,

                )

            except Exception:

                pass

        if not es_catchup:

            route_builder.generar_tablero_rutas(auto_deploy=True)

async def ejecutar_barrido_historico(client: TelegramClient, chats_vigilados: Dict[int, Dict[str, Any]], cfg: dict):

    """Realiza un barrido histórico (catch-up) al iniciar para procesar todo lo enviado mientras el bot estuvo apagado."""

    ultima_iso = database.obtener_ultima_ejecucion_vigia()

    tz_local = pytz.timezone("America/La_Paz")

    ahora = datetime.datetime.now(tz_local)

    if ultima_iso:

        try:

            dt_desde = datetime.datetime.fromisoformat(ultima_iso)

        except Exception:

            dt_desde = ahora - datetime.timedelta(hours=24)

    else:

        dt_desde = ahora - datetime.timedelta(hours=24)

    safe_print("\n" + "=" * 80)

    safe_print("🔄 [Vigía Catch-Up] INICIANDO BARRIDO HISTÓRICO DE APORTES...")

    safe_print(f"📅 Ventana de búsqueda: desde {dt_desde.strftime('%d/%m/%Y %H:%M')} hasta ahora")

    safe_print("=" * 80)

    total_procesados = 0

    for chat_id, info in list(chats_vigilados.items()):

        try:

            entity = info["entity"]

            nombre_mentor = info["mentor"]

            chat_title = info["title"]

            es_gen = not nombre_mentor or nombre_mentor.lower() in ("general", "sin mentor", "canal general")

            if es_gen:

                safe_print(f"   🔍 Analizando historial reciente en Canal General '{chat_title}'...")

            else:

                safe_print(f"   🔍 Analizando historial reciente en '{chat_title}' (Mentor: {nombre_mentor})...")

            mensajes_crudos = []

            async for msg in client.iter_messages(entity, offset_date=ahora, reverse=False, limit=50):

                msg_dt = msg.date.astimezone(tz_local) if msg.date else ahora

                if msg_dt < dt_desde:

                    break

                mensajes_crudos.append(msg)

            if not mensajes_crudos:

                continue

            # Separar Zoom/Voice chat inmediatos vs lote para análisis en nube
            mensajes_para_lote = []

            mapa_msgs = {}

            for msg in reversed(mensajes_crudos):

                mapa_msgs[msg.id] = msg

                txt = getattr(msg, "raw_text", "") or ""

                # Comprobación de Zoom (inmediato, 0 latencia)
                if extraer_urls_zoom(txt):

                    try:

                        await procesar_mensaje_vigia(msg, chat_title, nombre_mentor, cfg, es_catchup=True, client=client)

                        total_procesados += 1

                    except Exception as e_z:

                        safe_print(f"   [!] Aviso en catch-up Zoom: {e_z}")

                    continue

                # Comprobación de Voice Chat (inmediato)
                if isinstance(getattr(msg, "action", None), MessageActionGroupCall):

                    try:

                        await procesar_mensaje_vigia(msg, chat_title, nombre_mentor, cfg, es_catchup=True, client=client)

                        total_procesados += 1

                    except Exception as e_vc:

                        safe_print(f"   [!] Aviso en catch-up Voice Chat: {e_vc}")

                    continue

                # Detectar adjunto
                es_pdf = False

                doc = getattr(msg, "document", None)

                nom_archivo = ""

                if doc:

                    mime = getattr(doc, "mime_type", "") or ""

                    for attr in getattr(doc, "attributes", []):

                        if hasattr(attr, "file_name") and attr.file_name:

                            nom_archivo = attr.file_name

                            break

                    if "pdf" in mime.lower() or nom_archivo.lower().endswith(".pdf"):

                        es_pdf = True

                adj_tipo = "pdf" if es_pdf else ("audio" if getattr(msg, "audio", False) or getattr(msg, "voice", False) else ("video" if getattr(msg, "video", False) else ("foto" if getattr(msg, "photo", False) else "ninguno")))

                if len(txt.strip()) >= 6 or adj_tipo != "ninguno":

                    msg_dt = msg.date.astimezone(tz_local) if msg.date else ahora

                    mensajes_para_lote.append({

                        "msg_id": msg.id,

                        "texto": txt,

                        "fecha_str": msg_dt.strftime("%d/%m/%Y %H:%M"),

                        "adjunto_tipo": adj_tipo,

                        "nombre_archivo": nom_archivo,

                    })

            # BATCHING A GEMINI EN LA NUBE (UN SOLO REQUEST PARA TODO EL BLOQUE)
            if mensajes_para_lote and gemini_key:

                safe_print(f"   🚀 [Cloud Batching] Enviando lote de {len(mensajes_para_lote)} mensajes de '{chat_title}' a Gemini...")

                aportes_valiosos = await asyncio.to_thread(

                    analizar_lote_mensajes_con_gemini,

                    mensajes_para_lote,

                    nombre_mentor,

                    chat_title,

                    gemini_key,

                    modelo_cfg

                )

                safe_print(f"   ✨ [Cloud Batching] Gemini identificó {len(aportes_valiosos)} aportes de alto valor en la nube.")

                for valioso in aportes_valiosos:

                    mid = valioso.get("msg_id")

                    msg_target = mapa_msgs.get(mid)

                    if msg_target:

                        try:

                            await procesar_aporte_valioso_batch(

                                analisis=valioso,

                                event_or_msg=msg_target,

                                chat_title=chat_title,

                                nombre_mentor=nombre_mentor,

                                cfg=cfg,

                                client=client

                            )

                            total_procesados += 1

                        except Exception as e_val:

                            safe_print(f"   [!] Aviso procesando aporte en batch: {e_val}")

        except Exception as e_chat:

            safe_print(f"   [!] Aviso escaneando historial de {info.get('title')}: {e_chat}")

    database.guardar_ultima_ejecucion_vigia(ahora.strftime("%Y-%m-%dT%H:%M:%S-04:00"))

    safe_print(f"✅ [Vigía Catch-Up] Barrido histórico finalizado ({total_procesados} mensajes examinados).")

    if total_procesados > 0:

        route_builder.generar_tablero_rutas(auto_deploy=True)

async def ejecutar_vigia():

    database.init_db()

    cfg = cargar_config()

    api_id = cfg.get("telegram_api_id")

    api_hash = cfg.get("telegram_api_hash")

    mentores_reg = database.listar_mentores_grupos()

    client = TelegramClient(SESSION_FILE, int(api_id), str(api_hash))

    chats_vigilados: Dict[int, Dict[str, Any]] = {}

    @client.on(events.NewMessage)

    async def handler_mensajes(event):

        try:

            pausado, limite_pausa = database.obtener_estado_pausa_vigia()

            if pausado:

                return

            chat = await event.get_chat()

            chat_id = getattr(chat, "id", 0)

            chat_title = getattr(chat, "title", "") or ""

            chat_norm = database.normalizar_id(chat_title)

            norm_id = normalizar_chat_id(chat_id)

            info_chat = chats_vigilados.get(chat_id)

            if not info_chat:

                for cid, cinfo in list(chats_vigilados.items()):

                    if normalizar_chat_id(cid) == norm_id:

                        info_chat = cinfo

                        break

            if not info_chat:

                for cid, cinfo in list(chats_vigilados.items()):

                    if cinfo["title_norm"] and (cinfo["title_norm"] in chat_norm or chat_norm in cinfo["title_norm"]):

                        info_chat = cinfo

                        break

            if not info_chat:

                # Whitelist Estricto: Rechazar cualquier mensaje de chat privado o grupo no registrado
                return

            nombre_mentor = info_chat["mentor"]

            await procesar_mensaje_vigia(event.message, chat_title, nombre_mentor, cfg, es_catchup=False, client=client)

        except Exception as e_msg:

            safe_print(f"[Vigía] Aviso procesando mensaje: {e_msg}")

    @client.on(events.ChatAction)

    async def handler_chat_action(event):

        try:

            chat = await event.get_chat()

            chat_id = getattr(chat, "id", 0)

            chat_title = getattr(chat, "title", "") or ""

            norm_id = normalizar_chat_id(chat_id)

            info_chat = chats_vigilados.get(chat_id)

            if not info_chat:

                for cid, cinfo in list(chats_vigilados.items()):

                    if normalizar_chat_id(cid) == norm_id:

                        info_chat = cinfo

                        break

            if not info_chat:

                # Whitelist Estricto: Ignorar eventos de chats no autorizados
                return

            nombre_mentor = info_chat["mentor"]

            msg = getattr(event, "action_message", None)

            if msg:

                await procesar_mensaje_vigia(msg, chat_title, nombre_mentor, cfg, es_catchup=False, client=client)

        except Exception as e_act:

            safe_print(f"[Vigía ChatAction] Aviso: {e_act}")

    try:

        await client.start()

        safe_print("\n[Vigía Telegram] ✅ Conexión establecida con éxito.")

        # Resolver chats vigilados

        vigilados_resueltos = await resolver_dialogos_vigilados(client, mentores_reg)

        chats_vigilados.clear()

        chats_vigilados.update(vigilados_resueltos)

        # -------------------------------------------------------------

        # BARRIDO HISTÓRICO (CATCH-UP) AL INICIAR

        # -------------------------------------------------------------

        await ejecutar_barrido_historico(client, chats_vigilados, cfg)

        safe_print("[Vigía Telegram] 🟢 Escucha pasiva activada (Consumo de CPU en reposo: 0%).")

        await client.run_until_disconnected()

    finally:

        try:

            if client.is_connected():

                await client.disconnect()

        except Exception:

            pass

async def main():

    safe_print("=" * 80)

    safe_print("       VIGIA DE MENTORIAS - UNIVERSIDAD ONLINE (MULTIMODAL + VOICE CHATS)")

    safe_print("=" * 80)

    while True:

        try:

            await ejecutar_vigia()

            safe_print("\n[Vigía Telegram] Sesión finalizada o reiniciando. Pausa de 15 segundos...")

            await asyncio.sleep(15)

        except (KeyboardInterrupt, SystemExit):

            safe_print("\n🛑 Vigía detenido por el usuario.")

            break

        except (ConnectionError, OSError) as e_net:

            safe_print(f"\n⚠️ [Vigía Red] Caída o desconexión detectada ({e_net}).")

            safe_print("🔄 Reintentando reconexión automática en 15 segundos...")

            await asyncio.sleep(15)

        except (Exception, asyncio.CancelledError) as e_gen:

            safe_print(f"\n[!] Aviso o reconexión en el Vigía: {e_gen}. Reiniciando en 15s...")

            await asyncio.sleep(15)

if __name__ == "__main__":

    asyncio.run(main())

