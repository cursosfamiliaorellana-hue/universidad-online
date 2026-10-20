"""

programador_manual.py - Centro de Control Total (Hotmart + Mentorías + Efecto Dominó + Mentores + App Web)

"""

import asyncio

import datetime

import json

import os

import re

import sqlite3

import sys

from typing import Any, Dict

if sys.platform == "win32":

    try:

        sys.stdout.reconfigure(encoding="utf-8")

        sys.stderr.reconfigure(encoding="utf-8")

    except Exception:

        pass

import pytz

import calendar_sync

import database

import route_builder

import telegram_uploader

import ai_analyzer

import notebooklm_bot

import glob

import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

ARCHIVO_FRENO_MANUAL = os.path.join(BASE_DIR, "DETENER_GRABACION.txt")

def cargar_config() -> Dict[str, Any]:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:

        return json.load(f)

def normalizar_id(texto: str) -> str:

    texto = texto.lower().strip()

    texto = re.sub(r"[^a-z0-9\s-]", "", texto)

    return re.sub(r"[\s-]+", "_", texto)

def pedir_entero(mensaje: str, minimo: int = 1, maximo: int = 99999) -> int:

    while True:

        try:

            valor = int(input(mensaje).strip())

            if minimo <= valor <= maximo:

                return valor

            print(f"[!] Ingresa un número entre {minimo} y {maximo}.")

        except ValueError:

            print("[!] Por favor, ingresa un número válido.")

def pedir_horario(mensaje: str, tz: Any) -> datetime.datetime:

    while True:

        entrada = input(mensaje).strip().lower()

        if entrada == "ahora":

            return datetime.datetime.now(tz)

        try:

            if ":" in entrada:

                horas, mins = map(int, entrada.split(":"))

                hora_propuesta = datetime.datetime.now(tz).replace(hour=horas, minute=mins, second=0, microsecond=0)

                if hora_propuesta < datetime.datetime.now(tz) - datetime.timedelta(minutes=5):

                    hora_propuesta += datetime.timedelta(days=1)

                return hora_propuesta

            print("[!] Usa 'ahora' o formato 24h como '15:30'.")

        except Exception:

            print("[!] Formato inválido. Ejemplo: 02:30")

def opcion_programar_hotmart(tz_local: Any):

    print("\n--- 1. PROGRAMAR MASTERCLASS DE HOTMART (POR PARTES) ---")

    entrada_clase = input("Pega la URL de Hotmart O escribe el nombre de la clase:\n> ").strip()

    es_url = entrada_clase.startswith("http")

    url_hotmart = entrada_clase if es_url else ""

    nombre_base = input("Escribe un título para identificar esta clase:\n> ").strip() if es_url else entrada_clase

    es_multi = input("¿Está dividida en partes en Hotmart (Parte 1, 2, 3...)? (S/N):\n> ").strip().lower() == "s"

    while True:

        if es_multi:

            num_parte = pedir_entero("\n¿Qué NÚMERO de parte quieres programar? (Ej: 1, 2, 3...):\n> ", minimo=1)

            titulo_parte = f"{nombre_base} (Parte {num_parte})"

            id_parte = f"{normalizar_id(nombre_base)}_p{num_parte}"

            num_hotmart = num_parte

        else:

            titulo_parte = nombre_base

            id_parte = normalizar_id(nombre_base)

            num_hotmart = 0

        hora_inicio = pedir_horario("¿A qué hora debe iniciar a grabar? (Escribe 'ahora' o '02:30'):\n> ", tz_local)

        duracion_min = pedir_entero("¿Cuántos MINUTOS dura esta parte? (Ej: 3h 10m = 190):\n> ", minimo=1)

        analisis_json = json.dumps({"es_busqueda_inteligente": not es_url, "numero_parte_hotmart": num_hotmart})

        inicio_iso = hora_inicio.strftime("%Y-%m-%dT%H:%M:%S-04:00")

        database.guardar_o_actualizar_clase(

            id_clase=id_parte,

            titulo_original=titulo_parte,

            fecha_grabacion=inicio_iso,

            estado="PENDIENTE",

            ruta_archivo="",

            url_hotmart=url_hotmart,

        )

        database.ejecutar_query(

            "UPDATE clases_grabadas SET duracion_min = ?, analisis_json = ? WHERE id_clase = ?",

            (duracion_min, analisis_json, id_parte),

        )

        print(f"✅ Agendada: {titulo_parte} para las {hora_inicio.strftime('%H:%M')} ({duracion_min} min).")

        if not es_multi or input("\n¿Deseas agendar OTRA parte para otro horario? (S/N):\n> ").strip().lower() != "s":

            break

