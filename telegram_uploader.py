"""

telegram_uploader.py - Módulo de subida de videos a Telegram usando Telethon

Soporta:

- Corte sin pérdida (Stream Copy) para clases de más de 2 GB.

- Canal separado automático para 'Mentorías Universidad Online'.

- Edición en vivo de mensajes ya publicados en Telegram (Efecto Dominó al cambiar nombre del Mentor).

Compatible con Python 3.8 y 3.10+ (Windows 8 / 10 / 11).

"""

import asyncio

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

from typing import Optional, Dict, Any, Callable, Tuple, List

if sys.platform == "win32":

    try:

        sys.stdout.reconfigure(encoding="utf-8")

        sys.stderr.reconfigure(encoding="utf-8")

    except Exception:

        pass

from telethon import TelegramClient

import hashlib
import math
import random
import threading
from telethon.tl.functions.upload import SaveBigFilePartRequest, SaveFilePartRequest
from telethon.tl.types import InputFileBig, InputFile, DocumentAttributeVideo, DocumentAttributeAudio

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

SESSION_FILE = os.path.join(BASE_DIR, "sesion_telegram.session")

FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")

LIMITE_TELEGRAM_BYTES = 1950 * 1024 * 1024  # 1950 MB límite seguro

TAMANO_OBJETIVO_BYTES = 1850 * 1024 * 1024


