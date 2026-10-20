"""
notebooklm_bot.py - Automatización Inteligente de NotebookLM vía CDP (localhost:9222)
Gestión estricta de cuadernos aislados, subida de fuentes (.mp3/.md) y generación de Podcasts respetando límites.
Compatible con Python 3.8 y 3.10+ (Windows 8 / 10 / 11).
"""

import asyncio
import datetime
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional, Dict, Any, Tuple, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright, Page, BrowserContext

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
NOTEBOOKLM_BASE_URL = "https://notebook.google.com/"
FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")


def cargar_config() -> Dict[str, Any]:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)



# Tabla de normalización: mapea variaciones de nombre → nombre canónico oficial del cuaderno.
# Evita cuadernos duplicados por diferencias tipográficas menores.
_TRANSVERSAL_CANONICA = {
    # Ventas
    "ventas y negocios": "Ventas y Negociación",
    "ventas y negocio": "Ventas y Negociación",
    "ventas y negociacion": "Ventas y Negociación",
    "ventas y negociación": "Ventas y Negociación",
    "ventas": "Ventas y Negociación",
    "negociacion": "Ventas y Negociación",
    "negociación": "Ventas y Negociación",
    # Marketing
    "marketing digital": "Marketing Digital",
    "marketing digital y ventas": "Marketing Digital",
    "marketing": "Marketing Digital",
    # Tráfico y Publicidad
    "trafico y publicidad": "Tráfico y Publicidad",
    "tráfico y publicidad": "Tráfico y Publicidad",
    "trafico": "Tráfico y Publicidad",
    "tráfico": "Tráfico y Publicidad",
    "publicidad": "Tráfico y Publicidad",
    # Inteligencia Artificial
    "inteligencia artificial": "Inteligencia Artificial",
    "ia": "Inteligencia Artificial",
    "inteligencia artificial y ventas": "Inteligencia Artificial",
    # Emprendimiento
    "emprendimiento": "Emprendimiento y Negocios",
    "emprendimiento y negocios": "Emprendimiento y Negocios",
    "negocios digitales": "Emprendimiento y Negocios",
    "negocios": "Emprendimiento y Negocios",
    # Productividad
    "productividad": "Productividad y Mentalidad",
    "productividad y mentalidad": "Productividad y Mentalidad",
    "mentalidad": "Productividad y Mentalidad",
    "habitos": "Productividad y Mentalidad",
    "hábitos": "Productividad y Mentalidad",
}


def _normalizar_transversal(transversal: str) -> str:
    """Devuelve el nombre canónico estándar para evitar cuadernos duplicados."""
    clave = transversal.strip().lower() if transversal else "general"
    # Buscar coincidencia exacta
    if clave in _TRANSVERSAL_CANONICA:
        return _TRANSVERSAL_CANONICA[clave]
    # Buscar coincidencia parcial (si la clave contiene alguna palabra clave)
    for patron, canonico in _TRANSVERSAL_CANONICA.items():
        if patron in clave:
            return canonico
    # Sin coincidencia: capitalizar adecuadamente y devolver el original
    return transversal.strip().title() if transversal else "General"


def generar_nombre_cuaderno(transversal: str, parte: int = 1) -> str:
    """Genera el nombre con prefijo estricto de aislamiento para Universidad Online.
    Normaliza el nombre de la categoría para evitar cuadernos duplicados."""
    transversal_canonica = _normalizar_transversal(transversal)
    return f"UO - {transversal_canonica} (Parte {parte})"


async def obtener_o_crear_pagina_notebooklm(context: BrowserContext) -> Page:
    """Busca una pestaña abierta de NotebookLM o navega en una nueva."""
    for page in context.pages:
        url_lower = page.url.lower()
        if "notebook.google.com" in url_lower or "notebooklm.google.com" in url_lower:
            await page.bring_to_front()
            return page

    # Si no existe, abrir en nueva pestaña
    nueva_pagina = await context.new_page()
    await nueva_pagina.goto(NOTEBOOKLM_BASE_URL, wait_until="domcontentloaded", timeout=25000)
    await asyncio.sleep(2)
    return nueva_pagina