def opcion_programar_mentoria(tz_local: Any, cfg: Dict[str, Any]):

    print("\n--- 2. PROGRAMAR O INICIAR MENTORÍA (ZOOM / VOZ TELEGRAM) ---")

    tema = input("Escribe el tema de la Mentoría:\n> ").strip() or "Mentoría Estratégica"

    enlace = input("Pega el link de Zoom (o deja vacío si es llamada de voz de Telegram):\n> ").strip() or "chat_voz_telegram"

    hora_inicio = pedir_horario("¿A qué hora inicia? (Escribe 'ahora' o '20:00'):\n> ", tz_local)

    id_clase = f"mentoria_{int(datetime.datetime.now().timestamp())}"

    inicio_iso = hora_inicio.strftime("%Y-%m-%dT%H:%M:%S-04:00")

    fin_iso = (hora_inicio + datetime.timedelta(minutes=180)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

    database.guardar_o_actualizar_clase(id_clase, f"Mentoría: {tema}", inicio_iso, "PENDIENTE", "", enlace)

    database.ejecutar_query("UPDATE clases_grabadas SET duracion_min = 180, transversal = 'Mentorías' WHERE id_clase = ?", (id_clase,))

    calendar_sync.actualizar_estado_evento(id_clase, f"Mentoría: {tema}", "⏳ [Agendada]", inicio_iso, fin_iso, cfg)

    print("\n✅ ¡Mentoría agendada! Entrará como 'David Herbas' con micrófono y cámara apagados.")

def opcion_detener_grabacion_ahora():

    with open(ARCHIVO_FRENO_MANUAL, "w", encoding="utf-8") as f:

        f.write("STOP")

    print("\n🛑 ¡Señal de parada enviada! El grabador cerrará el video actual limpiamente.")

def opcion_cancelar_grabacion_o_pausar_vigia(tz_local: Any):

    print("\n" + "=" * 78)

    print("   🛑 CANCELAR GRABACIÓN O PAUSAR VIGÍA (HOT-CANCEL EN TIEMPO REAL)")

    print("=" * 78)

    pausado, limite_pausa = database.obtener_estado_pausa_vigia()

    if pausado:

        print(f"Estado del Vigía de Telegram: ⏸️ SILENCIADO / PAUSADO hasta: {limite_pausa}")

    else:

        print("Estado del Vigía de Telegram: 🟢 ACTIVO (Escuchando Zoom y Voice Chats)")

    print("-" * 78)

    print("  1. Cancelar una Clase o Mentoría agendada (Estado PENDIENTE)")

    print("  2. Pausar / Silenciar al Vigía de Telegram por hoy (Hasta las 23:59:59)")

    if pausado:

        print("  3. ▶️ Reanudar Vigía de Telegram AHORA (Quitar pausa)")

        print("  4. Volver al Menú Principal")

        max_sub = 4

    else:

        print("  3. Volver al Menú Principal")

        max_sub = 3

    print("-" * 78)

    sub_op = pedir_entero(f"Selecciona una opción (1-{max_sub}):\n> ", 1, max_sub)

    if sub_op == 1:

        print("\n--- CLASES Y MENTORÍAS ACTIVAS / PENDIENTES ---")

        pendientes = database.listar_clases(estado="PENDIENTE")

        grabando = database.listar_clases(estado="GRABANDO")

        todas_activas = grabando + pendientes

        if not todas_activas:

            print("[i] No hay clases ni mentorías pendientes ni en grabación en la base de datos.")

            return

        print(f"Se encontraron {len(todas_activas)} elemento(s) activo(s):")

        for idx, c in enumerate(todas_activas, 1):

            est = c.get("estado", "")

            badge = "🔴 [GRABANDO AHORA]" if est == "GRABANDO" else "⏳ [PENDIENTE]"

            print(f"  {idx}. {badge} ID: {c.get('id_clase')} | Título: {c.get('titulo_original')} | Horario: {c.get('fecha_grabacion')}")

        print("\nIngresa el NÚMERO de la lista (ej: 1) o escribe el ID de la clase.")

        print("(O presiona ENTER para regresar sin cancelar nada):")

        entrada = input("> ").strip()

        if not entrada:

            print("[i] Operación cancelada. No se modificó ninguna clase.")

            return

        clase_a_cancelar = None

        if entrada.isdigit() and 1 <= int(entrada) <= len(todas_activas):

            clase_a_cancelar = todas_activas[int(entrada) - 1]

        else:

            for c in todas_activas:

                if c.get("id_clase") == entrada:

                    clase_a_cancelar = c

                    break

        if not clase_a_cancelar:

            print(f"[!] No se encontró ninguna clase activa con el identificador '{entrada}'.")

            return

        id_sel = clase_a_cancelar["id_clase"]

        tit_sel = clase_a_cancelar["titulo_original"]

        est_sel = clase_a_cancelar.get("estado")

        confirmar = input(f"\n¿Confirmas que deseas CANCELAR '{tit_sel}' (ID: {id_sel})? (S/N):\n> ").strip().lower()

        if confirmar == "s":

            database.cancelar_clase_manualmente(id_sel)

            if est_sel == "GRABANDO":

                with open(ARCHIVO_FRENO_MANUAL, "w", encoding="utf-8") as f:

                    f.write("STOP")

                print("🛑 Señal de freno enviada al grabador en vivo.")

            print(f"\n✅ ¡Clase '{tit_sel}' cancelada con éxito!")

            print(f"Estado en BD cambiado a: 'CANCELADO_MANUALMENTE'.")

            print("El orquestador en ejecución (main.py) descartará la tarea en tiempo real sin necesidad de reiniciar.")

        else:

            print("[i] Cancelación abortada por el usuario.")

    elif sub_op == 2:

        ahora = datetime.datetime.now(tz_local)

        fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

        hasta_str = fin_dia.strftime("%Y-%m-%d %H:%M:%S")

        database.pausar_vigia_telegram(hasta_dt_str=hasta_str, motivo="Pausa manual del usuario (asistirá desde otra laptop)")

        print(f"\n⏸️ ¡VIGÍA DE TELEGRAM SILENCIADO CON ÉXITO!")

        print(f"El Vigía ignorará links de Zoom, llamadas de voz y mensajes hasta: {hasta_str}.")

        print("Ahora puedes entrar libremente a tus reuniones desde tu otra laptop sin que el bot interfiera.")

    elif sub_op == 3 and pausado:

        database.reanudar_vigia_telegram()

        print("\n▶️ ¡VIGÍA DE TELEGRAM REANUDADO!")

        print("El Vigía ha salido del modo pausa y volverá a escuchar eventos en tiempo real.")

    else:

        return

def opcion_gestor_almacenamiento_y_borrado():

    print("\n" + "=" * 78)

    print("   💾 5. GESTOR DE ALMACENAMIENTO Y RETENCIÓN DE DATOS (NUBE DEFINITIVA)")

    print("=" * 78)

    print("  A. 🧹 Borrar SOLO videos locales pesados (Conservar en App Web y Telegram)")

    print("  B. 👁️ Eliminar clase de la App Web (Ocultar / Mostrar temporalmente)")

    print("  C. 💥 Eliminación Nuclear de una Clase (Borrado Físico + BD + GitHub Pages)")

    print("  D. Volver al Menú Principal")

    print("-" * 78)

    sub_op = input("Selecciona una opción (A, B, C, D):\n> ").strip().upper()

    if sub_op == "A":

        print("\n--- A. BORRAR SOLO VIDEOS LOCALES PESADOS (.mp4, .m4a, .webm) ---")

        print("Esta acción escaneará el disco y eliminará los archivos de video y audio pesados,")

        print("conservando las Fichas Didácticas, Análisis, y los enlaces directos a Telegram.")

        confirmar = input("\n¿Deseas proceder con la purga masiva de videos locales? (S/N):\n> ").strip().lower()

        if confirmar == "s":

            print("\n🧹 Escaneando y purgando archivos multimedia...")

            borrados, bytes_lib = database.purgar_todos_los_videos_locales()

            mb_lib = round(bytes_lib / (1024 * 1024), 2)

            gb_lib = round(bytes_lib / (1024 * 1024 * 1024), 2)

            print("=" * 78)

            print(f"✅ ¡PURGA FINALIZADA CON ÉXITO!")

            print(f"📦 Archivos pesados eliminados: {borrados}")

            print(f"💾 Espacio en disco recuperado: {mb_lib} MB ({gb_lib} GB)")

            print(f"☁️ Tus clases y mentorías siguen 100% disponibles en la App Web y Telegram.")

            print("=" * 78)

        else:

            print("[i] Operación cancelada. No se borró ningún archivo.")

    elif sub_op == "B":

        print("\n--- B. ELIMINAR CLASE DE LA APP WEB (OCULTAR / VISIBILIDAD) ---")

        clases = database.listar_clases()

        if not clases:

            print("[!] No hay clases registradas en la base de datos.")

            return

        print("Clases y mentorías en la base de datos:")

        for idx, c in enumerate(clases, 1):

            est = c.get("estado", "")

            vis_badge = "🟢 [VISIBLE EN WEB]" if est == "COMPLETADA" else f"⚪ [{est}]"

            print(f"  {idx}. {vis_badge} ID: {c.get('id_clase')} | {c.get('titulo_original')}")

        print("\nIngresa el NÚMERO de la lista (ej: 1) o escribe el ID de la clase:")

        entrada = input("> ").strip()

        if not entrada:

            return

        clase_sel = None

        if entrada.isdigit() and 1 <= int(entrada) <= len(clases):

            clase_sel = clases[int(entrada) - 1]

        else:

            for c in clases:

                if c.get("id_clase") == entrada:

                    clase_sel = c

                    break

        if not clase_sel:

            print(f"[!] No se encontró la clase '{entrada}'.")

            return

        id_sel = clase_sel["id_clase"]

        tit_sel = clase_sel["titulo_original"]

        est_actual = clase_sel.get("estado")

        if est_actual == "OCULTA":

            acc = input(f"\nLa clase '{tit_sel}' está actualmente OCULTA. ¿Deseas MOSTRARLA en la web? (S/N):\n> ").strip().lower()

            if acc == "s":

                database.cambiar_visibilidad_web_clase(id_sel, ocultar=False)

                print(f"✅ Clase '{tit_sel}' restaurada a COMPLETADA.")

                print("🌐 Reconstruyendo y publicando App Web en GitHub Pages...")

                route_builder.generar_tablero_rutas(auto_deploy=True)

                print("✅ App Web actualizada: La clase vuelve a ser visible.")

        else:

            acc = input(f"\n¿Deseas OCULTAR '{tit_sel}' de la App Web (sin borrar archivos ni Telegram)? (S/N):\n> ").strip().lower()

            if acc == "s":

                database.cambiar_visibilidad_web_clase(id_sel, ocultar=True)

                print(f"✅ Clase '{tit_sel}' cambiada a estado 'OCULTA'.")

                print("🌐 Reconstruyendo y publicando App Web en GitHub Pages...")

                route_builder.generar_tablero_rutas(auto_deploy=True)

                print("✅ App Web actualizada: La clase ya no se renderiza en la web.")

                print("ℹ️ Los archivos locales y el chat de Telegram permanecen intactos.")

    elif sub_op == "C":

        print("\n" + "!" * 78)

        print("   💥 C. ELIMINACIÓN NUCLEAR DE UNA CLASE")

        print("!" * 78)

        id_entrada = input("Escribe el ID de la clase que deseas destruir completamente:\n> ").strip()

        if not id_entrada:

            return

        clase = database.obtener_clase(id_entrada)

        if not clase:

            todas = database.listar_clases()

            coincidencias = [c for c in todas if id_entrada.lower() in c.get("id_clase", "").lower() or id_entrada.lower() in c.get("titulo_original", "").lower()]

            if len(coincidencias) == 1:

                clase = coincidencias[0]

                id_entrada = clase["id_clase"]

            elif len(coincidencias) > 1:

                print("Se encontraron varias coincidencias:")

                for idx, c in enumerate(coincidencias, 1):

                    print(f"  {idx}. ID: {c.get('id_clase')} | {c.get('titulo_original')}")

                sel = pedir_entero("Selecciona el número a destruir:\n> ", 1, len(coincidencias))

                clase = coincidencias[sel - 1]

                id_entrada = clase["id_clase"]

            else:

                print(f"[!] No se encontró ninguna clase con el ID o texto '{id_entrada}'.")

                return

        tit = clase.get("titulo_original", id_entrada)

        print("\n" + "⚠️ " * 15)

        print(f"ADVERTENCIA CRÍTICA: Se destruirá la clase '{tit}' (ID: {id_entrada}).")

        print("Esta acción es IRREVERSIBLE: Eliminará la carpeta física del disco y el registro en la BD.")

        conf1 = input("¿Confirmas la primera verificación? (Escribe 'SI' en mayúsculas):\n> ").strip()

        if conf1 != "SI":

            print("[i] Operación abortada en confirmación 1.")

            return

        print("\n🚨 CONFIRMACIÓN FINAL:")

        print("Se ejecutará la aniquilación física total y se sincronizará la App Web limpia.")

        conf2 = input("Escribe 'ELIMINAR' para proceder con la destrucción:\n> ").strip()

        if conf2 != "ELIMINAR":

            print("[i] Operación abortada en confirmación 2.")

            return

        print("\n💥 Ejecutando aniquilación física y purga de base de datos...")

        database.eliminar_clase(id_entrada)

        print("🌐 Reconstruyendo App Web limpia y publicando en GitHub Pages...")

        route_builder.generar_tablero_rutas(auto_deploy=True)

        print("\n" + "=" * 78)

        print("💥 ¡ANIQUILACIÓN NUCLEAR COMPLETADA!")

        print(" - Carpeta física y archivos locales borrados por completo.")

        print(" - Registro eliminado de la Base de Datos SQLite.")

        print(" - App Web reconstruida limpia y subida a GitHub Pages.")

        print("=" * 78)

        print("⚠️ NOTA IMPORTANTE:")

        print("Por favor borra manualmente el post en Telegram y el source en NotebookLM.")

        print("=" * 78)

    else:

        return

def opcion_modificar_mentor_efecto_domino():

    print("\n--- 6. MODIFICAR NOMBRE DE MENTOR (EFECTO DOMINÓ) ---")

    clases = database.listar_clases()

    clases.reverse()

    clases = clases[:25]

    if not clases:

        print("[!] Aún no hay clases registradas.")

        return

    for idx, c in enumerate(clases, 1):

        print(f"  {idx}. [{c.get('estado')}] {c.get('titulo_original')} (ID: {c.get('id_clase')})")

    sel = pedir_entero("\nElige el número de la clase/mentoría:\n> ", 1, len(clases))

    elegida = clases[sel - 1]

    nuevo_mentor = input("Escribe el NOMBRE REAL del Mentor:\n> ").strip()

    if not nuevo_mentor:

        return

    titulo_actual = elegida.get("titulo_original", "Mentoría")

    titulo_limpio = re.sub(r"\s*\(Mentor:.*?\)", "", titulo_actual, flags=re.IGNORECASE).strip()

    nuevo_titulo = f"{titulo_limpio} (Mentor: {nuevo_mentor})"

    ruta_actual = elegida.get("ruta_archivo") or ""

    nueva_ruta = ruta_actual

    if ruta_actual and os.path.exists(ruta_actual):

        try:

            carpeta = os.path.dirname(ruta_actual)

            slug = normalizar_id(nuevo_mentor)

            base_limpia = re.sub(r"_mentor_[a-z0-9_]+", "", os.path.splitext(os.path.basename(ruta_actual))[0])

            nueva_ruta = os.path.join(carpeta, f"{base_limpia}_mentor_{slug}.mp4")

            if nueva_ruta != ruta_actual:

                os.replace(ruta_actual, nueva_ruta)

                print(f"✅ 1/4 Archivo MP4 renombrado: {os.path.basename(nueva_ruta)}")

        except Exception:

            pass

    analisis = {}

    if elegida.get("analisis_json"):

        try:

            analisis = json.loads(elegida["analisis_json"])

        except Exception:

            analisis = {}

    analisis["mentor_identificado"] = nuevo_mentor

    database.ejecutar_query(

        "UPDATE clases_grabadas SET titulo_original = ?, ruta_archivo = ?, analisis_json = ?, mentor = ? WHERE id_clase = ?",

        (nuevo_titulo, nueva_ruta, json.dumps(analisis, ensure_ascii=False), nuevo_mentor, elegida["id_clase"]),

    )

    print(f"✅ 2/4 Base de datos actualizada con: '{nuevo_titulo}'.")

    tg_url = elegida.get("telegram_url") or ""

    if tg_url:

        asyncio.run(

            telegram_uploader.editar_caption_en_telegram(

                telegram_url=tg_url,

                nuevo_titulo=nuevo_titulo,

                fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),

                duracion_min=int(elegida.get("duracion_min") or 60),

                analisis=analisis,

            )

        )

        print("✅ 3/4 Mensaje editado en tu canal de Telegram.")

    route_builder.generar_tablero_rutas(auto_deploy=True)

    print("✅ 4/4 ¡App Web actualizada y subida a GitHub Pages!")

