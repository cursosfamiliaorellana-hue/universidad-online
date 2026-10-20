"""

database.py - Módulo de base de datos SQLite Anti-duplicados para Bot_UniversidadOnline

Incluye Escáner Profundo de ./grabaciones y lógica estricta de Reactivación con Borrado Físico.

"""

import datetime

import glob

import json

import os

import re

import shutil

import sqlite3

import sys

import unicodedata

from typing import Optional, Dict, Any, List, Tuple

if sys.platform == "win32":

    try:

        sys.stdout.reconfigure(encoding="utf-8")

        sys.stderr.reconfigure(encoding="utf-8")

    except Exception:

        pass

DB_FILENAME = "clases.db"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DB_PATH = os.path.join(BASE_DIR, DB_FILENAME)

DB_FILE = DEFAULT_DB_PATH

DB_PATH = DEFAULT_DB_PATH

def normalizar_id(texto: str) -> str:

    if not texto:

        return ""

    descompuesto = unicodedata.normalize("NFKD", texto)

    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))

    minusculas = sin_tildes.lower()

    sin_simbolos = re.sub(r"[^a-z0-9\s]", " ", minusculas)

    return re.sub(r"\s+", " ", sin_simbolos).strip()

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:

    path = db_path or DEFAULT_DB_PATH

    conn = sqlite3.connect(path)

    conn.row_factory = sqlite3.Row

    return conn

def ejecutar_query(query: str, params: Tuple = (), db_path: Optional[str] = None) -> bool:

    conn = get_connection(db_path)

    try:

        query_fixed = re.sub(r"\bclases\b", "clases_grabadas", query)

        with conn:

            conn.execute(query_fixed, params)

        return True

    except Exception as e:

        print(f"[DB] Aviso en ejecutar_query: {e}")

        return False

    finally:

        conn.close()