async def limpiar_cuadernos_vacios(page: Page) -> int:
    """Elimina automáticamente cualquier 'Cuaderno sin título' con '0 fuentes'."""
    eliminados = 0
    try:
        # Asegurarse de estar en el dashboard de inicio
        if "/notebook/" in page.url:
            await page.goto(NOTEBOOKLM_BASE_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

        while True:
            cards = await page.locator("mat-card, .project-card, [role='listitem']").all()
            encontrado = False
            for c in cards:
                text = (await c.inner_text()).replace("\n", " ")
                if "Cuaderno sin título" in text and "0 fuentes" in text:
                    btn_more = c.locator("button[aria-label*='más'], button:has-text('more_vert')").first
                    if await btn_more.count() > 0:
                        await btn_more.click()
                        await asyncio.sleep(0.8)
                        btn_del = page.locator("button:has-text('Borrar'), button:has-text('Eliminar')").first
                        if await btn_del.count() > 0:
                            await btn_del.click()
                            await asyncio.sleep(0.8)
                            btn_confirm = page.locator("mat-dialog-container button:has-text('Borrar'), mat-dialog-container button:has-text('Eliminar')").first
                            if await btn_confirm.count() > 0:
                                await btn_confirm.click()
                                await asyncio.sleep(1.5)
                                eliminados += 1
                                encontrado = True
                                break
            if not encontrado:
                break
    except Exception as e:
        print(f"[NotebookLM] [Info] Limpieza de cuadernos vacíos omitida: {e}")

    if eliminados > 0:
        print(f"[NotebookLM] 🧹 Se limpiaron {eliminados} cuadernos vacíos automáticamente.")
    return eliminados


def obtener_variantes_busqueda(nombre_cuaderno: str) -> List[str]:
    """Genera variantes y nombres similares para encontrar y reutilizar cuadernos existentes sin duplicar."""
    variantes = [nombre_cuaderno]
    if "Ventas" in nombre_cuaderno or "Negociación" in nombre_cuaderno or "Negocios" in nombre_cuaderno:
        variantes.extend([
            "UO - Ventas y Negociación (Parte 1)",
            "UO - Ventas y Negocios (Parte 1)",
            "UO - Ventas y Negociación",
            "UO - Ventas y Negocios",
            "UO - Ventas",
        ])
    elif "Marketing" in nombre_cuaderno or "Tráfico" in nombre_cuaderno or "Trafico" in nombre_cuaderno or "Publicidad" in nombre_cuaderno:
        variantes.extend([
            "UO - Marketing Digital (Parte 1)",
            "UO - Tráfico y Publicidad (Parte 1)",
            "UO - Marketing Digital",
            "UO - Tráfico y Publicidad",
            "UO - Marketing",
            "UO - Tráfico",
        ])
    elif "Creación" in nombre_cuaderno or "Creacion" in nombre_cuaderno or "Inteligencia Artificial" in nombre_cuaderno or "IA" in nombre_cuaderno:
        variantes.extend([
            "UO - Inteligencia Artificial (Parte 1)",
            "UO - Creación de Productos (Parte 1)",
            "UO - Inteligencia Artificial",
            "UO - Creación de Productos",
            "UO - Creación",
        ])
    elif "Mentalidad" in nombre_cuaderno or "Emprendimiento" in nombre_cuaderno or "Productividad" in nombre_cuaderno:
        variantes.extend([
            "UO - Mentalidad y Estrategia (Parte 1)",
            "UO - Mentalidad y Productividad (Parte 1)",
            "UO - Emprendimiento y Negocios (Parte 1)",
            "UO - Mentalidad",
            "UO - Emprendimiento",
        ])
    return list(dict.fromkeys(variantes))


async def buscar_o_crear_cuaderno(page: Page, nombre_cuaderno: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Busca un cuaderno existente por su nombre estricto o por variantes similares para no duplicar.
    Si ya existe un cuaderno como 'UO - Ventas y Negocios' o 'UO - Ventas y Negociación', lo reutiliza.
    Solo si no existe ninguno similar, crea uno nuevo.
    """
    print(f"\n[NotebookLM] Buscando cuaderno para reutilizar: '{nombre_cuaderno}'...")

    # Si estamos dentro de un cuaderno específico, ir al inicio para listar
    if "/notebook/" in page.url:
        await page.goto(NOTEBOOKLM_BASE_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

    variantes = obtener_variantes_busqueda(nombre_cuaderno)

    # 1. Buscar entre los cuadernos existentes probando todas las variantes
    card_container = None
    nombre_encontrado = None
    for v in variantes:
        cand = page.locator(f"mat-card:has-text('{v}'), .project-card:has-text('{v}')").first
        if await cand.count() > 0:
            card_container = cand
            nombre_encontrado = v
            break
        cand2 = page.locator(f"*:has-text('{v}')").first
        if await cand2.count() > 0:
            card_container = cand2
            nombre_encontrado = v
            break

    if card_container and await card_container.count() > 0:
        print(f"[NotebookLM] ✅ Cuaderno existente encontrado: '{nombre_encontrado}'. Reutilizando sin duplicar...")
        link = card_container.locator("a[href*='/notebook/'], a").first
        if await link.count() > 0:
            href = await link.get_attribute("href")
            if href:
                if href.startswith("/notebook/"):
                    url_dest = f"https://notebook.google.com{href}"
                elif href.startswith("http"):
                    url_dest = href
                else:
                    url_dest = f"https://notebook.google.com/{href.lstrip('/')}"
                print(f"[NotebookLM] Navegando directamente a: {url_dest}")
                await page.goto(url_dest, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                return url_dest, url_dest
            else:
                await link.click(force=True)
        else:
            await card_container.click(force=True)
        await asyncio.sleep(3)
        url_actual = page.url
        print(f"[NotebookLM] ✅ Conectado a cuaderno: {url_actual}")
        return url_actual, url_actual

    # 2. Si no existe ninguno similar, crear nuevo cuaderno
    print(f"[NotebookLM] No existe ningún cuaderno previo para '{nombre_cuaderno}'. Creando nuevo...")
    btn_nuevo = page.locator("button:has-text('Crear cuaderno'), button:has-text('Nuevo cuaderno'), [aria-label*='Crear cuaderno']").first

    if await btn_nuevo.count() > 0:
        await btn_nuevo.click()
        await asyncio.sleep(4)

        # Si hay un backdrop/modal abierto al inicio ("Agregar fuentes"), cerrarlo con Escape para poder editar el título
        backdrop = page.locator(".cdk-overlay-backdrop")
        if await backdrop.count() > 0:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

        # Renombrar el cuaderno al título oficial
        try:
            titulo_input = page.locator("editable-project-title input.title-input").first
            if await titulo_input.count() > 0:
                await titulo_input.click()
                await titulo_input.fill(nombre_cuaderno)
                await page.keyboard.press("Enter")
                await asyncio.sleep(1)
            else:
                title_area = page.locator("editable-project-title").first
                if await title_area.count() > 0:
                    await title_area.click()
                    await asyncio.sleep(0.5)
                    await page.keyboard.type(nombre_cuaderno)
                    await page.keyboard.press("Enter")
        except Exception as e:
            print(f"[NotebookLM] [Aviso] Asignación de título alternativa: {e}")

        url_actual = page.url
        print(f"[NotebookLM] ✅ Cuaderno '{nombre_cuaderno}' creado: {url_actual}")
        return url_actual, url_actual

    print("[!] No se encontró el botón de crear cuaderno. ¿Se ha iniciado sesión en NotebookLM?")
    return None, None


async def subir_fuentes_a_cuaderno(page: Page, ruta_md: Optional[str] = None, ruta_mp3: Optional[str] = None) -> bool:
    """
    Sube archivos locales (.md y/o .mp3) como nuevas fuentes al cuaderno activo en NotebookLM.
    Utiliza el selector exacto de File Chooser probado con éxito.
    """
    archivos_a_subir = []
    if ruta_md and os.path.exists(ruta_md):
        archivos_a_subir.append(os.path.abspath(ruta_md))
    if ruta_mp3 and os.path.exists(ruta_mp3):
        archivos_a_subir.append(os.path.abspath(ruta_mp3))

    if not archivos_a_subir:
        print("[NotebookLM] No hay archivos locales para subir como fuente.")
        return False

    print(f"[NotebookLM] Subiendo {len(archivos_a_subir)} fuentes al cuaderno...")

    try:
        # 1. Abrir diálogo de agregar fuentes si no está visible el botón de 'Subir archivos'
        btn_upload = page.locator("button:has-text('Subir archivos')").first
        if await btn_upload.count() == 0 or not await btn_upload.is_visible():
            btn_add = page.locator("button[aria-label*='Agregar fuente'], button:has-text('Agregar fuentes')").first
            if await btn_add.count() > 0:
                await btn_add.click()
                await asyncio.sleep(1.5)

        # 2. Pulsar botón 'Subir archivos' activando el selector de archivos
        btn_upload = page.locator("button:has-text('Subir archivos')").first
        if await btn_upload.count() > 0:
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await btn_upload.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(archivos_a_subir)
            print(f"[NotebookLM] ✅ Archivos cargados exitosamente. Esperando procesamiento...")
            await asyncio.sleep(6)
            return True
        else:
            # Fallback directo con input[type='file']
            file_input = page.locator("input[type='file']").first
            if await file_input.count() > 0:
                await file_input.set_input_files(archivos_a_subir)
                print(f"[NotebookLM] ✅ Archivos cargados vía input[type=file].")
                await asyncio.sleep(6)
                return True
    except Exception as exc:
        print(f"[!] Error subiendo fuentes a NotebookLM: {exc}")

    return False


async def consultar_y_generar_material_notebooklm(
    page: Page,
    titulo_clase: str,
    analisis_existente: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Exclusividad de NotebookLM (Cero Gemini genérico):
    Envía un prompt estructurado al chat de NotebookLM dentro del cuaderno activo.
    Extrae el Mapa Mental en Mermaid.js, el Checklist de 15 min, las Flashcards de estudio
    y los pasos de Infografía grounded exclusivamente en las fuentes del cuaderno.
    """
    print(f"\n[NotebookLM Motor Pedagógico] Generando material didáctico exclusivo para: '{titulo_clase}'...")
    material: Dict[str, Any] = {}

    prompt = (
        f"Actúa como sintetizador pedagógico para la Masterclass '{titulo_clase}'. "
        f"Basándote EXCLUSIVAMENTE en las fuentes de este cuaderno, genera el material didáctico estructurado:\n\n"
        f"1. MAPA MENTAL MERMAID:\n"
        f"Genera un bloque de código Mermaid (iniciando con ```mermaid graph TD y terminando con ```) que organice visualmente la clase de forma jerárquica con nodos y flechas claras.\n\n"
        f"2. CHECKLIST DE 15 MINUTOS:\n"
        f"Genera 4 a 6 pasos concretos y accionables para ejecutar de inmediato tras ver la clase.\n\n"
        f"3. FLASHCARDS DE ESTUDIO:\n"
        f"Genera 5 tarjetas de repaso (Formato: P: [Pregunta] | R: [Respuesta concreta]).\n\n"
        f"4. INFOGRAFIA PASOS:\n"
        f"Genera 4 pasos secuenciales del método enseñado con icono temático, título corto y explicación clara."
    )

    try:
        # Cerrar posibles modales abiertos
        await page.keyboard.press("Escape")
        await asyncio.sleep(1)

        chat_locators = [
            "textarea[placeholder*='mensaje']",
            "textarea[placeholder*='message']",
            "textarea[placeholder*='fuentes']",
            "textarea.query-box-input",
            "textarea",
            "div[contenteditable='true']",
            "[role='textbox']",
        ]
        chat_input = None
        for loc in chat_locators:
            el = page.locator(loc).first
            if await el.count() > 0 and await el.is_visible():
                chat_input = el
                break

        if chat_input:
            print("[NotebookLM] Enviando consulta al chat de fuentes de NotebookLM...")
            await chat_input.click()
            await asyncio.sleep(0.5)
            await chat_input.fill(prompt)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

            btn_send = page.locator("button[aria-label*='Enviar'], button[aria-label*='Send'], button:has-text('send')").first
            if await btn_send.count() > 0 and await btn_send.is_visible():
                try:
                    await btn_send.click(timeout=2000)
                except Exception:
                    pass

            print("[NotebookLM] Esperando respuesta de NotebookLM (grounded en fuentes)...")
            texto_respuesta = ""
            for intento_espera in range(12):
                await asyncio.sleep(2.5)
                resp_els = page.locator(".chat-message, .response-text, .rendered-markdown, div[role='region'] p, [data-message-author='bot'], mat-card").all()
                all_els = await resp_els
                if all_els:
                    ultimo = all_els[-1]
                    t = await ultimo.inner_text()
                    if len(t) > len(texto_respuesta):
                        texto_respuesta = t
                    elif len(texto_respuesta) > 80:
                        break

            if texto_respuesta:
                print(f"[NotebookLM] ✅ Respuesta recibida de NotebookLM ({len(texto_respuesta)} caracteres).")

                # 1. Extraer Mermaid
                m_mermaid = re.search(r"```(?:mermaid)?\s*(graph\s+[TBR][DLR][\s\S]*?)```", texto_respuesta, re.IGNORECASE)
                if m_mermaid:
                    material["mapa_mental_mermaid"] = m_mermaid.group(1).strip()
                elif "graph TD" in texto_respuesta or "graph LR" in texto_respuesta:
                    m_graph = re.search(r"(graph\s+[TBR][DLR][\s\S]+?)(?:\n\n\d|\n\n[A-Z]|```|$)", texto_respuesta)
                    if m_graph:
                        material["mapa_mental_mermaid"] = m_graph.group(1).strip()

                # 2. Extraer Checklist
                lineas = texto_respuesta.split("\n")
                chk_items = []
                en_checklist = False
                for l in lineas:
                    l_clean = l.strip()
                    if "checklist" in l_clean.lower() or "15 minutos" in l_clean.lower():
                        en_checklist = True
                        continue
                    if en_checklist:
                        if l_clean.startswith(("- [ ]", "* [ ]", "-", "*")) or re.match(r"^\d+[\.\)]", l_clean):
                            item_txt = re.sub(r"^[-*]\s*(\[[ xX]\])?\s*|^\d+[\.\)]\s*", "", l_clean).strip()
                            if item_txt:
                                chk_items.append(item_txt)
                        elif "flashcard" in l_clean.lower() or "infografia" in l_clean.lower():
                            en_checklist = False
                if chk_items:
                    material["checklist_15_min"] = chk_items[:6]

                # 3. Extraer Flashcards
                flashcards = []
                for m_fc in re.finditer(r"(?:P|Pregunta|Q):\s*(.+?)\s*(?:\||\n)\s*(?:R|Respuesta|A):\s*(.+?)(?=(?:\n(?:P|Pregunta|Q):)|$)", texto_respuesta, re.IGNORECASE | re.DOTALL):
                    preg = m_fc.group(1).strip()
                    resp = m_fc.group(2).strip()
                    if preg and resp:
                        flashcards.append({"pregunta": preg, "respuesta": resp})
                if flashcards:
                    material["flashcards"] = flashcards[:5]
        else:
            print("[NotebookLM] [Aviso] Chat de NotebookLM no disponible de inmediato.")
    except Exception as e_chat:
        print(f"[NotebookLM] [Aviso] Consulta a chat de NotebookLM: {e_chat}")

    # Garantizar valores por defecto limpios basados en la clase si faltó alguno
    if not material.get("mapa_mental_mermaid"):
        material["mapa_mental_mermaid"] = (
            f"graph TD\n"
            f'  A["🎓 {titulo_clase}"] --> B["Fundamentos Estratégicos"]\n'
            f'  A --> C["Metodología de Aplicación"]\n'
            f'  B --> D["Palanca 20% Vital"]\n'
            f'  C --> E["Checklist de Acción Inmediata"]\n'
            f'  E --> F["Escalado y Conversión"]'
        )

    if not material.get("checklist_15_min") and analisis_existente:
        material["checklist_15_min"] = analisis_existente.get("checklist_15_min", [
            f"Definir el objetivo prioritario de {titulo_clase}",
            "Identificar la palanca del 20% vital de la lección",
            "Ejecutar la primera acción práctica sin perfeccionismo",
            "Validar resultados preliminares en 15 minutos",
        ])

    if not material.get("flashcards") and analisis_existente:
        material["flashcards"] = analisis_existente.get("flashcards", [])

    return material


async def gestionar_studio_y_podcast(
    page: Page,
    id_clase: str,
    titulo_clase: str,
    es_pareto_vital: bool,
    carpeta_destino: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Gestiona la generación y descarga del Podcast Didáctico (Audio Overview) en NotebookLM Studio:
    1. Si ya está generado, lo descarga directamente vía CDP a la carpeta de la clase.
    2. Si aún no está generado y hay cupo diario (<3), abre el modal de personalización y pulsa 'Generar ahora'.
    Retorna (ruta_podcast, None).
    """
    fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
    podcasts_hoy = database.obtener_conteo_podcasts_hoy(fecha_hoy)

    print(f"\n[NotebookLM Studio] Conteo diario de Podcasts hoy: {podcasts_hoy}/3")

    ruta_podcast_descargado = None
    sp = page.locator("studio-panel")

    try:
        # Configurar directorio de descargas en Chrome vía CDP
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": os.path.abspath(carpeta_destino),
            "eventsEnabled": True
        })

        # 1. Comprobar si ya existe un audio generado listo para descargar
        btn_more = sp.locator("button[aria-label='Más'], button:has-text('more_vert')").first
        if await btn_more.count() > 0:
            print("[NotebookLM Studio] Audio Overview detectado en Studio. Iniciando descarga...")
            # Cerrar menús previos con Escape
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            await btn_more.click()
            await asyncio.sleep(1)

            btn_dl = page.locator("button:has-text('Descargar'), [role='menuitem']:has-text('Descargar')").first
            if await btn_dl.count() > 0:
                await btn_dl.click()
                print("[NotebookLM Studio] Descarga iniciada. Esperando finalización del archivo...")

                # Esperar a que desaparezca el .crdownload
                for _ in range(30):
                    await asyncio.sleep(1.5)
                    archivos = os.listdir(carpeta_destino)
                    crdownloads = [f for f in archivos if f.endswith(".crdownload")]
                    audios = [f for f in archivos if f.endswith((".m4a", ".mp3", ".wav")) and not f.endswith("_audio.mp3")]
                    if not crdownloads and audios:
                        ultimo_audio = max([os.path.join(carpeta_destino, f) for f in audios], key=os.path.getmtime)
                        if os.path.getsize(ultimo_audio) > 1024 * 50:
                            ruta_podcast_descargado = ultimo_audio
                            print(f"[NotebookLM Studio] ✅ Audio Overview descargado con éxito: {os.path.basename(ruta_podcast_descargado)} ({os.path.getsize(ruta_podcast_descargado)/(1024*1024):.1f} MB)")
                            break

        # 2. Si no hay audio aún y hay cupo diario, solicitar nueva generación
        limite_detectado = False
        if not ruta_podcast_descargado and podcasts_hoy < 3:
            btn_audio = sp.locator("button[aria-label='Resumen en audio'], [aria-label*='Resumen en audio']").first
            if await btn_audio.count() > 0 and await btn_audio.is_visible():
                print(f"[NotebookLM Studio] Solicitando nuevo Audio Overview para '{titulo_clase}'...")
                await btn_audio.click()
                await asyncio.sleep(2)

                # Pulsar 'Generar ahora' en el diálogo de personalización
                btn_generar_ahora = page.locator("button:has-text('Generar ahora')").first
                if await btn_generar_ahora.count() > 0:
                    await btn_generar_ahora.click()
                    await asyncio.sleep(2)

                    # Verificar si saltó algún mensaje de cuota o límite en la interfaz
                    toast_limite = page.locator("*:has-text('límite'), *:has-text('limite'), *:has-text('Try again later'), *:has-text('reached your limit')")
                    if await toast_limite.count() > 0 and await toast_limite.first.is_visible():
                        print("[NotebookLM Studio] ⚠️ Límite de uso gratuito alcanzado en NotebookLM.")
                        limite_detectado = True
                    else:
                        print(f"[NotebookLM Studio] ✅ ¡Generación de Audio Overview iniciada! Estará listo en 3-5 minutos.")
                        database.registrar_podcast_hoy(id_clase, fecha_hoy)
        elif podcasts_hoy >= 3 and not ruta_podcast_descargado:
            print(f"[NotebookLM Studio] Cupo máximo diario alcanzado ({podcasts_hoy}/3 hoy).")
            limite_detectado = True

        if limite_detectado and not ruta_podcast_descargado:
            return None, "LIMITE_ALCANZADO_5H"

    except Exception as exc:
        print(f"[!] Error interactuando con NotebookLM Studio: {exc}")

    return ruta_podcast_descargado, ("OK" if ruta_podcast_descargado else "PENDIENTE")


async def procesar_clase_en_notebooklm(
    clase_info: Dict[str, Any],
    analisis: Dict[str, Any],
    ruta_mp3: Optional[str] = None,
    ruta_md: Optional[str] = None,
    cdp_url: str = "http://localhost:9222",
) -> Dict[str, Any]:
    """
    Punto de entrada principal para procesar una clase en NotebookLM:
    1. Determina el cuaderno correspondiente (con aislamiento UO - {transversal} (Parte {N})).
    2. Sube la ficha Markdown y el audio MP3.
    3. Si hay cupo, genera o descarga el Audio Overview. Si alcanza el límite, encola automáticamente para reintentar en 5 horas.
    4. Guarda la información en clases.db y retorna el resultado.
    """
    titulo = clase_info.get("titulo_original", "Masterclass")
    id_clase = clase_info.get("id_clase", database.normalizar_id(titulo))
    transversal = analisis.get("transversal", "General")

    vc = analisis.get("vertical_creacion", {})
    vcom = analisis.get("vertical_comercializacion", {})
    es_pareto = vc.get("es_pareto_20_vital", False) or vcom.get("es_pareto_20_vital", False)

    # Calcular parte según fuentes registradas (< 45 por parte)
    fuentes_actuales = database.contar_fuentes_cuaderno(transversal)
    parte = (fuentes_actuales // 45) + 1
    nombre_cuaderno = generar_nombre_cuaderno(transversal, parte)

    resultado = {
        "nombre_cuaderno": nombre_cuaderno,
        "notebook_url": None,
        "podcast_archivo": None,
        "fuentes_subidas": False,
    }

    print(f"\n" + "=" * 80)
    print(f"       AUTOMATIZACIÓN NOTEBOOKLM - {titulo}")
    print(f"=" * 80)
    print(f"Cuaderno objetivo: {nombre_cuaderno}")
    print(f"Es Pareto 20 Vital: {es_pareto}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            print(f"[NotebookLM] [Aviso] No se pudo conectar a Chrome en {cdp_url}: {exc}")
            url_fallback = f"{NOTEBOOKLM_BASE_URL}"
            resultado["notebook_url"] = url_fallback
            database.guardar_info_notebooklm(id_clase=id_clase, notebook_url=url_fallback)
            return resultado

        context = browser.contexts[0]
        page = await obtener_o_crear_pagina_notebooklm(context)

        try:
            # Limpiar posibles cuadernos vacíos
            await limpiar_cuadernos_vacios(page)

            # 1. Buscar o crear cuaderno oficial
            notebook_id, notebook_url = await buscar_o_crear_cuaderno(page, nombre_cuaderno)
            resultado["notebook_url"] = notebook_url or page.url

            # 2. Subir fuentes
            subida_ok = await subir_fuentes_a_cuaderno(page, ruta_md=ruta_md, ruta_mp3=ruta_mp3)
            resultado["fuentes_subidas"] = subida_ok

            # 2.5 Generar material pedagógico exclusivo en NotebookLM (Mermaid, Checklist, Flashcards)
            try:
                material_nlm = await consultar_y_generar_material_notebooklm(page, titulo, analisis)
                if material_nlm:
                    analisis.update(material_nlm)
                    database.guardar_analisis_clase(id_clase, analisis)
                    print(f"[NotebookLM] ✅ Material pedagógico exclusivo inyectado en base de datos para '{titulo}'.")
            except Exception as e_mat:
                print(f"[NotebookLM] [Aviso] Error generando material en NotebookLM: {e_mat}")

            # 3. Studio / Podcast
            carpeta_destino = os.path.dirname(ruta_mp3) if ruta_mp3 else BASE_DIR
            podcast_file, estado_pod = await gestionar_studio_y_podcast(
                page=page,
                id_clase=id_clase,
                titulo_clase=titulo,
                es_pareto_vital=es_pareto,
                carpeta_destino=carpeta_destino,
            )
            resultado["podcast_archivo"] = podcast_file

            # Si el límite fue alcanzado, encolar en lista de espera de 5 horas
            if not podcast_file and estado_pod == "LIMITE_ALCANZADO_5H":
                database.encolar_reintento_notebooklm(
                    id_clase=id_clase,
                    titulo=titulo,
                    ruta_mp3=ruta_mp3,
                    ruta_md=ruta_md,
                    analisis=analisis,
                    horas_espera=5.0,
                )

            # Guardar en SQLite
            fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
            database.guardar_info_notebooklm(
                id_clase=id_clase,
                notebook_url=resultado["notebook_url"],
                podcast_archivo=podcast_file,
                podcast_fecha=fecha_hoy if podcast_file else None,
            )
            print(f"[NotebookLM] ✅ Proceso completado para '{titulo}'.")
        except Exception as err_nlm:
            print(f"[NotebookLM] [Aviso] Error durante la interacción con NotebookLM: {err_nlm}")
            if not resultado.get("notebook_url"):
                resultado["notebook_url"] = NOTEBOOKLM_BASE_URL
        return resultado


async def reintentar_tarea_encolada(tarea: Dict[str, Any], cdp_url: str = "http://localhost:9222") -> Optional[str]:
    """
    Reanuda una tarea en cola tras cumplirse el período de 5 horas:
    Abre el cuaderno en NotebookLM, intenta descargar o generar el podcast pendiente.
    Retorna la ruta del archivo de podcast si tuvo éxito, o None si aún continúa el límite.
    """
    id_clase = tarea["id_clase"]
    titulo = tarea["titulo"]
    ruta_mp3 = tarea.get("ruta_mp3")
    ruta_md = tarea.get("ruta_md")
    analisis_raw = tarea.get("analisis_json")
    analisis = json.loads(analisis_raw) if analisis_raw else {}

    print(f"\n[NotebookLM Queue] 🔄 Reanudando tarea pendiente de: '{titulo}'...")
    clase_dummy = {"id_clase": id_clase, "titulo_original": titulo}
    res = await procesar_clase_en_notebooklm(
        clase_info=clase_dummy,
        analisis=analisis,
        ruta_mp3=ruta_mp3,
        ruta_md=ruta_md,
        cdp_url=cdp_url,
    )
    podcast = res.get("podcast_archivo")
    if podcast:
        database.marcar_reintento_notebooklm_completado(id_clase)
        print(f"[NotebookLM Queue] ✅ Tarea '{titulo}' completada exitosamente. Podcast: {podcast}")
        return podcast
    else:
        database.marcar_reintento_notebooklm_fallido(id_clase, horas_espera=5.0)
        print(f"[NotebookLM Queue] ⏳ Límite aún activo. Pospuesto 5 horas adicionales.")
        return None



    print("=== TEST NOTEBOOKLM_BOT.PY ===")
    clase_dummy = {
        "id_clase": "test_clase_ia",
        "titulo_original": "Masterclass de Inteligencia Artificial y Ventas",
    }
    analisis_dummy = {
        "transversal": "Inteligencia Artificial",
        "vertical_creacion": {"es_pareto_20_vital": True},
        "vertical_comercializacion": {"es_pareto_20_vital": True},
    }
    res = asyncio.run(procesar_clase_en_notebooklm(clase_dummy, analisis_dummy))
    print("Resultado:", res)
