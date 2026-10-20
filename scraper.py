"""

scraper.py - Extractor inteligente de horarios de Masterclasses de Universidad.Online

con detección de zona horaria local ("hora Bolivia", America/La_Paz -04:00)

vs HTML estático / Los Ángeles, compatible con Python 3.8 y 3.10+ (Windows 8 / 10 / 11).

"""

import asyncio

import datetime

import html

import json

import os

import re

import sys

from typing import Optional, Dict, Any, List, Tuple

if sys.platform == "win32":

    try:

        sys.stdout.reconfigure(encoding="utf-8")

        sys.stderr.reconfigure(encoding="utf-8")

    except Exception:

        pass

import pytz

import requests

from bs4 import BeautifulSoup

import calendar_sync

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

URL_UNIVERSIDAD = "https://universidad.online/"

MESES_ES = {

    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,

    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12

}

def formatear_hora_am_pm(dt: datetime.datetime) -> str:

    """Retorna la hora en formato 12h con am/pm en minúsculas y sin cero inicial (ej: '6:30pm')."""

    s = dt.strftime("%I:%M%p").lower()

    if s.startswith("0"):

        s = s[1:]

    return s

def parsear_hora_12h(hora_str: str) -> datetime.time:

    """Parsea una cadena como '6:30pm' o '8am' a objeto datetime.time."""

    h_str = hora_str.strip().lower()

    m = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)$", h_str)

    if m:

        h, minuto, ap = int(m.group(1)), int(m.group(2)), m.group(3)

    else:

        m2 = re.match(r"^(\d{1,2})\s*(am|pm)$", h_str)

        if m2:

            h, minuto, ap = int(m2.group(1)), 0, m2.group(2)

        else:

            raise ValueError(f"Formato horario no reconocido: '{hora_str}'")

    if ap == "pm" and h != 12:

        h += 12

    elif ap == "am" and h == 12:

        h = 0

    return datetime.time(h, minuto)

def parsear_texto_fecha_es(fecha_texto: str, anio_referencia: int) -> Optional[datetime.date]:

    """Parsea textos como '15 de octubre' a datetime.date."""

    m = re.search(r"(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)", fecha_texto.lower())

    if m:

        dia = int(m.group(1))

        mes_nombre = m.group(2)

        mes = MESES_ES.get(mes_nombre)

        if mes:

            return datetime.date(anio_referencia, mes, dia)

    return None

def procesar_rango_horario(

    fecha: datetime.date,

    rango_str: str,

    texto_zona: str,

) -> Tuple[str, str, int, str]:

    """

    Lógica de detección inteligente de zona horaria:

    1. Si el texto indica 'hora Bolivia' (o America/La_Paz / -04:00):

       NO se aplica conversión: se toma la hora directamente como America/La_Paz (-04:00).

    2. Si el texto indica 'hora de Los Ángeles':

       Se interpreta en America/Los_Angeles y se convierte exactamente a America/La_Paz (-04:00).

    Retorna: (inicio_iso, fin_iso, duracion_min, modo_descripcion)

    """

    partes = [p.strip() for p in rango_str.split("-")]

    if len(partes) != 2:

        raise ValueError(f"Formato de rango no válido: '{rango_str}'")

    t_inicio = parsear_hora_12h(partes[0])

    t_fin = parsear_hora_12h(partes[1])

    zona_lower = (texto_zona or "").lower()

    es_bolivia = "bolivia" in zona_lower or "la_paz" in zona_lower or "la paz" in zona_lower or "-04" in zona_lower

    if es_bolivia:

        # Modo Directo: La hora renderizada ya es hora Bolivia

        dt_ini = datetime.datetime.combine(fecha, t_inicio)

        dt_fin = datetime.datetime.combine(fecha, t_fin)

        if dt_fin <= dt_ini:

            dt_fin += datetime.timedelta(days=1)

        duracion_min = int(round((dt_fin - dt_ini).total_seconds() / 60))

        inicio_iso = dt_ini.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        fin_iso = dt_fin.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        modo = "hora Bolivia (Directo sin conversión)"

    else:

        # Modo Conversión: Se convierte de America/Los_Angeles a America/La_Paz (-04:00)

        tz_la = pytz.timezone("America/Los_Angeles")

        tz_lp = pytz.timezone("America/La_Paz")

        dt_ini_la = tz_la.localize(datetime.datetime.combine(fecha, t_inicio))

        dt_fin_la = tz_la.localize(datetime.datetime.combine(fecha, t_fin))

        if dt_fin_la <= dt_ini_la:

            dt_fin_la += datetime.timedelta(days=1)

        dt_ini_lp = dt_ini_la.astimezone(tz_lp)

        dt_fin_lp = dt_fin_la.astimezone(tz_lp)

        duracion_min = int(round((dt_fin_lp - dt_ini_lp).total_seconds() / 60))

        inicio_iso = dt_ini_lp.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        fin_iso = dt_fin_lp.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        modo = "hora Los Ángeles (Convertido a hora Bolivia)"

    return inicio_iso, fin_iso, duracion_min, modo