def opcion_gestionar_grupos_mentores():

    print("\n" + "=" * 78)

    print("--- 7. GESTIONAR MENTORES Y CANALES/GRUPOS DE TELEGRAM (VIGÍA) ---")

    print("=" * 78)

    actuales = database.listar_mentores_grupos()

    mentores = [m for m in actuales if m.get("tipo_grupo", "MENTOR") != "GENERAL" and m.get("nombre_mentor", "").lower() not in ("general", "sin mentor", "canal general")]

    generales = [m for m in actuales if m.get("tipo_grupo", "MENTOR") == "GENERAL" or m.get("nombre_mentor", "").lower() in ("general", "sin mentor", "canal general")]

    if mentores:

        print("\n🎙️ MENTORES REGISTRADOS:")

        for idx, m in enumerate(mentores, 1):

            print(f"  [{idx}] 🎙️ {m['nombre_mentor']} | Palabra/ID: '{m['palabra_clave_grupo']}' | Especialidad: {m['especialidad']}")

    else:

        print("\n🎙️ MENTORES: Ninguno registrado.")

    if generales:

        print("\n🌐 GRUPOS / CANALES GENERALES (Sin mentor asociado):")

        for idx, g in enumerate(generales, 1):

            nom_g = g.get("nombre_mentor") if g.get("nombre_mentor") not in ("General", "Sin Mentor", "Canal General") else g.get("especialidad", "Canal General")

            print(f"  [{idx}] 🌐 {nom_g} | Palabra/ID: '{g['palabra_clave_grupo']}' | Área: {g['especialidad']}")

    else:

        print("\n🌐 GRUPOS / CANALES GENERALES: Ninguno registrado.")

    print("\n" + "-" * 60)

    print("Opciones de Gestión:")

    print("  1. Añadir nuevo Mentor y su grupo de Telegram")

    print("  2. Añadir nuevo Grupo/Canal General (sin mentor asociado)")

    print("  3. Desactivar / Eliminar un grupo o mentor del Vigía")

    print("  4. Volver al menú principal")

    print("-" * 60)

    sub = input("👉 Elige una opción (1-4):\n> ").strip()

    if sub == "1":

        nombre = input("Nombre del Mentor (ej. Vinicius Loureiro, Kike Cadena):\n> ").strip()

        palabra = input("Palabra clave única del nombre de su grupo de Telegram:\n> ").strip()

        esp = input("Especialidad o área (ej. Tráfico, Ventas, IA):\n> ").strip() or "General"

        if nombre and palabra:

            database.agregar_o_actualizar_mentor_grupo(nombre, palabra, esp, tipo_grupo="MENTOR")

            print(f"✅ Mentor '{nombre}' vinculado al grupo '{palabra}'. El Vigía capturará sus Tips, Cápsulas y Noticias.")

            route_builder.generar_tablero_rutas(auto_deploy=True)

    elif sub == "2":

        nombre = input("Nombre o descripción del Canal/Grupo General (ej. Comunidad Tráfico, Avisos UO):\n> ").strip()

        palabra = input("Palabra clave única, ID (-100...) o username del canal de Telegram:\n> ").strip()

        esp = input("Área o temática (ej. Tráfico, Copywriting, General):\n> ").strip() or "General"

        if palabra:

            nom_final = nombre or "Canal General"

            database.agregar_grupo_general(nom_final, palabra, esp)

            print(f"✅ Canal General '{nom_final}' vinculado al Vigía ({palabra}).")

            print("   El Vigía realizará barridos históricos, analizará audios/PDFs y subirá su contenido a la App Web.")

            route_builder.generar_tablero_rutas(auto_deploy=True)

    elif sub == "3":

        id_pal = input("Escribe la palabra clave, ID o nombre exacto a desactivar:\n> ").strip()

        if id_pal:

            if database.desactivar_grupo_vigilado(id_pal):

                print(f"✅ Grupo o canal '{id_pal}' desactivado del Vigía.")

                route_builder.generar_tablero_rutas(auto_deploy=True)

            else:

                print(f"[!] No se encontró ningún registro activo con '{id_pal}'.")