def init_db(db_path: Optional[str] = None) -> None:

    conn = get_connection(db_path)

    try:

        with conn:

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS clases_grabadas (

                    id_clase TEXT PRIMARY KEY,

                    titulo_original TEXT NOT NULL,

                    fecha_grabacion TEXT,

                    estado TEXT NOT NULL DEFAULT 'PENDIENTE',

                    ruta_archivo TEXT,

                    transversal TEXT,

                    nivel INTEGER DEFAULT 1,

                    duracion_min INTEGER DEFAULT 60,

                    importancia_creacion INTEGER DEFAULT 0,

                    pareto_creacion INTEGER DEFAULT 0,

                    importancia_comercializacion INTEGER DEFAULT 0,

                    pareto_comercializacion INTEGER DEFAULT 0,

                    analisis_json TEXT,

                    notebook_url TEXT,

                    podcast_archivo TEXT,

                    podcast_fecha TEXT,

                    url_hotmart TEXT,

                    telegram_url TEXT,

                    telegram_app_url TEXT,

                    telegram_web_url TEXT,

                    mentor TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            conn.execute("CREATE INDEX IF NOT EXISTS idx_clases_estado ON clases_grabadas (estado);")

            # Migración preventiva: Si la tabla fue creada en una versión antigua con restricción CHECK(estado IN ...)

            try:

                cur_mig = conn.cursor()

                cur_mig.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='clases_grabadas'")

                row_sql = cur_mig.fetchone()

                if row_sql and "CHECK(estado IN" in (row_sql[0] or ""):

                    cur_mig.execute("PRAGMA foreign_keys = OFF")

                    cur_mig.execute("PRAGMA table_info(clases_grabadas)")

                    cols = [r[1] for r in cur_mig.fetchall()]

                    cols_str = ", ".join(cols)

                    cur_mig.execute("""

                        CREATE TABLE clases_grabadas_mig_auto (

                            id_clase TEXT PRIMARY KEY,

                            titulo_original TEXT NOT NULL,

                            fecha_grabacion TEXT,

                            estado TEXT NOT NULL DEFAULT 'PENDIENTE',

                            ruta_archivo TEXT,

                            transversal TEXT,

                            nivel INTEGER DEFAULT 1,

                            duracion_min INTEGER DEFAULT 60,

                            importancia_creacion INTEGER DEFAULT 0,

                            pareto_creacion INTEGER DEFAULT 0,

                            importancia_comercializacion INTEGER DEFAULT 0,

                            pareto_comercializacion INTEGER DEFAULT 0,

                            analisis_json TEXT,

                            notebook_url TEXT,

                            podcast_archivo TEXT,

                            podcast_fecha TEXT,

                            url_hotmart TEXT,

                            telegram_url TEXT,

                            telegram_app_url TEXT,

                            telegram_web_url TEXT,

                            mentor TEXT DEFAULT '',

                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                        )

                    """)

                    cur_mig.execute(f"INSERT INTO clases_grabadas_mig_auto ({cols_str}) SELECT {cols_str} FROM clases_grabadas")

                    cur_mig.execute("DROP TABLE clases_grabadas")

                    cur_mig.execute("ALTER TABLE clases_grabadas_mig_auto RENAME TO clases_grabadas")

                    cur_mig.execute("CREATE INDEX IF NOT EXISTS idx_clases_estado ON clases_grabadas (estado)")

            except Exception:

                pass

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS registro_podcasts (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    id_clase TEXT NOT NULL,

                    fecha TEXT NOT NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS notebooklm_cola_reintentos (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    id_clase TEXT NOT NULL UNIQUE,

                    titulo TEXT NOT NULL,

                    ruta_mp3 TEXT,

                    ruta_md TEXT,

                    analisis_json TEXT,

                    intentos INTEGER DEFAULT 0,

                    proximo_reintento TEXT,

                    estado TEXT DEFAULT 'PENDIENTE',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS mentores_grupos (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    nombre_mentor TEXT NOT NULL,

                    palabra_clave_grupo TEXT NOT NULL UNIQUE,

                    especialidad TEXT DEFAULT 'General',

                    activo INTEGER DEFAULT 1,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS capsulas_mentores (

                    id_capsula TEXT PRIMARY KEY,

                    mentor TEXT NOT NULL,

                    grupo_origen TEXT,

                    tipo TEXT NOT NULL,

                    titulo TEXT NOT NULL,

                    contenido_resumen TEXT,

                    fecha_mensaje_iso TEXT,

                    fecha_legible TEXT,

                    hora_legible TEXT,

                    analisis_json TEXT,

                    notebook_url TEXT,

                    podcast_archivo TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS configuracion_vigia (

                    clave TEXT PRIMARY KEY,

                    valor TEXT,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            conn.execute(

                """

                CREATE TABLE IF NOT EXISTS ingesta_manual_registro (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    ruta_archivo TEXT NOT NULL UNIQUE,

                    id_clase TEXT NOT NULL,

                    carpeta_origen TEXT NOT NULL,

                    fecha_ingesta TEXT NOT NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

                """

            )

            columnas_nuevas = [

                ("transversal", "TEXT"),

                ("nivel", "INTEGER DEFAULT 1"),

                ("duracion_min", "INTEGER DEFAULT 60"),

                ("importancia_creacion", "INTEGER DEFAULT 0"),

                ("pareto_creacion", "INTEGER DEFAULT 0"),

                ("importancia_comercializacion", "INTEGER DEFAULT 0"),

                ("pareto_comercializacion", "INTEGER DEFAULT 0"),

                ("analisis_json", "TEXT"),

                ("notebook_url", "TEXT"),

                ("podcast_archivo", "TEXT"),

                ("podcast_fecha", "TEXT"),

                ("url_hotmart", "TEXT"),

                ("telegram_url", "TEXT"),

                ("telegram_app_url", "TEXT"),

                ("telegram_web_url", "TEXT"),

                ("mentor", "TEXT DEFAULT ''"),

                ("regrabacion_activa", "INTEGER DEFAULT 0"),

            ]

            cur = conn.cursor()

            cur.execute("PRAGMA table_info(clases_grabadas)")

            existentes = {row["name"] for row in cur.fetchall()}

            for col, tipo in columnas_nuevas:

                if col not in existentes:

                    cur.execute(f"ALTER TABLE clases_grabadas ADD COLUMN {col} {tipo}")

            # Migración para soporte de Grupos Generales en mentores_grupos
            cur.execute("PRAGMA table_info(mentores_grupos)")

            mg_existentes = {row["name"] for row in cur.fetchall()}

            if "tipo_grupo" not in mg_existentes:

                cur.execute("ALTER TABLE mentores_grupos ADD COLUMN tipo_grupo TEXT DEFAULT 'MENTOR'")

    finally:

        conn.close()

def sincronizar_y_rescatar_grabaciones_locales(db_path: Optional[str] = None) -> int:

    init_db(db_path)

    dir_grab = os.path.join(BASE_DIR, "grabaciones")

    if not os.path.exists(dir_grab):

        return 0

    rescatadas = 0

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute("SELECT * FROM clases_grabadas")

            filas_bd = [dict(r) for r in cur.fetchall()]

            for r in filas_bd:

                id_c = r["id_clase"]

                if "prueba" in id_c.lower() or "test" in id_c.lower():

                    continue

                slug_c = id_c.replace(" ", "_")

                posibles = (

                    glob.glob(os.path.join(dir_grab, "**", f"*{slug_c}*.*"), recursive=True)

                    + glob.glob(os.path.join(dir_grab, f"*{slug_c}*"), recursive=False)

                )

                tiene_archivos = (r.get("ruta_archivo") and os.path.exists(r["ruta_archivo"])) or len(posibles) > 0 or bool(r.get("analisis_json")) or bool(r.get("telegram_url"))

                if r.get("estado") not in ("COMPLETADA", "OCULTA", "CANCELADO_MANUALMENTE") and tiene_archivos:

                    cur.execute("UPDATE clases_grabadas SET estado = 'COMPLETADA' WHERE id_clase = ?", (id_c,))

                    rescatadas += 1

            cur.execute("SELECT id_clase, titulo_original, ruta_archivo FROM clases_grabadas")

            completadas_actuales = cur.fetchall()

            ids_conocidos = {row["id_clase"] for row in completadas_actuales}

            slugs_conocidos = {normalizar_id(row["id_clase"]).replace(" ", "_") for row in completadas_actuales}

            rutas_conocidas = {os.path.abspath(row["ruta_archivo"]) for row in completadas_actuales if row["ruta_archivo"]}

            for root, dirs, files in os.walk(dir_grab):

                if os.path.abspath(root) == os.path.abspath(dir_grab):

                    continue

                nombre_carpeta = os.path.basename(root)

                if nombre_carpeta.lower() in ("test", "temp", "mentores_capsulas", "mentorias"):

                    continue

                if "prueba" in nombre_carpeta.lower():

                    continue

                mp4s = [os.path.join(root, f) for f in files if f.lower().endswith(".mp4")]

                mds = [os.path.join(root, f) for f in files if f.lower().endswith(".md")]

                pngs = [os.path.join(root, f) for f in files if f.lower().endswith(".png")]

                audios = [os.path.join(root, f) for f in files if f.lower().endswith((".mp3", ".m4a"))]

                if not (mp4s or mds or pngs or audios):

                    continue

                id_candidato = normalizar_id(nombre_carpeta)

                slug_candidato = id_candidato.replace(" ", "_")

                ruta_mp4_principal = mp4s[0] if mp4s else ""

                if (

                    id_candidato in ids_conocidos

                    or slug_candidato in slugs_conocidos

                    or (ruta_mp4_principal and os.path.abspath(ruta_mp4_principal) in rutas_conocidas)

                ):

                    continue

                titulo_limpio = nombre_carpeta.replace("_", " ").strip().title()

                resumen_extraido = "Masterclass grabada y procesada en tu biblioteca local."

                if mds:

                    try:

                        with open(mds[0], "r", encoding="utf-8", errors="replace") as f_md:

                            texto_md = f_md.read()

                            primera_linea = texto_md.splitlines()[0] if texto_md.splitlines() else ""

                            if ":" in primera_linea:

                                titulo_limpio = primera_linea.split(":", 1)[1].strip()

                            elif primera_linea.startswith("#"):

                                titulo_limpio = primera_linea.lstrip("# ").strip()

                            m_res = re.search(r"## 📝 Resumen Didáctico\s+(.+?)(?:\n## |\Z)", texto_md, flags=re.DOTALL)

                            if m_res:

                                resumen_extraido = m_res.group(1).strip()

                    except Exception:

                        pass

                ref_file = ruta_mp4_principal or (mds[0] if mds else (pngs[0] if pngs else audios[0]))

                fecha_iso = datetime.datetime.fromtimestamp(os.path.getmtime(ref_file)).strftime("%Y-%m-%dT%H:%M:%S-04:00")

                es_ment = "mentoria" in root.lower() or "mentor" in nombre_carpeta.lower()

                transversal_def = "Mentorías" if es_ment else "General"

                analisis_basico = {

                    "transversal": transversal_def,

                    "nivel": 1,

                    "resumen_didactico": resumen_extraido,

                    "vertical_creacion": {"porcentaje_importancia": 80, "es_pareto_20_vital": True, "por_que_y_cuando_ver": "Grabación disponible en tu biblioteca."},

                    "vertical_comercializacion": {"porcentaje_importancia": 80, "es_pareto_20_vital": True, "por_que_y_cuando_ver": "Aplicación práctica directa."},

                }

                cur.execute(

                    """

                    INSERT OR REPLACE INTO clases_grabadas

                    (id_clase, titulo_original, fecha_grabacion, estado, ruta_archivo, transversal, importancia_creacion, pareto_creacion, importancia_comercializacion, pareto_comercializacion, analisis_json, podcast_archivo)

                    VALUES (?, ?, ?, 'COMPLETADA', ?, ?, 80, 1, 80, 1, ?, ?)

                    """,

                    (

                        slug_candidato,

                        titulo_limpio,

                        fecha_iso,

                        ruta_mp4_principal,

                        transversal_def,

                        json.dumps(analisis_basico, ensure_ascii=False),

                        audios[0] if audios else "",

                    ),

                )

                ids_conocidos.add(slug_candidato)

                slugs_conocidos.add(slug_candidato)

                rescatadas += 1

    except Exception as e:

        print(f"[DB] Error en escáner profundo de grabaciones: {e}")

    finally:

        conn.close()

    return rescatadas

def obtener_clase(id_clase: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT * FROM clases_grabadas WHERE id_clase = ?", (id_clase,))

        row = cur.fetchone()

        return dict(row) if row else None

    finally:

        conn.close()

def guardar_o_actualizar_clase(

    id_clase: str,

    titulo_original: str,

    fecha_grabacion: Optional[str] = None,

    estado: str = "PENDIENTE",

    ruta_archivo: Optional[str] = None,

    url_hotmart: Optional[str] = None,

    telegram_url: Optional[str] = None,

    telegram_app_url: Optional[str] = None,

    telegram_web_url: Optional[str] = None,

    duracion_min: Optional[int] = None,

    db_path: Optional[str] = None,

) -> Dict[str, Any]:

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute(

                "SELECT estado, ruta_archivo, fecha_grabacion, url_hotmart, telegram_url, telegram_app_url, telegram_web_url, duracion_min, regrabacion_activa FROM clases_grabadas WHERE id_clase = ?",

                (id_clase,),

            )

            existente = cur.fetchone()

            if existente:

                estado_actual = existente["estado"]

                # Lógica Safe Overwrite: Si se solicita PENDIENTE sobre una clase ya COMPLETADA (re-grabación),
                # se activa regrabacion_activa = 1 y se conserva todo el contenido anterior intacto.
                if estado == "COMPLETADA":

                    nuevo_estado = "COMPLETADA"

                    regrab_val = 0

                elif estado == "PENDIENTE":

                    nuevo_estado = "PENDIENTE"

                    regrab_val = 1 if (estado_actual == "COMPLETADA" or existente["ruta_archivo"]) else 0

                else:

                    nuevo_estado = "COMPLETADA" if estado_actual == "COMPLETADA" else estado

                    regrab_val = existente["regrabacion_activa"] if ("regrabacion_activa" in existente.keys() and existente["regrabacion_activa"]) else 0

                nueva_ruta = ruta_archivo if ruta_archivo else existente["ruta_archivo"]

                nueva_fecha = fecha_grabacion if fecha_grabacion else existente["fecha_grabacion"]

                nueva_url = url_hotmart if url_hotmart else existente["url_hotmart"]

                nuevo_tg_url = telegram_url if telegram_url else existente["telegram_url"]

                nuevo_tg_app = telegram_app_url if telegram_app_url else existente["telegram_app_url"]

                nuevo_tg_web = telegram_web_url if telegram_web_url else existente["telegram_web_url"]

                dur_existente = existente["duracion_min"] or 60

                nueva_dur = int(duracion_min) if (duracion_min is not None and int(duracion_min) > 0) else dur_existente

                cur.execute(

                    """

                    UPDATE clases_grabadas

                    SET titulo_original = ?,

                        fecha_grabacion = ?,

                        estado = ?,

                        ruta_archivo = ?,

                        url_hotmart = ?,

                        telegram_url = ?,

                        telegram_app_url = ?,

                        telegram_web_url = ?,

                        duracion_min = ?,

                        regrabacion_activa = ?,

                        updated_at = CURRENT_TIMESTAMP

                    WHERE id_clase = ?

                    """,

                    (titulo_original, nueva_fecha, nuevo_estado, nueva_ruta, nueva_url, nuevo_tg_url, nuevo_tg_app, nuevo_tg_web, nueva_dur, regrab_val, id_clase),

                )

            else:

                dur_insert = int(duracion_min) if (duracion_min is not None and int(duracion_min) > 0) else 60

                cur.execute(

                    """

                    INSERT INTO clases_grabadas (id_clase, titulo_original, fecha_grabacion, estado, ruta_archivo, url_hotmart, telegram_url, telegram_app_url, telegram_web_url, duracion_min)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                    """,

                    (id_clase, titulo_original, fecha_grabacion, estado, ruta_archivo, url_hotmart, telegram_url, telegram_app_url, telegram_web_url, dur_insert),

                )

        return obtener_clase(id_clase, db_path) or {}

    finally:

        conn.close()

def es_zoom_ya_registrado_bd(zoom_id: str, db_path: Optional[str] = None) -> bool:

    """Comprueba si un ID de reunión de Zoom ya está registrado en la base de datos."""

    if not zoom_id or zoom_id == "chat_voz_telegram":

        return False

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute(

            "SELECT id_clase, url_hotmart, estado FROM clases_grabadas WHERE url_hotmart LIKE ? AND estado IN ('PENDIENTE', 'GRABANDO', 'COMPLETADA')",

            (f"%{zoom_id}%",),

        )

        row = cur.fetchone()

        return bool(row)

    except Exception:

        return False

    finally:

        conn.close()

def guardar_enlace_telegram(

    id_clase: str,

    telegram_url: str,

    telegram_app_url: Optional[str] = None,

    telegram_web_url: Optional[str] = None,

    db_path: Optional[str] = None,

) -> bool:

    conn = get_connection(db_path)

    try:

        with conn:

            conn.execute(

                """

                UPDATE clases_grabadas

                SET telegram_url = ?,

                    telegram_app_url = COALESCE(?, telegram_app_url),

                    telegram_web_url = COALESCE(?, telegram_web_url),

                    updated_at = CURRENT_TIMESTAMP

                WHERE id_clase = ?

                """,

                (telegram_url, telegram_app_url, telegram_web_url, id_clase),

            )

        return True

    except Exception:

        return False

    finally:

        conn.close()

def es_clase_completada(id_clase: str, db_path: Optional[str] = None) -> bool:

    clase = obtener_clase(id_clase, db_path)

    return bool(clase and clase.get("estado") == "COMPLETADA")

def listar_clases(estado: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        if estado:

            cur.execute("SELECT * FROM clases_grabadas WHERE estado = ? ORDER BY fecha_grabacion ASC", (estado,))

        else:

            cur.execute("SELECT * FROM clases_grabadas ORDER BY fecha_grabacion ASC")

        return [dict(r) for r in cur.fetchall()]

    finally:

        conn.close()

def guardar_analisis_clase(id_clase: str, analisis: Dict[str, Any], db_path: Optional[str] = None) -> bool:

    conn = get_connection(db_path)

    try:

        transversal = analisis.get("transversal", "General")

        nivel = int(analisis.get("nivel", 1))

        mentor = analisis.get("mentor_identificado", "")

        vc = analisis.get("vertical_creacion", {})

        imp_creacion = int(vc.get("porcentaje_importancia", 0))

        pareto_creacion = 1 if vc.get("es_pareto_20_vital", False) else 0

        vcom = analisis.get("vertical_comercializacion", {})

        imp_comercializacion = int(vcom.get("porcentaje_importancia", 0))

        pareto_comercializacion = 1 if vcom.get("es_pareto_20_vital", False) else 0

        analisis_str = json.dumps(analisis, ensure_ascii=False)

        with conn:

            conn.execute(

                """

                UPDATE clases_grabadas

                SET transversal = ?,

                    nivel = ?,

                    importancia_creacion = ?,

                    pareto_creacion = ?,

                    importancia_comercializacion = ?,

                    pareto_comercializacion = ?,

                    analisis_json = ?,

                    mentor = COALESCE(NULLIF(?, ''), mentor),

                    updated_at = CURRENT_TIMESTAMP

                WHERE id_clase = ?

                """,

                (

                    transversal,

                    nivel,

                    imp_creacion,

                    pareto_creacion,

                    imp_comercializacion,

                    pareto_comercializacion,

                    analisis_str,

                    mentor,

                    id_clase,

                ),

            )

        return True

    except Exception:

        return False

    finally:

        conn.close()

def guardar_info_notebooklm(

    id_clase: str,

    notebook_url: Optional[str] = None,

    podcast_archivo: Optional[str] = None,

    podcast_fecha: Optional[str] = None,

    db_path: Optional[str] = None,

) -> bool:

    conn = get_connection(db_path)

    try:

        with conn:

            conn.execute(

                """

                UPDATE clases_grabadas

                SET notebook_url = COALESCE(?, notebook_url),

                    podcast_archivo = COALESCE(?, podcast_archivo),

                    podcast_fecha = COALESCE(?, podcast_fecha),

                    updated_at = CURRENT_TIMESTAMP

                WHERE id_clase = ?

                """,

                (notebook_url, podcast_archivo, podcast_fecha, id_clase),

            )

        return True

    finally:

        conn.close()

def agregar_o_actualizar_mentor_grupo(

    nombre_mentor: str,

    palabra_clave_grupo: str,

    especialidad: str = "General",

    tipo_grupo: str = "MENTOR",

    db_path: Optional[str] = None,

) -> bool:

    init_db(db_path)

    conn = get_connection(db_path)

    try:

        with conn:

            conn.execute(

                """

                INSERT INTO mentores_grupos (nombre_mentor, palabra_clave_grupo, especialidad, activo, tipo_grupo)

                VALUES (?, ?, ?, 1, ?)

                ON CONFLICT(palabra_clave_grupo) DO UPDATE SET

                    nombre_mentor = excluded.nombre_mentor,

                    especialidad = excluded.especialidad,

                    tipo_grupo = excluded.tipo_grupo,

                    activo = 1

                """,

                (nombre_mentor.strip(), palabra_clave_grupo.strip().lower(), especialidad.strip(), tipo_grupo.upper()),

            )

        return True

    except Exception:

        return False

    finally:

        conn.close()

def listar_mentores_grupos(db_path: Optional[str] = None) -> List[Dict[str, Any]]:

    init_db(db_path)

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT * FROM mentores_grupos WHERE activo = 1 ORDER BY nombre_mentor ASC")

        return [dict(r) for r in cur.fetchall()]

    finally:

        conn.close()

def guardar_capsula_o_noticia_mentor(

    id_capsula: str,

    mentor: str,

    grupo_origen: str,

    tipo: str,

    titulo: str,

    contenido_resumen: str,

    fecha_mensaje_iso: str,

    fecha_legible: str,

    hora_legible: str,

    analisis: Optional[Dict[str, Any]] = None,

    notebook_url: Optional[str] = None,

    podcast_archivo: Optional[str] = None,

    db_path: Optional[str] = None,

) -> bool:

    init_db(db_path)

    conn = get_connection(db_path)

    try:

        analisis_str = json.dumps(analisis or {}, ensure_ascii=False)

        with conn:

            conn.execute(

                """

                INSERT OR REPLACE INTO capsulas_mentores

                (id_capsula, mentor, grupo_origen, tipo, titulo, contenido_resumen, fecha_mensaje_iso, fecha_legible, hora_legible, analisis_json, notebook_url, podcast_archivo)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                """,

                (

                    id_capsula,

                    mentor,

                    grupo_origen,

                    tipo,

                    titulo,

                    contenido_resumen,

                    fecha_mensaje_iso,

                    fecha_legible,

                    hora_legible,

                    analisis_str,

                    notebook_url or "",

                    podcast_archivo or "",

                ),

            )

        return True

    except Exception:

        return False

    finally:

        conn.close()

def listar_capsulas_mentores(db_path: Optional[str] = None) -> List[Dict[str, Any]]:

    init_db(db_path)

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT * FROM capsulas_mentores ORDER BY fecha_mensaje_iso DESC")

        return [dict(r) for r in cur.fetchall()]

    finally:

        conn.close()

def obtener_conteo_podcasts_hoy(fecha_hoy: str, db_path: Optional[str] = None) -> int:

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS total FROM registro_podcasts WHERE fecha = ?", (fecha_hoy,))

        row = cur.fetchone()

        return row["total"] if row else 0

    finally:

        conn.close()

def registrar_podcast_hoy(id_clase: str, fecha_hoy: str, db_path: Optional[str] = None) -> None:

    conn = get_connection(db_path)

    try:

        with conn:

            conn.execute("INSERT INTO registro_podcasts (id_clase, fecha) VALUES (?, ?)", (id_clase, fecha_hoy))

    finally:

        conn.close()

def contar_fuentes_cuaderno(nombre_transversal: str, parte: int = 1, db_path: Optional[str] = None) -> int:

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS total FROM clases_grabadas WHERE transversal = ? AND estado = 'COMPLETADA'", (nombre_transversal,))

        row = cur.fetchone()

        total = row["total"] if row else 0

        return total % 45

    finally:

        conn.close()

def limpiar_clases_prueba(db_path: Optional[str] = None) -> int:

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute("DELETE FROM clases_grabadas WHERE id_clase LIKE '%prueba%'")

            return cur.rowcount

    finally:

        conn.close()

# ==============================================================================

# PUNTO 3: DESTRUCCIÓN FÍSICA Y REINICIO (Solución al "Rescate Fantasma")

# ==============================================================================

def reactivar_clase(id_clase: str, db_path: Optional[str] = None) -> bool:

    """Cambia el estado a PENDIENTE, limpia los campos y DESTRUYE FÍSICAMENTE las carpetas usando shutil.rmtree para evitar rescates fantasma."""

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT titulo_original, ruta_archivo FROM clases_grabadas WHERE id_clase = ?", (id_clase,))

        row = cur.fetchone()

        

        titulo_orig = row["titulo_original"] if row and row["titulo_original"] else ""

        slug_c = normalizar_id(id_clase).replace(" ", "_")

        slug_t = normalizar_id(titulo_orig).replace(" ", "_") if titulo_orig else ""

        # 1. Aniquilación física directa de la carpeta guardada en ruta_archivo

        if row and row["ruta_archivo"]:

            ruta_v = row["ruta_archivo"]

            carpeta = os.path.dirname(os.path.abspath(ruta_v))

            dir_grab = os.path.abspath(os.path.join(BASE_DIR, "grabaciones"))

            if os.path.exists(carpeta) and os.path.abspath(carpeta) != os.path.abspath(BASE_DIR) and os.path.abspath(carpeta) != dir_grab:

                try:

                    shutil.rmtree(carpeta, ignore_errors=True)

                    print(f"[DB] 🗑️ Carpeta de video destruida físicamente con shutil.rmtree: {carpeta}")

                except Exception as e_del:

                    print(f"[DB] Aviso al destruir carpeta {carpeta}: {e_del}")

        # 2. Búsqueda y aniquilación física exhaustiva en grabaciones y grabaciones/mentorias

        carpetas_base = [

            os.path.join(BASE_DIR, "grabaciones"),

            os.path.join(BASE_DIR, "grabaciones", "mentorias"),

        ]

        for root_dir in carpetas_base:

            if os.path.exists(root_dir):

                for item in os.listdir(root_dir):

                    item_path = os.path.join(root_dir, item)

                    item_low = item.lower()

                    if os.path.isdir(item_path):

                        if (

                            (slug_c and slug_c in item_low)

                            or id_clase.lower() in item_low

                            or (slug_t and slug_t in item_low)

                        ):

                            try:

                                shutil.rmtree(item_path, ignore_errors=True)

                                print(f"[DB] 🗑️ Carpeta coincidente destruida con shutil.rmtree: {item_path}")

                            except Exception as e_del:

                                print(f"[DB] Aviso al destruir carpeta {item_path}: {e_del}")

                    elif os.path.isfile(item_path):

                        if (slug_c and slug_c in item_low) or id_clase.lower() in item_low:

                            try:

                                os.remove(item_path)

                            except Exception:

                                pass

        # 3. Reiniciar la Base de Datos a estado virgen

        with conn:

            cur.execute(

                """

                UPDATE clases_grabadas 

                SET estado = 'PENDIENTE', 

                    ruta_archivo = NULL, 

                    analisis_json = NULL,

                    telegram_url = NULL,

                    telegram_app_url = NULL,

                    telegram_web_url = NULL,

                    notebook_url = NULL,

                    podcast_archivo = NULL,

                    updated_at = CURRENT_TIMESTAMP 

                WHERE id_clase = ?

                """,

                (id_clase,)

            )

            return cur.rowcount > 0

    except Exception as e:

        print(f"[DB] Error reactivando clase {id_clase}: {e}")

        return False

    finally:

        conn.close()

def eliminar_clase(id_clase: str, db_path: Optional[str] = None) -> bool:

    """Borra físicamente todas las carpetas con shutil.rmtree y elimina el registro de la BD."""

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT titulo_original, ruta_archivo FROM clases_grabadas WHERE id_clase = ?", (id_clase,))

        row = cur.fetchone()

        titulo_orig = row["titulo_original"] if row and row["titulo_original"] else ""

        slug_c = normalizar_id(id_clase).replace(" ", "_")

        slug_t = normalizar_id(titulo_orig).replace(" ", "_") if titulo_orig else ""

        # 1. Aniquilación física directa de la carpeta guardada

        if row and row["ruta_archivo"]:

            carpeta = os.path.dirname(os.path.abspath(row["ruta_archivo"]))

            dir_grab = os.path.abspath(os.path.join(BASE_DIR, "grabaciones"))

            if os.path.exists(carpeta) and os.path.abspath(carpeta) != os.path.abspath(BASE_DIR) and os.path.abspath(carpeta) != dir_grab:

                try:

                    shutil.rmtree(carpeta, ignore_errors=True)

                    print(f"[DB] 🗑️ Carpeta de video destruida con shutil.rmtree: {carpeta}")

                except Exception as e_del:

                    print(f"[DB] Aviso al destruir carpeta {carpeta}: {e_del}")

        # 2. Búsqueda y aniquilación física exhaustiva

        carpetas_base = [

            os.path.join(BASE_DIR, "grabaciones"),

            os.path.join(BASE_DIR, "grabaciones", "mentorias"),

        ]

        for root_dir in carpetas_base:

            if os.path.exists(root_dir):

                for item in os.listdir(root_dir):

                    item_path = os.path.join(root_dir, item)

                    item_low = item.lower()

                    if os.path.isdir(item_path):

                        if (

                            (slug_c and slug_c in item_low)

                            or id_clase.lower() in item_low

                            or (slug_t and slug_t in item_low)

                        ):

                            try:

                                shutil.rmtree(item_path, ignore_errors=True)

                                print(f"[DB] 🗑️ Carpeta coincidente destruida con shutil.rmtree: {item_path}")

                            except Exception as e_del:

                                print(f"[DB] Aviso al destruir carpeta {item_path}: {e_del}")

                    elif os.path.isfile(item_path):

                        if (slug_c and slug_c in item_low) or id_clase.lower() in item_low:

                            try:

                                os.remove(item_path)

                            except Exception:

                                pass

        with conn:

            cur.execute("DELETE FROM clases_grabadas WHERE id_clase = ?", (id_clase,))

            return cur.rowcount > 0

    except Exception as e:

        print(f"[DB] Error eliminando clase {id_clase}: {e}")

        return False

    finally:

        conn.close()

# ==============================================================================

# PUENTE INTER-PROCESOS: PAUSA DE VIGÍA Y CANCELACIÓN EN TIEMPO REAL (HOT-CANCEL)

# ==============================================================================

ESTADO_VIGIA_FILE = os.path.join(BASE_DIR, "estado_vigia.json")

def cancelar_clase_manualmente(id_clase: str, db_path: Optional[str] = None) -> bool:

    """Cambia el estado de una clase a CANCELADO_MANUALMENTE en la BD."""

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute(

                "UPDATE clases_grabadas SET estado = 'CANCELADO_MANUALMENTE', updated_at = CURRENT_TIMESTAMP WHERE id_clase = ?",

                (id_clase,)

            )

            return cur.rowcount > 0

    except Exception as e:

        print(f"[DB] Error cancelando clase {id_clase}: {e}")

        return False

    finally:

        conn.close()

def es_clase_cancelada(id_clase: str, db_path: Optional[str] = None) -> bool:

    """Verifica de forma rápida si la clase fue cancelada manualmente por el usuario."""

    clase = obtener_clase(id_clase, db_path)

    return bool(clase and clase.get("estado") == "CANCELADO_MANUALMENTE")

def pausar_vigia_telegram(hasta_dt_str: Optional[str] = None, motivo: str = "Pausa manual del usuario") -> str:

    """Pausa el Vigía de Telegram escribiendo en estado_vigia.json hasta la fecha indicada o fin del día."""

    if not hasta_dt_str:

        hoy = datetime.date.today()

        hasta_dt_str = f"{hoy.strftime('%Y-%m-%d')} 23:59:59"

    datos = {

        "vigia_pausado_hasta": hasta_dt_str,

        "motivo": motivo,

        "fecha_pausa": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

    }

    try:

        with open(ESTADO_VIGIA_FILE, "w", encoding="utf-8") as f:

            json.dump(datos, f, indent=2, ensure_ascii=False)

        return hasta_dt_str

    except Exception as e:

        print(f"[DB] Error al pausar Vigía: {e}")

        return ""

def reanudar_vigia_telegram() -> bool:

    """Reanuda el Vigía de Telegram limpiando el archivo puente de estado."""

    try:

        if os.path.exists(ESTADO_VIGIA_FILE):

            os.remove(ESTADO_VIGIA_FILE)

        return True

    except Exception as e:

        print(f"[DB] Error al reanudar Vigía: {e}")

        return False

def obtener_estado_pausa_vigia() -> Tuple[bool, str]:

    """Retorna (True, 'hasta las ...') si el Vigía de Telegram se encuentra en pausa activa."""

    if not os.path.exists(ESTADO_VIGIA_FILE):

        return False, ""

    try:

        with open(ESTADO_VIGIA_FILE, "r", encoding="utf-8") as f:

            data = json.load(f)

        limite_str = data.get("vigia_pausado_hasta", "").strip()

        if not limite_str:

            return False, ""

        dt_limite = None

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):

            try:

                dt_limite = datetime.datetime.strptime(limite_str[:19], fmt)

                break

            except Exception:

                continue

        if not dt_limite:

            return False, ""

        if datetime.datetime.now() < dt_limite:

            return True, limite_str

        else:

            try:

                os.remove(ESTADO_VIGIA_FILE)

            except Exception:

                pass

            return False, ""

    except Exception:

        return False, ""

# ==============================================================================

# GESTIÓN DE ALMACENAMIENTO LOCAL Y PURGA DE MULTIMEDIA (NUBE DEFINITIVA)

# ==============================================================================

def purgar_multimedia_local_clase(

    id_clase: str,

    ruta_video: Optional[str] = None,

    ruta_audio: Optional[str] = None,

    db_path: Optional[str] = None,

) -> int:

    """

    Elimina automáticamente los archivos pesados (.mp4, .m4a, .webm, clips temporales)

    de una clase ya respaldada en Telegram y publicada en la App Web.

    Conserva estrictamente los metadatos ligeros:

    - Ficha_Didactica_*.md

    - *.json (análisis)

    - *.png (infografías y mapas mentales)

    Retorna la cantidad de bytes liberados.

    """

    bytes_liberados = 0

    archivos_a_borrar = set()

    for r in (ruta_video, ruta_audio):

        if r and os.path.exists(r) and os.path.isfile(r):

            archivos_a_borrar.add(os.path.abspath(r))

    clase = obtener_clase(id_clase, db_path)

    if clase:

        r_db = clase.get("ruta_archivo")

        if r_db and os.path.exists(r_db) and os.path.isfile(r_db):

            archivos_a_borrar.add(os.path.abspath(r_db))

        r_pod = clase.get("podcast_archivo")

        if r_pod and os.path.exists(r_pod) and os.path.isfile(r_pod):

            archivos_a_borrar.add(os.path.abspath(r_pod))

    carpetas_a_escanear = set()

    for arch in list(archivos_a_borrar):

        carpetas_a_escanear.add(os.path.dirname(arch))

    slug = normalizar_id(id_clase).replace(" ", "_")

    dir_grab = os.path.join(BASE_DIR, "grabaciones")

    if os.path.exists(dir_grab):

        for root, dirs, files in os.walk(dir_grab):

            bname = os.path.basename(root).lower()

            if slug in bname or id_clase.lower() in bname:

                carpetas_a_escanear.add(os.path.abspath(root))

    exts_pesadas = (".mp4", ".m4a", ".webm", ".mkv", ".avi")

    for carpeta in carpetas_a_escanear:

        if not os.path.exists(carpeta):

            continue

        try:

            for item in os.listdir(carpeta):

                item_path = os.path.join(carpeta, item)

                if not os.path.isfile(item_path):

                    continue

                ext = os.path.splitext(item)[1].lower()

                if ext in exts_pesadas or (ext == ".mp3" and ("temp" in item.lower() or "clip" in item.lower())):

                    archivos_a_borrar.add(os.path.abspath(item_path))

        except Exception:

            pass

    for arch_path in archivos_a_borrar:

        try:

            if os.path.exists(arch_path):

                peso = os.path.getsize(arch_path)

                os.remove(arch_path)

                bytes_liberados += peso

        except Exception as e_del:

            print(f"[Limpieza] Aviso al borrar archivo {arch_path}: {e_del}")

    mb_liberados = round(bytes_liberados / (1024 * 1024), 1)

    print(f"\n[Limpieza Local] 🧹 Multimedia local purgada para ahorrar espacio ({mb_liberados} MB liberados). Backup en Telegram: [OK]")

    print(f"[Limpieza Local] 💾 Metadatos conservados: Ficha Didáctica, Resumen y Análisis.")

    return bytes_liberados

def purgar_todos_los_videos_locales() -> Tuple[int, int]:

    """

    Escanea todo el directorio grabaciones/ y elimina TODOS los archivos pesados

    (.mp4, .m4a, .webm, temporales), conservando únicamente .md, .json, .png, .jpg.

    Retorna (cantidad_archivos_borrados, bytes_liberados).

    """

    dir_grab = os.path.join(BASE_DIR, "grabaciones")

    if not os.path.exists(dir_grab):

        return 0, 0

    archivos_borrados = 0

    bytes_liberados = 0

    exts_pesadas = (".mp4", ".m4a", ".webm", ".mkv", ".avi")

    for root, dirs, files in os.walk(dir_grab):

        for f in files:

            ext = os.path.splitext(f)[1].lower()

            if ext in exts_pesadas or (ext == ".mp3" and ("temp" in f.lower() or "clip" in f.lower())):

                full_path = os.path.join(root, f)

                try:

                    peso = os.path.getsize(full_path)

                    os.remove(full_path)

                    archivos_borrados += 1

                    bytes_liberados += peso

                except Exception as e:

                    print(f"[Limpieza] No se pudo borrar {full_path}: {e}")

    # Archivos temporales sueltos en BASE_DIR

    try:

        for f in os.listdir(BASE_DIR):

            if f.lower().startswith("temp_") and os.path.splitext(f)[1].lower() in (".mp4", ".webm", ".mp3", ".ogg"):

                full_p = os.path.join(BASE_DIR, f)

                if os.path.isfile(full_p):

                    try:

                        peso = os.path.getsize(full_p)

                        os.remove(full_p)

                        archivos_borrados += 1

                        bytes_liberados += peso

                    except Exception:

                        pass

    except Exception:

        pass

    return archivos_borrados, bytes_liberados

def cambiar_visibilidad_web_clase(id_clase: str, ocultar: bool = True, db_path: Optional[str] = None) -> bool:

    """Cambia el estado de una clase entre COMPLETADA y OCULTA para controlar su visibilidad en la App Web."""

    conn = get_connection(db_path)

    try:

        nuevo_estado = "OCULTA" if ocultar else "COMPLETADA"

        with conn:

            cur = conn.cursor()

            cur.execute(

                "UPDATE clases_grabadas SET estado = ?, updated_at = CURRENT_TIMESTAMP WHERE id_clase = ?",

                (nuevo_estado, id_clase),

            )

            return cur.rowcount > 0

    except Exception as e:

        print(f"[DB] Error al cambiar visibilidad de clase {id_clase}: {e}")

        return False

    finally:

        conn.close()

def encolar_reintento_notebooklm(

    id_clase: str,

    titulo: str,

    ruta_mp3: Optional[str] = None,

    ruta_md: Optional[str] = None,

    analisis: Optional[Dict[str, Any]] = None,

    horas_espera: float = 5.0,

    db_path: Optional[str] = None,

) -> bool:

    conn = get_connection(db_path)

    try:

        proximo = datetime.datetime.now() + datetime.timedelta(hours=horas_espera)

        proximo_iso = proximo.strftime("%Y-%m-%d %H:%M:%S")

        analisis_str = json.dumps(analisis, ensure_ascii=False) if analisis else None

        with conn:

            conn.execute(

                """

                INSERT INTO notebooklm_cola_reintentos (id_clase, titulo, ruta_mp3, ruta_md, analisis_json, intentos, proximo_reintento, estado)

                VALUES (?, ?, ?, ?, ?, 1, ?, 'PENDIENTE')

                ON CONFLICT(id_clase) DO UPDATE SET

                    ruta_mp3 = COALESCE(?, ruta_mp3),

                    ruta_md = COALESCE(?, ruta_md),

                    analisis_json = COALESCE(?, analisis_json),

                    intentos = intentos + 1,

                    proximo_reintento = ?,

                    estado = 'PENDIENTE',

                    updated_at = CURRENT_TIMESTAMP

                """,

                (id_clase, titulo, ruta_mp3, ruta_md, analisis_str, proximo_iso, ruta_mp3, ruta_md, analisis_str, proximo_iso),

            )

        return True

    except Exception:

        return False

    finally:

        conn.close()

def obtener_reintentos_notebooklm_listos(db_path: Optional[str] = None) -> List[Dict[str, Any]]:

    conn = get_connection(db_path)

    try:

        ahora_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur = conn.cursor()

        cur.execute(

            "SELECT * FROM notebooklm_cola_reintentos WHERE estado = 'PENDIENTE' AND proximo_reintento <= ? ORDER BY proximo_reintento ASC",

            (ahora_iso,),

        )

        return [dict(r) for r in cur.fetchall()]

    finally:

        conn.close()

def marcar_reintento_notebooklm_completado(id_clase: str, db_path: Optional[str] = None) -> bool:

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute("UPDATE notebooklm_cola_reintentos SET estado = 'COMPLETADO', updated_at = CURRENT_TIMESTAMP WHERE id_clase = ?", (id_clase,))

            return cur.rowcount > 0

    finally:

        conn.close()

def marcar_reintento_notebooklm_fallido(id_clase: str, horas_espera: float = 5.0, db_path: Optional[str] = None) -> bool:

    conn = get_connection(db_path)

    try:

        proximo = datetime.datetime.now() + datetime.timedelta(hours=horas_espera)

        proximo_iso = proximo.strftime("%Y-%m-%d %H:%M:%S")

        with conn:

            cur = conn.cursor()

            cur.execute(

                "UPDATE notebooklm_cola_reintentos SET intentos = intentos + 1, proximo_reintento = ?, updated_at = CURRENT_TIMESTAMP WHERE id_clase = ?",

                (proximo_iso, id_clase),

            )

            return cur.rowcount > 0

    finally:

        conn.close()

def obtener_ultima_ejecucion_vigia(db_path: Optional[str] = None) -> Optional[str]:

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT valor FROM configuracion_vigia WHERE clave = 'ultima_ejecucion_vigia'")

        row = cur.fetchone()

        return row[0] if row else None

    except Exception:

        return None

    finally:

        conn.close()

def guardar_ultima_ejecucion_vigia(dt_str: Optional[str] = None, db_path: Optional[str] = None) -> bool:

    valor = dt_str or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S-04:00")

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute(

                "INSERT INTO configuracion_vigia (clave, valor, updated_at) VALUES ('ultima_ejecucion_vigia', ?, CURRENT_TIMESTAMP) "

                "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, updated_at = CURRENT_TIMESTAMP",

                (valor,),

            )

            return True

    except Exception as e:

        print(f"[DB] Error guardando última ejecución vigía: {e}")

        return False

    finally:

        conn.close()

def buscar_mentoria_por_mentor_y_fecha(mentor: str, fecha_iso: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:

    """Busca si ya existe una mentoría o clase del mismo mentor en la misma fecha (o día)."""

    if not mentor:

        return None

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT * FROM clases_grabadas")

        filas = [dict(r) for r in cur.fetchall()]

        dia_buscado = fecha_iso[:10] if len(fecha_iso) >= 10 else ""

        norm_mentor = normalizar_id(mentor)

        for c in filas:

            c_mentor = normalizar_id(c.get("mentor") or "")

            c_tit = normalizar_id(c.get("titulo_original") or "")

            c_fecha = (c.get("fecha_grabacion") or "")[:10]

            coincide_mentor = (norm_mentor in c_mentor or norm_mentor in c_tit) if norm_mentor else False

            coincide_fecha = bool(dia_buscado and c_fecha == dia_buscado)

            if coincide_mentor and coincide_fecha:

                return c

            if coincide_mentor and c.get("id_clase", "").startswith("voz_tg_"):

                return c

        return None

    finally:

        conn.close()

def borrado_seguro_clase(id_clase: str, db_path: Optional[str] = None) -> Dict[str, Any]:

    """

    Borrado Seguro (Safe-Purge):

    Elimina los archivos físicos multimedia locales (.mp4, .m4a, .webm) para liberar espacio,

    pero MANTIENE la clase en la Base de Datos con estado 'COMPLETADA' y sus enlaces de Telegram /

    NotebookLM intactos, asegurando que siga existiendo para siempre en la App Web y la Nube.

    """

    conn = get_connection(db_path)

    clase = None

    try:

        cur = conn.cursor()

        cur.execute("SELECT * FROM clases_grabadas WHERE id_clase = ?", (id_clase,))

        r = cur.fetchone()

        if r:

            clase = dict(r)

    finally:

        conn.close()

    if not clase:

        return {"ok": False, "mensaje": f"Clase '{id_clase}' no encontrada en la base de datos.", "bytes_liberados": 0}

    bytes_liberados = 0

    archivos_borrados = []

    # 1. Borrar ruta_archivo registrada si existe

    ruta_reg = clase.get("ruta_archivo")

    if ruta_reg and os.path.exists(ruta_reg) and os.path.isfile(ruta_reg):

        ext = os.path.splitext(ruta_reg)[1].lower()

        if ext in (".mp4", ".m4a", ".webm", ".mkv", ".mov", ".avi"):

            try:

                sz = os.path.getsize(ruta_reg)

                os.remove(ruta_reg)

                bytes_liberados += sz

                archivos_borrados.append(os.path.basename(ruta_reg))

            except Exception as e:

                print(f"[DB Borrado Seguro] No se pudo borrar {ruta_reg}: {e}")

    # 2. Escanear carpeta de grabaciones por archivos pesados con este slug

    dir_grab = os.path.join(BASE_DIR, "grabaciones")

    slug = id_clase.replace(" ", "_")

    coincidencias = glob.glob(os.path.join(dir_grab, "**", f"*{slug}*.*"), recursive=True)

    for f in coincidencias:

        if os.path.isfile(f) and os.path.exists(f):

            ext = os.path.splitext(f)[1].lower()

            if ext in (".mp4", ".m4a", ".webm", ".mkv", ".mov", ".avi", ".ts"):

                try:

                    sz = os.path.getsize(f)

                    os.remove(f)

                    bytes_liberados += sz

                    archivos_borrados.append(os.path.basename(f))

                except Exception:

                    pass

    # 3. Preservar estado COMPLETADA y asegurar que no se oculte de la App Web

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute(

                "UPDATE clases_grabadas SET estado = 'COMPLETADA', updated_at = CURRENT_TIMESTAMP WHERE id_clase = ?",

                (id_clase,)

            )

    finally:

        conn.close()

    mb_liberados = round(bytes_liberados / (1024 * 1024), 2)

    return {

        "ok": True,

        "id_clase": id_clase,

        "titulo": clase.get("titulo_original"),

        "archivos_borrados": archivos_borrados,

        "bytes_liberados": bytes_liberados,

        "mb_liberados": mb_liberados,

        "mensaje": f"Se liberaron {mb_liberados} MB. La clase sigue activa y visible en la App Web con sus enlaces a Telegram."

    }

def obtener_resumen_dashboard(db_path: Optional[str] = None) -> Dict[str, Any]:

    """Retorna un resumen de métricas completas para el Dashboard Operativo."""

    conn = get_connection(db_path)

    try:

        cur = conn.cursor()

        cur.execute("SELECT * FROM clases_grabadas ORDER BY fecha_grabacion DESC, created_at DESC")

        filas = [dict(r) for r in cur.fetchall()]

        total = len(filas)

        completadas = sum(1 for c in filas if c.get("estado") == "COMPLETADA")

        pendientes = sum(1 for c in filas if c.get("estado") == "PENDIENTE")

        grabando = sum(1 for c in filas if c.get("estado") == "GRABANDO")

        canceladas = sum(1 for c in filas if c.get("estado") == "CANCELADO_MANUALMENTE")

        con_telegram = sum(1 for c in filas if bool(c.get("telegram_url") or c.get("telegram_app_url") or c.get("telegram_web_url")))

        con_audio = sum(1 for c in filas if bool(c.get("podcast_archivo") or (c.get("notebook_url") and c.get("notebook_url") != "https://notebooklm.google.com/")))

        cur.execute("SELECT COUNT(*) FROM capsulas_mentores")

        total_capsulas = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM mentores_grupos WHERE activo = 1")

        total_mentores = cur.fetchone()[0]

        return {

            "total_clases": total,

            "completadas": completadas,

            "pendientes": pendientes,

            "grabando": grabando,

            "canceladas": canceladas,

            "con_telegram": con_telegram,

            "con_audio": con_audio,

            "total_capsulas": total_capsulas,

            "total_mentores": total_mentores,

            "clases": filas,

        }

    finally:

        conn.close()

if __name__ == "__main__":

    init_db()

    sincronizar_y_rescatar_grabaciones_locales()

def marcar_regrabacion_segura(id_clase: str, db_path: Optional[str] = None) -> bool:

    """Activa la re-grabación segura (Safe Overwrite / Reemplazo Diferido) de una clase.

    Pasa su estado a 'PENDIENTE' con regrabacion_activa = 1 sin borrar ningún archivo local

    ni análisis previo, asegurando que siga visible en la App Web hasta que la nueva versión culmine."""

    init_db(db_path)

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute(

                """

                UPDATE clases_grabadas

                SET estado = 'PENDIENTE',

                    regrabacion_activa = 1,

                    updated_at = CURRENT_TIMESTAMP

                WHERE id_clase = ?

                """,

                (id_clase,),

            )

            return cur.rowcount > 0

    finally:

        conn.close()

def es_regrabacion_activa(id_clase: str, db_path: Optional[str] = None) -> bool:

    """Comprueba si una clase tiene una re-grabación segura pendiente."""

    c = obtener_clase(id_clase, db_path)

    return bool(c and c.get("regrabacion_activa") == 1)

def agregar_grupo_general(

    nombre_canal: str,

    palabra_clave_o_id: str,

    especialidad: str = "General",

    db_path: Optional[str] = None,

) -> bool:

    """Registra un grupo o canal general de Telegram (sin mentor asociado) en la base de datos."""

    return agregar_o_actualizar_mentor_grupo(

        nombre_mentor=nombre_canal.strip() or "General",

        palabra_clave_grupo=palabra_clave_o_id.strip(),

        especialidad=especialidad.strip(),

        tipo_grupo="GENERAL",

        db_path=db_path,

    )

def desactivar_grupo_vigilado(id_o_palabra: str, db_path: Optional[str] = None) -> bool:

    """Desactiva un grupo o canal del Vigía por su palabra clave o ID numérico."""

    init_db(db_path)

    conn = get_connection(db_path)

    try:

        with conn:

            cur = conn.cursor()

            cur.execute(

                """

                UPDATE mentores_grupos

                SET activo = 0

                WHERE palabra_clave_grupo = ? OR id = ? OR LOWER(nombre_mentor) = ?

                """,

                (str(id_o_palabra).strip().lower(), str(id_o_palabra).strip(), str(id_o_palabra).strip().lower()),

            )

            return cur.rowcount > 0

    finally:

        conn.close()