async def _extraer_con_playwright_async() -> Tuple[List[Dict[str, Any]], str]:

    """

    Abre la página con Playwright (conectando vía CDP a Chrome local si está disponible o lanzando headless).

    Lee las tarjetas renderizadas y el texto 'hora de Bolivia'.

    """

    from playwright.async_api import async_playwright

    async with async_playwright() as p:

        browser = None

        es_cdp = False

        try:

            browser = await p.chromium.connect_over_cdp("http://localhost:9222")

            context = browser.contexts[0]

            es_cdp = True

        except Exception:

            pass

        if not browser:

            try:

                browser = await p.chromium.launch(headless=True, channel="chrome")

            except Exception:

                browser = await p.chromium.launch(headless=True)

            context = await browser.new_context(

                timezone_id="America/La_Paz",

                locale="es-BO",

            )

        page = await context.new_page()

        try:

            await page.goto(URL_UNIVERSIDAD, wait_until="domcontentloaded", timeout=20000)

            try:

                await page.wait_for_selector("#uo-calendar", timeout=12000)

            except Exception:

                pass

            await page.wait_for_timeout(1500)

            eval_data = await page.evaluate(

                """() => {

                const groups = document.querySelectorAll('.uoc-daygroup');

                const cardsData = [];

                groups.forEach(g => {

                    const label = g.querySelector('.uoc-daygroup__label')?.innerText.trim() || '';

                    const dateText = g.querySelector('.uoc-daygroup__date')?.innerText.trim() || '';

                    const cards = g.querySelectorAll('.uoc-card');

                    cards.forEach(c => {

                        const time = c.querySelector('.uoc-card__time')?.innerText.trim() || '';

                        const title = c.querySelector('.uoc-card__title')?.innerText.trim() || '';

                        const zone = c.querySelector('.uoc-card__zone')?.innerText.trim() || '';

                        const link = c.querySelector('a')?.href || '';

                        cardsData.push({ label, dateText, time, title, zone, link });

                    });

                });

                const preloadItems = window.uocConfig && window.uocConfig.preload ? window.uocConfig.preload.items : [];

                return { cards: cardsData, preload: preloadItems };

            }"""

            )

            return eval_data.get("cards", []), eval_data.get("preload", [])

        finally:

            await page.close()

            if not es_cdp and browser:

                await browser.close()

def extraer_con_playwright() -> Tuple[List[Dict[str, Any]], str]:

    """Wrapper compatible para ejecutar la extracción de Playwright tanto dentro como fuera de un bucle asyncio."""

    import concurrent.futures

    try:

        loop = asyncio.get_running_loop()

    except RuntimeError:

        loop = None

    if loop and loop.is_running():

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

            fut = executor.submit(asyncio.run, _extraer_con_playwright_async())

            return fut.result(timeout=45)

    else:

        return asyncio.run(_extraer_con_playwright_async())