def opcion_auditar_y_rescatar_procesos():

    print("\n" + "=" * 78)

    print("   🔍 8. AUDITORÍA Y RESCATE DE PROCESOS INCOMPLETOS")

    print("=" * 78)

    print("Escaneando base de datos y carpetas en busca de tareas pendientes...")

    # 1. Videos grabados pero NO subidos a Telegram

    clases = database.listar_clases()

    pendientes_telegram = []

    for c in clases:

        ruta = c.get("ruta_archivo") or ""

        tg_url = c.get("telegram_app_url") or c.get("telegram_url") or ""

        if ruta and os.path.exists(ruta) and not tg_url:

            peso_mb = round(os.path.getsize(ruta) / (1024 * 1024), 1)

            pendientes_telegram.append({

                "clase": c,

                "ruta": ruta,

                "peso_mb": peso_mb,

            })

    # También buscar videos huérfanos en grabaciones que no estén subidos

    dir_grab = os.path.join(BASE_DIR, "grabaciones")

    if os.path.exists(dir_grab):

        import glob

        todos_mp4 = glob.glob(os.path.join(dir_grab, "**", "*.mp4"), recursive=True)

        rutas_en_bd = {c.get("ruta_archivo") for c in clases if c.get("ruta_archivo")}

        for f in todos_mp4:

            if f not in rutas_en_bd and os.path.getsize(f) > 2 * 1024 * 1024 and "temp" not in f.lower():

                nom = os.path.splitext(os.path.basename(f))[0]

                peso_mb = round(os.path.getsize(f) / (1024 * 1024), 1)

                pendientes_telegram.append({

                    "clase": {

                        "id_clase": database.normalizar_id(nom),

                        "titulo_original": nom.replace("_", " "),

                        "fecha_grabacion": datetime.datetime.now().isoformat(),

                        "duracion_min": 60,

                        "transversal": "General",

                    },

                    "ruta": f,

                    "peso_mb": peso_mb,

                })

    # 2. Clases completadas listas para la App Web (GitHub Pages)

    clases_web = [c for c in clases if c.get("estado") == "COMPLETADA" and "prueba" not in c.get("id_clase", "").lower()]

    total_clases_bd = len(clases_web)

    # 3. Errores o tareas de NotebookLM a medias

    pendientes_nlm = database.obtener_reintentos_notebooklm_listos()

    if not pendientes_nlm:

        try:

            conn = database.get_connection()

            cur = conn.cursor()

            cur.execute("SELECT * FROM notebooklm_cola_reintentos WHERE estado = 'PENDIENTE'")

            pendientes_nlm = [dict(r) for r in cur.fetchall()]

            conn.close()

        except Exception:

            pendientes_nlm = []

    # REPORTE EN PANTALLA

    print("\n📊 REPORTE DE AUDITORÍA:")

    print("-" * 78)

    print(f"a) Videos locales pendientes de subir a Telegram: {len(pendientes_telegram)}")

    for idx, p in enumerate(pendientes_telegram[:5], 1):

        print(f"   [{idx}] {p['clase']['titulo_original']} ({p['peso_mb']} MB) -> {os.path.basename(p['ruta'])}")

    if len(pendientes_telegram) > 5:

        print(f"   ... y {len(pendientes_telegram) - 5} videos más.")

    print(f"\nb) Clases listas para la App Web (GitHub Pages): {total_clases_bd} activas")

    print(f"\nc) Tareas de NotebookLM pendientes en cola: {len(pendientes_nlm)}")

    for idx, n in enumerate(pendientes_nlm[:3], 1):

        print(f"   [{idx}] {n.get('titulo', 'Tarea')} (Intentos: {n.get('intentos', 0)})")

    print("-" * 78)

    hay_trabajo = len(pendientes_telegram) > 0 or len(pendientes_nlm) > 0

    if not hay_trabajo:

        print("✅ ¡Todo está al día! No se encontraron procesos incompletos ni videos pendientes.")

        if input("\n¿Deseas forzar la regeneración y subida de la App Web a GitHub Pages de todos modos? (S/N):\n> ").strip().lower() == "s":

            route_builder.generar_tablero_rutas(auto_deploy=True)

            print("✅ App Web actualizada.")

        return

    resp = input("\n¿Deseas reanudar y completar estos procesos ahora? (S/N):\n> ").strip().lower()

    if resp != "s":

        print("Operación cancelada por el usuario.")

        return

    # EJECUTAR RESCATE

    print("\n🚀 INICIANDO RESCATE AUTOMÁTICO DE PROCESOS...")

    # 1. Reintentar NotebookLM

    if pendientes_nlm:

        print(f"\n🧠 [1/3] Procesando {len(pendientes_nlm)} tareas pendientes de NotebookLM...")

        import notebooklm_bot

        for n in pendientes_nlm:

            try:

                print(f"   -> Reanudando NotebookLM para '{n.get('titulo')}'...")

                asyncio.run(notebooklm_bot.reintentar_tarea_encolada(n))

            except Exception as e_nlm:

                print(f"   [!] Error en NotebookLM: {e_nlm}")

    # 2. Subir videos a Telegram

    if pendientes_telegram:

        print(f"\n📤 [2/3] Subiendo {len(pendientes_telegram)} videos pendientes a Telegram...")

        import telegram_uploader

        for p in pendientes_telegram:

            c = p["clase"]

            ruta_v = p["ruta"]

            tit = c["titulo_original"]

            id_c = c.get("id_clase") or database.normalizar_id(tit)

            dur = int(c.get("duracion_min") or 60)

            fecha_clase = datetime.date.today().strftime("%d/%m/%Y")

            analisis = {}

            if c.get("analisis_json"):

                try:

                    analisis = json.loads(c["analisis_json"])

                except Exception:

                    pass

            if not analisis:

                analisis = {"transversal": c.get("transversal") or "General", "nivel": 1, "resumen_didactico": tit}

            print(f"   -> Subiendo a Telegram: '{tit}' ({p['peso_mb']} MB)...")

            try:

                res_tg = asyncio.run(

                    telegram_uploader.subir_entrega_completa_telegram(

                        ruta_video=ruta_v,

                        titulo_clase=tit,

                        fecha_clase=fecha_clase,

                        duracion_min=dur,

                        analisis=analisis,

                    )

                )

                tg_url = res_tg.get("telegram_url") if isinstance(res_tg, dict) else ""

                tg_app = res_tg.get("telegram_app_url") if isinstance(res_tg, dict) else ""

                tg_web = res_tg.get("telegram_web_url") if isinstance(res_tg, dict) else ""

                database.guardar_o_actualizar_clase(

                    id_clase=id_c,

                    titulo_original=tit,

                    fecha_grabacion=c.get("fecha_grabacion") or datetime.datetime.now().isoformat(),

                    estado="COMPLETADA",

                    ruta_archivo=ruta_v,

                    telegram_url=tg_url,

                    telegram_app_url=tg_app,

                    telegram_web_url=tg_web,

                )

                print(f"   ✅ '{tit}' subido a Telegram y registrado como COMPLETADA.")

            except Exception as e_tg:

                print(f"   [!] Error subiendo '{tit}': {e_tg}")

    # 3. Regenerar y publicar App Web en GitHub Pages

    print("\n🌐 [3/3] Sincronizando y publicando App Web actualizada en GitHub Pages...")

    try:

        route_builder.generar_tablero_rutas(auto_deploy=True)

        print("✅ App Web actualizada y publicada con éxito en GitHub Pages.")

    except Exception as e_web:

        print(f"[!] Error publicando App Web: {e_web}")

    print("\n🎉 ¡RESCATE Y AUDITORÍA FINALIZADOS CON ÉXITO!")