async def turbo_subir_archivo_telethon(
    client: TelegramClient,
    ruta_archivo: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    concurrency: int = 4,
    part_size_kb: int = 512,
) -> Any:
    """
    Subida paralela ultra-rápida (Fast-Telethon / Parallel Chunk Uploader):
    Divide el archivo en partes de 512 KB y las envía en paralelo usando 4 workers concurrentes
    y aceleración criptográfica cryptg (AES-IGE por hardware) sin sobrecargar CPU ni RAM.
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")

    tamano_total = os.path.getsize(ruta_archivo)
    nombre_archivo = os.path.basename(ruta_archivo)
    part_size = part_size_kb * 1024  # 512 KB por chunk (máximo soportado por MTProto)
    total_parts = math.ceil(tamano_total / part_size) or 1
    file_id = random.randint(1, 2**63 - 1)
    is_big = tamano_total > 10 * 1024 * 1024

    tamano_mb = tamano_total / (1024 * 1024)
    print(f"\n[Telegram Turbo] Transmitiendo '{nombre_archivo}' ({tamano_mb:.1f} MB en {total_parts} partes de 512KB) con {concurrency} workers paralelos...")

    bytes_subidos = 0
    lock_progreso = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    def _leer_chunk(part_idx: int) -> bytes:
        with open(ruta_archivo, "rb") as f:
            f.seek(part_idx * part_size)
            return f.read(part_size)

    # Pre-calcular checksum solo si el archivo es menor a 10MB
    md5_checksum = ""
    if not is_big:
        h = hashlib.md5()
        with open(ruta_archivo, "rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        md5_checksum = h.hexdigest()

    loop = asyncio.get_running_loop()

    async def _subir_parte(part_idx: int):
        nonlocal bytes_subidos
        # Leer el chunk en un executor para no bloquear el loop de asyncio
        data = await loop.run_in_executor(None, _leer_chunk, part_idx)
        async with sem:
            for reintento in range(3):
                try:
                    if is_big:
                        req = SaveBigFilePartRequest(
                            file_id=file_id,
                            file_part=part_idx,
                            file_total_parts=total_parts,
                            bytes=data,
                        )
                    else:
                        req = SaveFilePartRequest(
                            file_id=file_id,
                            file_part=part_idx,
                            bytes=data,
                        )
                    await client(req)
                    async with lock_progreso:
                        bytes_subidos += len(data)
                        if progress_callback:
                            try:
                                progress_callback(bytes_subidos, tamano_total)
                            except Exception:
                                pass
                    return
                except Exception as e_err:
                    if reintento == 2:
                        raise e_err
                    await asyncio.sleep(1.0 + reintento)

    # Disparar workers en paralelo
    tareas = [_subir_parte(i) for i in range(total_parts)]
    await asyncio.gather(*tareas)
    print(f"\n[Telegram Turbo] ✅ Transmisión de {total_parts} partes completada con éxito.")

    if is_big:
        return InputFileBig(id=file_id, parts=total_parts, name=nombre_archivo)
    else:
        return InputFile(id=file_id, parts=total_parts, name=nombre_archivo, md5_checksum=md5_checksum)


def obtener_atributos_video(ruta_video: str, duracion_min_fallback: int = 60) -> Tuple[int, int, int]:

    duracion = duracion_min_fallback * 60

    ancho, alto = 1280, 720

    try:

        res = subprocess.run([FFMPEG_EXE, "-i", ruta_video], capture_output=True, text=True, errors="replace")

        m_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr or "")

        if m_dur:

            h, m, s = m_dur.groups()

            duracion = int(int(h) * 3600 + int(m) * 60 + float(s))

        m_res = re.search(r"Video:.*,\s*(\d{3,4})x(\d{3,4})", res.stderr or "")

        if m_res:

            ancho, alto = int(m_res.group(1)), int(m_res.group(2))

    except Exception:

        pass

    return duracion, ancho, alto

def obtener_duracion_audio(ruta_audio: str) -> int:

    duracion = 60

    try:

        res = subprocess.run([FFMPEG_EXE, "-i", ruta_audio], capture_output=True, text=True, errors="replace")

        m_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr or "")

        if m_dur:

            h, m, s = m_dur.groups()

            duracion = int(int(h) * 3600 + int(m) * 60 + float(s))

    except Exception:

        pass

    return max(int(duracion), 1)

def asegurar_tamano_video(ruta_video: str, duracion_min_fallback: int = 60) -> str:

    return ruta_video

def dividir_video_sin_perdida(ruta_video: str, duracion_segundos: int) -> List[str]:

    tamano_bytes = os.path.getsize(ruta_video)

    if tamano_bytes <= LIMITE_TELEGRAM_BYTES:

        return [ruta_video]

    num_parts = int((tamano_bytes + TAMANO_OBJETIVO_BYTES - 1) // TAMANO_OBJETIVO_BYTES)

    part_duration = int(duracion_segundos / num_parts) + 2

    print(f"\n[Telegram] ⚠️ ALERTA: El video original pesa {tamano_bytes / (1024*1024):.1f} MB (> 2 GB).")

    print(f"[Telegram] ✂️ Cortando el video en {num_parts} fragmentos sin perder calidad (Stream Copy)...")

    carpeta = os.path.dirname(ruta_video)

    nombre_base = os.path.splitext(os.path.basename(ruta_video))[0]

    partes = []

    for i in range(num_parts):

        ruta_part = os.path.join(carpeta, f"{nombre_base}_parte{i+1}.mp4")

        if os.path.exists(ruta_part):

            try:

                os.remove(ruta_part)

            except Exception:

                pass

        start_time = max(0, i * (part_duration - 2))

        cmd = [FFMPEG_EXE, "-y", "-ss", str(start_time)]

        if i < num_parts - 1:

            cmd.extend(["-t", str(part_duration)])

        cmd.extend(["-i", ruta_video, "-c", "copy", "-avoid_negative_ts", "make_non_negative", ruta_part])

        try:

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(ruta_part) and os.path.getsize(ruta_part) > 1024:

                partes.append(ruta_part)

        except Exception as e:

            print(f"[!] Error cortando fragmento {i+1}: {e}")

    return partes if len(partes) > 0 else [ruta_video]

def cargar_config() -> Dict[str, Any]:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:

        return json.load(f)

def crear_cliente_telegram() -> TelegramClient:

    cfg = cargar_config()

    return TelegramClient(

        os.path.join(BASE_DIR, "sesion_telegram"),

        int(cfg.get("telegram_api_id", 0)),

        str(cfg.get("telegram_api_hash", "")),

    )

async def obtener_canal(client: TelegramClient, titulo_canal: str):

    if not titulo_canal:

        return None

    dialogs = await client.get_dialogs()

    # 1. Coincidencia exacta insensible a mayúsculas

    for d in dialogs:

        if d.title and d.title.strip().lower() == titulo_canal.strip().lower():

            return d.entity

    # 2. Coincidencia normalizada (sin tildes, símbolos, espacios extras)

    norm_target = database.normalizar_id(titulo_canal)

    for d in dialogs:

        if d.title and database.normalizar_id(d.title) == norm_target:

            return d.entity

    # 3. Coincidencia por subcadena

    for d in dialogs:

        if d.title:

            d_norm = database.normalizar_id(d.title)

            if norm_target in d_norm or d_norm in norm_target:

                return d.entity

    # 4. Intento directo por entidad o username

    try:

        ent = await client.get_entity(titulo_canal)

        if ent:

            return ent

    except Exception:

        pass

    return None

def formatear_caption_video(

    titulo_clase: str,

    fecha_clase: str,

    duracion_min: int,

    analisis: Optional[Dict[str, Any]] = None,

    notebook_url: Optional[str] = None,

) -> str:

    if not analisis:

        return f"🎓 {titulo_clase}\n📅 Fecha: {fecha_clase}\n⏱ Duración: {duracion_min} min"

    vc, vcom = analisis.get("vertical_creacion", {}), analisis.get("vertical_comercializacion", {})

    pct_c, pct_com = vc.get("porcentaje_importancia", 0), vcom.get("vertical_comercializacion", {}).get("porcentaje_importancia", vcom.get("porcentaje_importancia", 0))

    vit_c = "🔥 20% VITAL" if vc.get("es_pareto_20_vital") else "💡 80% COMP."

    vit_com = "🔥 20% VITAL" if vcom.get("es_pareto_20_vital") else "💡 80% COMP."

    resumen = analisis.get("resumen_didactico", "")

    if len(resumen) > 300:

        resumen = resumen[:297] + "..."

    nb_url = notebook_url or "https://notebooklm.google.com/"

    mentor = analisis.get("mentor_identificado", "")

    linea_mentor = f"🎙️ Mentor: {mentor}\n" if mentor else ""

    return (

        f"🎓 {titulo_clase}\n"

        f"{linea_mentor}"

        f"📅 Fecha: {fecha_clase} | ⏱ {duracion_min} min | 🏷 {analisis.get('transversal', 'General')}\n\n"

        f"📊 SEMÁFORO PARETO 80/20:\n • Creación: {pct_c}% [{vit_c}]\n • Comercialización: {pct_com}% [{vit_com}]\n\n"

        f"💡 Resumen:\n{resumen}\n\n"

        f"🔗 NotebookLM: {nb_url}\n\n📱 App Web: Material interactivo disponible en tu PWA."

    )

async def subir_entrega_completa_telegram(

    ruta_video: Optional[str] = None,

    titulo_clase: str = "Masterclass",

    fecha_clase: str = "",

    duracion_min: int = 60,

    analisis: Optional[Dict[str, Any]] = None,

    notebook_url: Optional[str] = None,

    ruta_podcast: Optional[str] = None,

    ruta_infografia_png: Optional[str] = None,

    ruta_mapa_mental_png: Optional[str] = None,

    ruta_md_guia: Optional[str] = None,

    ruta_html_rutas: Optional[str] = None,

    adjuntar_archivos_adicionales: bool = False,

    callback_progreso: Optional[Callable[[int, int], None]] = None,

    canal_destino_custom: Optional[str] = None,

) -> Any:

    cfg = cargar_config()

    canal_masterclasses = cfg.get("telegram_channel_title", "Masterclasses Universidad Online")

    canal_mentorias = cfg.get("telegram_mentorias_channel_title", "Mentorías - Universidad Online")

    canal_playbooks = cfg.get("telegram_playbooks_channel_title", "Playbooks - Universidad Online")

    transversal = (analisis.get("transversal") if isinstance(analisis, dict) else "") or ""

    es_pdf_o_doc = bool(ruta_video and ruta_video.lower().endswith((".pdf", ".epub", ".docx", ".doc")))

    es_playbook = (

        transversal == "Playbooks"

        or "playbook" in titulo_clase.lower()

        or es_pdf_o_doc

        or (ruta_md_guia and "playbook" in ruta_md_guia.lower())

    )

    es_mentoria = (

        not es_playbook and (

            transversal == "Mentorías"

            or "mentoría" in titulo_clase.lower()

            or "mentoria" in titulo_clase.lower()

            or "zoom.us" in (ruta_video or "").lower()

            or "chat_voz" in (ruta_video or "").lower()

            or (analisis and analisis.get("mentor_identificado"))

        )

    )

    if canal_destino_custom:

        canal_objetivo = canal_destino_custom

    elif es_playbook:

        canal_objetivo = canal_playbooks

    elif es_mentoria:

        canal_objetivo = canal_mentorias

    else:

        canal_objetivo = canal_masterclasses

    client = crear_cliente_telegram()

    await client.connect()

    if not await client.is_user_authorized():

        await client.disconnect()

        return False

    entity_canal = await obtener_canal(client, canal_objetivo)

    if not entity_canal:

        print(f"\n========================================================================================")

        print(f"⚠️ ERROR CRÍTICO TELEGRAM: No se pudo acceder al canal de destino: '{canal_objetivo}'.")

        print(f"   Por favor verifica que la cuenta pertenezca al canal '{canal_objetivo}' o confirma el nombre exacto.")

        print(f"========================================================================================")

        # Fallback de rescate para no perder el material

        for canal_alt in [canal_mentorias, canal_masterclasses]:

            if canal_alt != canal_objetivo:

                entity_canal = await obtener_canal(client, canal_alt)

                if entity_canal:

                    print(f"[Telegram] ⚠️ Redirigiendo entrega temporalmente al canal alternativo: '{canal_alt}'.")

                    break

    if not entity_canal:

        await client.disconnect()

        return False

    try:

        url_tg, url_app, url_web = "", "", ""

        msg_video_principal = None

        if ruta_video and os.path.exists(ruta_video) and es_pdf_o_doc:

            tamano_mb = os.path.getsize(ruta_video) / (1024 * 1024)

            print(f"\n[Telegram] Subiendo Playbook/Documento: {os.path.basename(ruta_video)} ({tamano_mb:.1f} MB) a '{canal_objetivo}'...")

            caption_doc = f"📘 [PLAYBOOK / GUÍA] {titulo_clase}\n📅 Fecha: {fecha_clase}\n\n{(analisis.get('resumen_didactico', '') if analisis else '')[:600]}\n\n📱 Consulta el material interactivo y flashcards en la App Web."

            msg_doc = await client.send_file(

                entity=entity_canal,

                file=ruta_video,

                caption=caption_doc,

            )

            msg_video_principal = msg_doc

            print(f"[Telegram] ✅ ¡Documento/Playbook subido exitosamente a '{canal_objetivo}'!")

        elif ruta_video and os.path.exists(ruta_video):

            duracion_seg, ancho, alto = obtener_atributos_video(ruta_video, duracion_min)

            partes_video = dividir_video_sin_perdida(ruta_video, duracion_seg)

            for idx, ruta_part in enumerate(partes_video):

                es_multi = len(partes_video) > 1

                texto_parte = f" [🎬 Fragmento {idx+1}/{len(partes_video)}]" if es_multi else ""

                caption_video = formatear_caption_video(

                    titulo_clase=f"{titulo_clase}{texto_parte}",

                    fecha_clase=fecha_clase,

                    duracion_min=int(duracion_min / len(partes_video)) if es_multi else duracion_min,

                    analisis=analisis if idx == 0 else None,

                    notebook_url=notebook_url,

                )

                tamano_mb = os.path.getsize(ruta_part) / (1024 * 1024)

                print(f"\n[Telegram] Subiendo '{titulo_clase}{texto_parte}': {os.path.basename(ruta_part)} ({tamano_mb:.1f} MB)...")

                ultimo_porcentaje = [-1]

                def _progreso_interno(actual: int, total: int):

                    pct = int((actual / total) * 100)

                    if pct % 5 == 0 and pct != ultimo_porcentaje[0]:

                        ultimo_porcentaje[0] = pct

                        sys.stdout.write(f"\r[Telegram] Subiendo video: {pct}%")

                        sys.stdout.flush()

                d_seg, a_part, al_part = obtener_atributos_video(ruta_part, 60)

                # Parallel Turbo Chunk Uploader
                archivo_remoto = ruta_part
                try:
                    archivo_remoto = await turbo_subir_archivo_telethon(
                        client=client,
                        ruta_archivo=ruta_part,
                        progress_callback=_progreso_interno,
                        concurrency=4,
                        part_size_kb=512,
                    )
                except Exception as e_turbo:
                    print(f"\n[Telegram] [Aviso Turbo] Fallback a subida estándar: {e_turbo}")
                    archivo_remoto = ruta_part

                msg_video = None

                max_retries_tg = 3

                for intento_tg in range(1, max_retries_tg + 1):

                    try:

                        msg_video = await client.send_file(

                            entity=entity_canal,

                            file=archivo_remoto,

                            caption=caption_video,

                            attributes=[

                                DocumentAttributeVideo(

                                    duration=d_seg if d_seg > 0 else duracion_seg,

                                    w=a_part if a_part > 0 else ancho,

                                    h=al_part if al_part > 0 else alto,

                                    supports_streaming=True,

                                )

                            ],

                            supports_streaming=True,

                            progress_callback=_progreso_interno,

                        )

                        if msg_video:

                            break

                    except Exception as err_part:

                        print(f"\n[Telegram] ⚠️ Intento {intento_tg}/{max_retries_tg} falló al subir video: {err_part}")

                        if intento_tg < max_retries_tg:

                            print("[Telegram] 🔄 Pausa de 20s para reintentar tras saturación o fallo interno de Telegram (Error 500)...")

                            await asyncio.sleep(20)

                            try:

                                if not client.is_connected():

                                    await client.connect()

                            except Exception:

                                pass

                        else:

                            raise err_part

                if idx == 0:

                    msg_video_principal = msg_video

                print(f"\n[Telegram] ✅ ¡Video{texto_parte} subido exitosamente!")

            if msg_video_principal:

                cid = str(getattr(entity_canal, "id", 0))

                cid = cid[4:] if cid.startswith("-100") else (cid[1:] if cid.startswith("-") else cid)

                username = getattr(entity_canal, "username", None)

                if username:

                    url_tg = f"https://t.me/{username}/{msg_video_principal.id}"

                    url_app = f"tg://resolve?domain={username}&post={msg_video_principal.id}"

                    url_web = f"https://web.telegram.org/k/#?tgaddr=tg%3A%2F%2Fresolve%3Fdomain%3D{username}%26post%3D{msg_video_principal.id}"

                else:

                    url_tg = f"https://t.me/c/{cid}/{msg_video_principal.id}"

                    url_app = f"tg://privatepost?channel={cid}&post={msg_video_principal.id}"

                    url_web = f"https://web.telegram.org/k/#-100{cid}_{msg_video_principal.id}"

        if ruta_podcast and os.path.exists(ruta_podcast):

            print("[Telegram] Subiendo Audio Resumen (Podcast)...")

            await client.send_file(

                entity=entity_canal,

                file=ruta_podcast,

                caption=f"🎧 Audio Resumen / Podcast Didáctico - {titulo_clase}\nGenerado automáticamente.",

                attributes=[

                    DocumentAttributeAudio(

                        duration=obtener_duracion_audio(ruta_podcast),

                        title=f"Podcast - {titulo_clase}",

                        performer="NotebookLM AI",

                    )

                ],

            )

        return {

            "subida_ok": True,

            "telegram_url": url_tg,

            "telegram_app_url": url_app,

            "telegram_web_url": url_web,

            "telegram_msg_id": msg_video_principal.id if msg_video_principal else None,

        }

    except Exception as exc:

        print(f"\n[Telegram] ❌ Error durante la subida: {exc}")

        return None

    finally:

        await client.disconnect()

        # Liberación de memoria en tiempo muerto post-subida
        gc.collect()

async def editar_caption_en_telegram(

    telegram_url: str,

    nuevo_titulo: str,

    fecha_clase: str,

    duracion_min: int,

    analisis: Dict[str, Any],

) -> bool:

    """Edita el mensaje ya publicado en Telegram cuando el usuario actualiza el nombre del Mentor manualmente."""

    if not telegram_url:

        return False

    m = re.search(r"/(\d+)$", telegram_url.strip())

    if not m:

        return False

    msg_id = int(m.group(1))

    cfg = cargar_config()

    client = crear_cliente_telegram()

    await client.connect()

    try:

        for nombre_c in [

            cfg.get("telegram_mentorias_channel_title", "Mentorías Universidad Online"),

            cfg.get("telegram_channel_title", "Masterclasses Universidad Online"),

        ]:

            ent = await obtener_canal(client, nombre_c)

            if ent:

                try:

                    nuevo_caption = formatear_caption_video(nuevo_titulo, fecha_clase, duracion_min, analisis)

                    await client.edit_message(ent, msg_id, text=nuevo_caption)

                    print(f"[Telegram] ✅ Mensaje #{msg_id} actualizado en vivo en el canal '{nombre_c}'.")

                    return True

                except Exception:

                    continue

    finally:

        await client.disconnect()

    return False