def extraer_con_requests() -> List[Dict[str, Any]]:

    """Extrae las clases a través de requests leyendo window.uocConfig del HTML estático."""

    headers = {

        "User-Agent": (

            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "

            "AppleWebKit/537.36 (KHTML, like Gecko) "

            "Chrome/124.0.0.0 Safari/537.36"

        ),

        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",

        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",

    }

    try:

        resp = requests.get(URL_UNIVERSIDAD, headers=headers, timeout=15)

        resp.raise_for_status()

        html_content = resp.text

        m = re.search(r"window\.uocConfig\s*=\s*(\{.*?\});\s*(?:/\*|#|\n|<)", html_content, re.DOTALL)

        if m:

            config_data = json.loads(m.group(1))

            return config_data.get("preload", {}).get("items", [])

        soup = BeautifulSoup(html_content, "html.parser")

        for script in soup.find_all("script"):

            script_text = script.string or ""

            if "window.uocConfig" in script_text:

                m2 = re.search(r"window\.uocConfig\s*=\s*(\{.*?\});", script_text, re.DOTALL)

                if m2:

                    config_data = json.loads(m2.group(1))

                    return config_data.get("preload", {}).get("items", [])

    except Exception as exc:

        print(f"[Aviso] No se pudo extraer vía requests: {exc}")

    return []