def opcion_rescatar_y_publicar_web():

    print("\n--- 9. RESCATAR GRABACIONES LOCALES Y ACTUALIZAR APP WEB EN GITHUB PAGES ---")

    route_builder.generar_tablero_rutas(auto_deploy=True)

    print("\n✅ ¡Proceso finalizado! Recarga la página de tu App Web en el celular o laptop.")

def asegurar_carpetas_ingesta():

    carpetas = {

        "masterclasses": os.path.join(BASE_DIR, "Ingesta_Manual", "Masterclasses"),

        "mentorias": os.path.join(BASE_DIR, "Ingesta_Manual", "Mentorias"),

        "independientes": os.path.join(BASE_DIR, "Ingesta_Manual", "Grabaciones_Independientes"),

        "playbooks": os.path.join(BASE_DIR, "Playbooks_Externos"),

    }

    for c in carpetas.values():

        os.makedirs(c, exist_ok=True)

    return carpetas

def mostrar_dashboard_operativo():

    res = database.obtener_resumen_dashboard()

    clases = res.get("clases", [])

    print("\n" + "=" * 110)

    print("                      📊 DASHBOARD OPERATIVO Y MEMORIA VIVA - UNIVERSIDAD ONLINE")

    print("=" * 110)

    print(f"  📚 Total Clases: {res['total_clases']}  |  ✅ Completadas: {res['completadas']}  |  ⏳ Pendientes: {res['pendientes']}  |  🔴 Grabando: {res['grabando']}")

    print(f"  ☁️ En Telegram: {res['con_telegram']}  |  🎧 Con Audio/Podcast: {res['con_audio']}  |  💡 Cápsulas Mentores: {res['total_capsulas']}  |  🎙️ Mentores: {res['total_mentores']}")

    print("-" * 110)

    print(f"{'#':<3} | {'ID Clase':<24} | {'Título':<34} | {'Estado':<12} | {'Telegram':<10} | {'Audio NLM':<10}")

    print("-" * 110)

    for i, c in enumerate(clases[:18], 1):

        cid = (c.get("id_clase") or "")[:23]

        tit = (c.get("titulo_original") or "")[:32]

        est = (c.get("estado") or "")[:11]

        tg = "✅ Nube" if bool(c.get("telegram_url") or c.get("telegram_app_url") or c.get("telegram_web_url")) else "⏳ Pend."

        nlm = "🎧 Sí" if bool(c.get("podcast_archivo") or (c.get("notebook_url") and c.get("notebook_url") != "https://notebooklm.google.com/")) else "⏳ Pend."

        print(f"{i:<3} | {cid:<24} | {tit:<34} | {est:<12} | {tg:<10} | {nlm:<10}")

    if len(clases) > 18:

        print(f"... y {len(clases) - 18} clases adicionales registradas en la biblioteca.")

    print("=" * 110)