def obtener_clases_inteligente(

    preferir_navegador: bool = True,

    config: Optional[Dict[str, Any]] = None,

) -> Tuple[List[Dict[str, Any]], str]:

    """

    Obtiene las clases de HOY y MAÑANA aplicando la lógica inteligente solicitada:

    1. Si se usa el navegador (Playwright), detecta el texto 'hora de Bolivia' y

       toma las horas DIRECTAMENTE como America/La_Paz (-04:00) sin conversión.

    2. Si se usa requests o si el texto fijo es 'hora de Los Ángeles', calcula

       la equivalencia exacta minuto a minuto con America/La_Paz (-04:00).

    Asegura que el offset '-04:00' esté explícito en inicio_iso y fin_iso.

    """

    cfg = config or calendar_sync.cargar_config()

    tz_local = pytz.timezone("America/La_Paz")

    ahora_local = datetime.datetime.now(tz_local)

    hoy_local = ahora_local.date()

    manana_local = hoy_local + datetime.timedelta(days=1)

    cards_dom = []

    preload_items = []

    fuente_usada = ""

    if preferir_navegador:

        try:

            cards_dom, preload_items = extraer_con_playwright()

            fuente_usada = "Navegador Playwright (Chrome local)"

        except Exception as exc:

            print(f"[Aviso] No se pudo ejecutar Playwright ({exc}). Usando requests...")

            fuente_usada = "HTML estático (requests)"

    if not cards_dom and not preload_items:

        preload_items = extraer_con_requests()

        fuente_usada = "HTML estático (requests)"

    clases_resultado = []

    titulos_procesados = set()

    # Primero procesar tarjetas visibles del DOM si están disponibles

    if cards_dom:

        for card in cards_dom:

            raw_title = card.get("title", "").strip()

            if not raw_title:

                continue

            titulo_limpio = html.unescape(raw_title)

            id_clase = database.normalizar_id(titulo_limpio)

            time_range = card.get("time", "")

            zone_text = card.get("zone", "hora de Bolivia")

            label_dia = card.get("label", "").lower()

            date_text = card.get("dateText", "")

            # Determinar fecha exacta

            fecha_card = parsear_texto_fecha_es(date_text, hoy_local.year)

            if not fecha_card:

                if "hoy" in label_dia:

                    fecha_card = hoy_local

                elif "mañana" in label_dia or "manana" in label_dia:

                    fecha_card = manana_local

                else:

                    continue

            # Filtrar solo HOY y MAÑANA

            if fecha_card not in (hoy_local, manana_local):

                continue

            dia_tag = "HOY" if fecha_card == hoy_local else "MAÑANA"

            inicio_iso, fin_iso, duracion_min, modo_det = procesar_rango_horario(

                fecha=fecha_card,

                rango_str=time_range,

                texto_zona=zone_text,

            )

            # Rango formateado en hora Bolivia

            t_ini_dt = datetime.datetime.fromisoformat(inicio_iso)

            t_fin_dt = datetime.datetime.fromisoformat(fin_iso)

            horario_bolivia = f"{formatear_hora_am_pm(t_ini_dt)} - {formatear_hora_am_pm(t_fin_dt)}"

            clase_obj = {

                "id_clase": id_clase,

                "titulo_original": titulo_limpio,

                "dia": dia_tag,

                "fecha": fecha_card.strftime("%Y-%m-%d"),

                "horario_bolivia": horario_bolivia,

                "inicio_iso": inicio_iso,

                "fin_iso": fin_iso,

                "duracion_min": duracion_min,

                "zona_detectada": zone_text,

                "modo_procesamiento": modo_det,

                "url_hotmart": card.get("link", ""),

                "timestamp_sort": int(t_ini_dt.timestamp()),

            }

            clases_resultado.append(clase_obj)

            titulos_procesados.add(id_clase)

    # Si hay items en preload que no salieron en las tarjetas DOM (por ejemplo, clases pasadas de HOY)

    # o si se usó el modo requests:

    if preload_items:

        for item in preload_items:

            ts_start = item.get("start")

            ts_end = item.get("end")

            if not ts_start or not ts_end:

                continue

            # Convertir timestamp a America/La_Paz (-04:00) exactamente como hace el JS public.js

            dt_start_lp = datetime.datetime.fromtimestamp(ts_start, tz_local)

            dt_end_lp = datetime.datetime.fromtimestamp(ts_end, tz_local)

            fecha_clase = dt_start_lp.date()

            if fecha_clase not in (hoy_local, manana_local):

                continue

            dia_tag = "HOY" if fecha_clase == hoy_local else "MAÑANA"

            titulo_limpio = html.unescape(item.get("title", "").strip())

            id_clase = database.normalizar_id(titulo_limpio)

            # Si ya se procesó desde el DOM visible, no duplicar

            if id_clase in titulos_procesados:

                continue

            duracion_min = item.get("duration_min")

            if not duracion_min:

                duracion_min = int(round((ts_end - ts_start) / 60))

            inicio_iso = dt_start_lp.strftime("%Y-%m-%dT%H:%M:%S-04:00")

            fin_iso = dt_end_lp.strftime("%Y-%m-%dT%H:%M:%S-04:00")

            horario_bolivia = f"{formatear_hora_am_pm(dt_start_lp)} - {formatear_hora_am_pm(dt_end_lp)}"

            loc = item.get("location")

            url_hotmart = loc.get("value") if isinstance(loc, dict) else (loc if isinstance(loc, str) else "")

            clase_obj = {

                "id_clase": id_clase,

                "titulo_original": titulo_limpio,

                "dia": dia_tag,

                "fecha": fecha_clase.strftime("%Y-%m-%d"),

                "horario_bolivia": horario_bolivia,

                "inicio_iso": inicio_iso,

                "fin_iso": fin_iso,

                "duracion_min": int(duracion_min),

                "zona_detectada": "hora de Bolivia (Cálculo directo local JS)",

                "modo_procesamiento": "Timestamp convertido a America/La_Paz (-04:00)",

                "url_hotmart": url_hotmart,

                "timestamp_sort": ts_start,

            }

            clases_resultado.append(clase_obj)

            titulos_procesados.add(id_clase)

    # Ordenar cronológicamente

    clases_resultado.sort(key=lambda x: x["timestamp_sort"])

    return clases_resultado, fuente_usada

def ejecutar_scraper_y_sincronizacion() -> List[Dict[str, Any]]:

    """

    Ejecuta el flujo completo corrigiendo horarios con zona horaria local (-04:00):

    1. Extrae clases con detección inteligente.

    2. Actualiza SQLite clases.db.

    3. Sincroniza con Google Calendar vía Webhook.

    4. Imprime tabla formateada en consola con los horarios exactos en hora Bolivia.

    """

    cfg = calendar_sync.cargar_config()

    database.init_db()

    print("=" * 115)

    print("      BOT UNIVERSIDAD ONLINE - EXTRACCIÓN INTELIGENTE Y SINCRONIZACIÓN GOOGLE CALENDAR")

    print("=" * 115)

    print(f"Zona horaria local:  America/La_Paz (UTC-4, offset: -04:00)")

    print(f"Webhook Calendar:    {cfg.get('calendar_webhook_url')}")

    print("-" * 115)

    clases, fuente = obtener_clases_inteligente(preferir_navegador=True, config=cfg)

    print(f"Fuente de extracción: {fuente}")

    print(f"Total clases detectadas para HOY y MAÑANA: {len(clases)}\n")

    if not clases:

        print("[!] No se detectaron clases para hoy ni mañana.")

        return []

    # Encabezado de tabla

    header = f"{'DÍA':<7} | {'HORA BOLIVIA':<17} | {'OFFSET':<7} | {'DUR':<7} | {'ESTADO BD':<11} | {'WEBHOOK':<11} | {'TÍTULO'}"

    print(header)

    print("-" * 115)

    resultados_finales = []

    for c in clases:

        id_clase = c["id_clase"]

        titulo = c["titulo_original"]

        # Verificar / Registrar en SQLite

        reg = database.obtener_clase(id_clase)

        duracion_clase = int(c.get("duracion_min") or 60)

        if not reg:

            database.guardar_o_actualizar_clase(

                id_clase=id_clase,

                titulo_original=titulo,

                fecha_grabacion=c["inicio_iso"],

                estado="PENDIENTE",

                duracion_min=duracion_clase,

            )

            estado_bd = "PENDIENTE"

        else:

            estado_bd = reg.get("estado", "PENDIENTE")

            # Actualizar fecha de grabación y duración correcta

            database.guardar_o_actualizar_clase(

                id_clase=id_clase,

                titulo_original=titulo,

                fecha_grabacion=c["inicio_iso"],

                estado=estado_bd,

                duracion_min=duracion_clase,

            )

        # Sincronizar con Google Calendar

        res_sync = calendar_sync.sincronizar_clase(c, config=cfg)

        webhook_resp = res_sync.get("respuesta", "ERROR")

        if not res_sync.get("exito"):

            webhook_resp = f"ERR: {res_sync.get('error', 'Fallo')[:10]}"

        dur_str = f"{c['duracion_min']} min"

        fila = (

            f"{c['dia']:<7} | "

            f"{c['horario_bolivia']:<17} | "

            f"{'-04:00':<7} | "

            f"{dur_str:<7} | "

            f"{estado_bd:<11} | "

            f"{webhook_resp:<11} | "

            f"{titulo}"

        )

        print(fila)

        c_res = dict(c)

        c_res["estado_bd"] = estado_bd

        c_res["webhook_resp"] = webhook_resp

        c_res["webhook_exito"] = res_sync.get("exito", False)

        resultados_finales.append(c_res)

    print("-" * 115)

    total_exitos = sum(1 for r in resultados_finales if r["webhook_exito"])

    print(f"[RESUMEN] Total clases: {len(resultados_finales)} | Sincronizadas exitosamente con Webhook: {total_exitos}/{len(resultados_finales)}")

    print("=" * 115)

    return resultados_finales

if __name__ == "__main__":

    ejecutar_scraper_y_sincronizacion()