def opcion_gestion_individual_clase():

    print("\n--- 2. GESTIÓN INDIVIDUAL DE CLASE / MENTORÍA ---")

    clases = database.listar_clases()

    if not clases:

        print("[!] No hay clases registradas en la base de datos.")

        return

    print("\nÚltimas clases registradas:")

    for i, c in enumerate(clases[:20], 1):

        print(f"  {i}. [{c.get('id_clase')}] {c.get('titulo_original')} (Estado: {c.get('estado')})")

    entrada = input("\nIngresa el NÚMERO o ID exacto de la clase a gestionar (o 'cancelar'):\n> ").strip()

    if entrada.lower() in ("cancelar", "salir", ""):

        return

    clase_sel = None

    if entrada.isdigit():

        idx = int(entrada)

        if 1 <= idx <= len(clases):

            clase_sel = clases[idx - 1]

    if not clase_sel:

        for c in clases:

            if c.get("id_clase") == entrada or c.get("id_clase") == normalizar_id(entrada):

                clase_sel = c

                break

    if not clase_sel:

        print(f"[!] No se encontró ninguna clase con el identificador '{entrada}'.")

        return

    id_c = clase_sel["id_clase"]

    tit = clase_sel["titulo_original"]

    print("\n" + "=" * 70)

    print(f"🎯 GESTIONANDO: [{id_c}] {tit}")

    print(f"   Estado actual: {clase_sel.get('estado')} | Mentor: {clase_sel.get('mentor') or 'General'}")

    print(f"   Telegram URL: {clase_sel.get('telegram_url') or 'No asignada'}")

    print(f"   NotebookLM URL: {clase_sel.get('notebook_url') or 'No asignada'}")

    print(f"   Archivo local: {clase_sel.get('ruta_archivo') or 'Ninguno'}")

    print("=" * 70)

    print("  1. Cambiar estado manualmente (PENDIENTE, COMPLETADA, OCULTA, etc.)")

    print("  2. Forzar subida a Telegram ahora")

    print("  3. Forzar procesamiento en NotebookLM")

    print("  4. 🛡️ Borrado Seguro (Safe-Purge: libera GB locales, mantiene en Nube y Web)")

    print("  5. Volver")

    sub_op = pedir_entero("\nSelecciona una acción (1-5):\n> ", 1, 5)

    if sub_op == 1:

        print("\nEstados válidos: PENDIENTE, GRABANDO, COMPLETADA, OCULTA, CANCELADO_MANUALMENTE, ERROR_REMUXING")

        nuevo_est = input("Escribe el nuevo estado:\n> ").strip().upper()

        if nuevo_est in ("PENDIENTE", "GRABANDO", "COMPLETADA", "OCULTA", "CANCELADO_MANUALMENTE", "ERROR_REMUXING"):

            if nuevo_est == "PENDIENTE" and (clase_sel.get("estado") == "COMPLETADA" or clase_sel.get("ruta_archivo")):

                database.marcar_regrabacion_segura(id_c)

                print(f"🛡️ [Safe Overwrite] Re-grabación diferida activada para '{tit}'.")

                print("   Los archivos locales y la ficha en la App Web permanecen intactos hasta que la nueva grabación termine con éxito.")

            else:

                database.ejecutar_query("UPDATE clases_grabadas SET estado = ?, updated_at = CURRENT_TIMESTAMP WHERE id_clase = ?", (nuevo_est, id_c))

                print(f"✅ Estado de '{tit}' actualizado a: {nuevo_est}")

            route_builder.generar_tablero_rutas(auto_deploy=True)

        else:

            print("[!] Estado inválido.")

    elif sub_op == 2:

        ruta_v = clase_sel.get("ruta_archivo")

        if not ruta_v or not os.path.exists(ruta_v):

            print(f"[!] No existe archivo local para subir ({ruta_v}).")

            return

        print(f"🚀 Subiendo '{tit}' a Telegram...")

        try:

            res_tg = asyncio.run(telegram_uploader.subir_entrega_completa_telegram(

                ruta_video=ruta_v,

                titulo_clase=tit,

                fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),

                duracion_min=int(clase_sel.get("duracion_min") or 60),

            ))

            tg_url = res_tg.get("telegram_url") if isinstance(res_tg, dict) else ""

            if tg_url:

                database.guardar_o_actualizar_clase(id_clase=id_c, titulo_original=tit, estado="COMPLETADA", telegram_url=tg_url)

                print(f"✅ ¡Clase subida a Telegram con éxito! URL: {tg_url}")

                route_builder.generar_tablero_rutas(auto_deploy=True)

        except Exception as e_tg:

            print(f"[!] Error subiendo a Telegram: {e_tg}")

    elif sub_op == 3:

        print(f"🧠 Enviando '{tit}' a NotebookLM...")

        try:

            analisis = json.loads(clase_sel["analisis_json"]) if clase_sel.get("analisis_json") else {}

            res_nlm = asyncio.run(notebooklm_bot.procesar_clase_en_notebooklm(clase_sel, analisis, clase_sel.get("ruta_archivo")))

            if isinstance(res_nlm, dict) and res_nlm.get("notebook_url"):

                print(f"✅ NotebookLM completado: {res_nlm.get('notebook_url')}")

                route_builder.generar_tablero_rutas(auto_deploy=True)

        except Exception as e_nlm:

            print(f"[!] Error en NotebookLM: {e_nlm}")

    elif sub_op == 4:

        print(f"\n🛡️ Ejecutando Borrado Seguro para '{tit}'...")

        res_purge = database.borrado_seguro_clase(id_c)

        if res_purge.get("ok"):

            print(f"✅ {res_purge.get('mensaje')}")

            print(f"Archivos eliminados del disco: {res_purge.get('archivos_borrados')}")

            route_builder.generar_tablero_rutas(auto_deploy=True)

        else:

            print(f"[!] {res_purge.get('mensaje')}")

def opcion_ingesta_manual_y_playbooks():

    print("\n--- 3. INGESTA MANUAL DE CLASES Y PLAYBOOKS EXTERNOS ---")

    carpetas = asegurar_carpetas_ingesta()

    print("Las siguientes carpetas de ingesta están listas en tu disco duro:")

    print(f"  📁 1. Masterclasses: {carpetas['masterclasses']}")

    print(f"  📁 2. Mentorías: {carpetas['mentorias']}")

    print(f"  📁 3. Grabaciones Independientes: {carpetas['independientes']}")

    print(f"  📁 4. Playbooks Externos: {carpetas['playbooks']}")

    print("\n💡 Puedes copiar/pegar videos (.mp4), audios (.mp3, .m4a) o playbooks (.pdf, .md) en esas carpetas.")

    if input("\n¿Deseas escanear y procesar automáticamente los archivos nuevos ahora? (S/N):\n> ").strip().lower() != "s":

        return

    print("\n🔍 Escaneando carpetas de Ingesta Manual...")

    cfg = cargar_config()

    tz_local = pytz.timezone(cfg.get("timezone_local", "America/La_Paz"))

    conn = database.get_connection()

    procesados = 0

    try:

        cur = conn.cursor()

        cur.execute("SELECT ruta_archivo FROM ingesta_manual_registro")

        ya_ingestados = {r[0] for r in cur.fetchall()}

    finally:

        conn.close()

    formatos_soportados = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".m4a", ".wav", ".pdf", ".md", ".txt")

    for cat_clave, folder_path in carpetas.items():

        if not os.path.exists(folder_path):

            continue

        for root, dirs, files in os.walk(folder_path):

            for f in files:

                ext = os.path.splitext(f)[1].lower()

                if ext not in formatos_soportados:

                    continue

                ruta_completa = os.path.abspath(os.path.join(root, f))

                if ruta_completa in ya_ingestados:

                    continue

                nombre_sin_ext = os.path.splitext(f)[0].replace("_", " ").strip().title()

                ts_id = int(time.time())

                id_clase = f"ingesta_{cat_clave}_{normalizar_id(nombre_sin_ext)[:25]}_{ts_id % 10000}"

                print(f"\n🎯 [Ingesta] Nuevo archivo detectado: '{f}' en {cat_clave.upper()}")

                # Determinar categoría y transversal

                if cat_clave == "masterclasses":

                    transversal = "General"

                    mentor = "Universidad Online"

                elif cat_clave == "mentorias":

                    transversal = "Mentorías"

                    mentor = os.path.basename(root) if root != folder_path else "Mentor Invitado"

                elif cat_clave == "playbooks":

                    transversal = "Playbooks"

                    mentor = "Estrategia & Táctica"

                else:

                    transversal = "Grabación Independiente"

                    mentor = "General"

                # 1. Extraer audio si es video pesado o usar el archivo directo

                ruta_mp3 = None

                if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):

                    try:

                        ruta_mp3 = ai_analyzer.extraer_audio_ligero(ruta_completa)

                    except Exception:

                        ruta_mp3 = None

                elif ext in (".mp3", ".m4a", ".wav"):

                    ruta_mp3 = ruta_completa

                # 2. Análisis con Gemini

                print(f"   ⚙️ Analizando contenido educativo con Gemini...")

                analisis = ai_analyzer.analizar_clase_con_gemini(nombre_sin_ext, ruta_mp3)

                if not analisis:

                    analisis = {

                        "transversal": transversal,

                        "nivel": 2 if cat_clave == "playbooks" else 1,

                        "resumen_didactico": f"Documento o clase ingestada manualmente: {nombre_sin_ext}.",

                        "flashcards": [

                            {"pregunta": f"¿De qué trata este recurso ({nombre_sin_ext})?", "respuesta": f"Recurso clave de {transversal}.", "dificultad": "Básica"}

                        ]

                    }

                # 3. Generar Ficha Didáctica Markdown

                carpeta_ficha = os.path.dirname(ruta_completa)

                ruta_md = os.path.join(carpeta_ficha, f"Ficha_Didactica_{id_clase}.md")

                ai_analyzer.generar_ficha_markdown(analisis, nombre_sin_ext, datetime.date.today().strftime("%d/%m/%Y"), ruta_md)

                # 4. Procesar en NotebookLM

                print(f"   ⚙️ Vinculando con NotebookLM...")

                notebook_url = ""

                podcast_archivo = ""

                try:

                    res_nlm = asyncio.run(notebooklm_bot.procesar_clase_en_notebooklm(

                        {"id_clase": id_clase, "titulo_original": nombre_sin_ext},

                        analisis,

                        ruta_mp3,

                        ruta_md

                    ))

                    if isinstance(res_nlm, dict):

                        notebook_url = res_nlm.get("notebook_url") or ""

                        podcast_archivo = res_nlm.get("podcast_archivo") or ""

                except Exception as e_nlm:

                    print(f"   [!] Aviso en NotebookLM: {e_nlm}")

                # 5. Subir a Telegram

                tg_url = ""

                if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".m4a", ".pdf"):

                    print(f"   ⚙️ Subiendo entrega a Telegram...")

                    try:

                        res_tg = asyncio.run(telegram_uploader.subir_entrega_completa_telegram(

                            ruta_video=ruta_completa if ext in (".mp4", ".webm", ".pdf") else "",

                            titulo_clase=nombre_sin_ext,

                            fecha_clase=datetime.date.today().strftime("%d/%m/%Y"),

                            duracion_min=60,

                            analisis=analisis,

                            notebook_url=notebook_url,

                            ruta_podcast=podcast_archivo or (ruta_mp3 if ext in (".mp3", ".m4a") else ""),

                            ruta_md_guia=ruta_md,

                        ))

                        if isinstance(res_tg, dict):

                            tg_url = res_tg.get("telegram_url") or ""

                    except Exception as e_tg:

                        print(f"   [!] Aviso subiendo a Telegram: {e_tg}")

                # 6. Guardar en SQLite con "Memoria Viva"

                fecha_iso = datetime.datetime.now(tz_local).strftime("%Y-%m-%dT%H:%M:%S-04:00")

                database.guardar_o_actualizar_clase(

                    id_clase=id_clase,

                    titulo_original=nombre_sin_ext,

                    fecha_grabacion=fecha_iso,

                    estado="COMPLETADA",

                    ruta_archivo=ruta_completa,

                    url_hotmart="ingesta_manual",

                    telegram_url=tg_url,

                )

                database.guardar_analisis_clase(id_clase, analisis)

                if notebook_url:

                    database.guardar_notebook_url(id_clase, notebook_url)

                # Registrar en ingesta_manual_registro

                conn_reg = database.get_connection()

                try:

                    with conn_reg:

                        conn_reg.execute(

                            "INSERT OR IGNORE INTO ingesta_manual_registro (ruta_archivo, id_clase, carpeta_origen, fecha_ingesta) VALUES (?, ?, ?, ?)",

                            (ruta_completa, id_clase, cat_clave, fecha_iso)

                        )

                finally:

                    conn_reg.close()

                print(f"   ✅ ¡'{nombre_sin_ext}' procesado, guardado en SQLite y respaldado en la nube!")

                procesados += 1

    if procesados > 0:

        print(f"\n🎉 Ingesta completada con éxito: {procesados} archivos incorporados a la biblioteca.")

        route_builder.generar_tablero_rutas(auto_deploy=True)

    else:

        print("\n✅ No se encontraron archivos nuevos pendientes de ingesta.")

def main():

    database.init_db()

    cfg = cargar_config()

    tz_local = pytz.timezone(cfg.get("timezone_local", "America/La_Paz"))

    # Mostrar Dashboard Operativo al abrir

    mostrar_dashboard_operativo()

    while True:

        print("\n" + "=" * 80)

        print("   🎬 CENTRO DE CONTROL Y DIRECTOR DE OPERACIONES - UNIVERSIDAD ONLINE")

        print("=" * 80)

        print("  1. 📊 Ver / Refrescar Dashboard de Operaciones (Tabla de Estado)")

        print("  2. 🎯 Gestión Individual de Clase / Mentoría (Estados, NLM, Borrado Seguro)")

        print("  3. 📥 Ingesta Manual y Playbooks Externos (Escanear Carpetas Ahora)")

        print("  4. Programar Masterclass de Hotmart (Soporta Partes 1, 2, 3...)")

        print("  5. Programar o Iniciar Mentoría (Zoom / Chat de Voz Telegram)")

        print("  6. 🛑 DETENER grabación en curso ahora mismo (Corte limpio)")

        print("  7. 🛑 Cancelar Grabación o Pausar Vigía (Hot-Cancel en Tiempo Real)")

        print("  8. 💾 Gestor de Almacenamiento y Borrado (Liberar Espacio / Ocultar / Nuclear)")

        print("  9. ✏️ Modificar nombre de Mentor ('Efecto Dominó': PC + Telegram + Web)")

        print(" 10. 👥 Añadir / Gestionar Mentores y sus Grupos Privados de Telegram")

        print(" 11. 🔍 Auditar y Rescatar Procesos Incompletos (Videos, Telegram, NLM)")

        print(" 12. 🌐 Regenerar y Publicar App Web en GitHub Pages Ahora")

        print(" 13. Salir")

        print("=" * 80)

        op = pedir_entero("Selecciona una opción (1-13):\n> ", 1, 13)

        if op == 1:

            mostrar_dashboard_operativo()

        elif op == 2:

            opcion_gestion_individual_clase()

        elif op == 3:

            opcion_ingesta_manual_y_playbooks()

        elif op == 4:

            opcion_programar_hotmart(tz_local)

        elif op == 5:

            opcion_programar_mentoria(tz_local, cfg)

        elif op == 6:

            opcion_detener_grabacion_ahora()

        elif op == 7:

            opcion_cancelar_grabacion_o_pausar_vigia(tz_local)

        elif op == 8:

            opcion_gestor_almacenamiento_y_borrado()

        elif op == 9:

            opcion_modificar_mentor_efecto_domino()

        elif op == 10:

            opcion_gestionar_grupos_mentores()

        elif op == 11:

            opcion_auditar_y_rescatar_procesos()

        elif op == 12:

            opcion_rescatar_y_publicar_web()

        elif op == 13:

            print("\n👋 Saliendo del Centro de Control. ¡Hasta pronto!")

            break

if __name__ == "__main__":

    main()

