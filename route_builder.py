"""
route_builder.py - Generador de la Plataforma Web LMS Interactiva & PWA
Incluye:
- Audio-resumen expandido para TODAS las Masterclasses, Mentorías y Playbooks (sin límites restrictivos).
- Sistema Interactivo de Flashcards (Pregunta/Respuesta/Dificultad) con animación de giro 3D.
- Checklist de Estudio con persistencia en LocalStorage del navegador y contador de progreso en tiempo real.
- Mapa Panorámico de Estudio (Roadmap Guiado por Fases) unificando la ruta de aprendizaje.
- Distintivo visual elegante para Clases Clave (⭐ Clase Clave).
- Auto-deploy a GitHub Pages y Service Worker Anti-Caché.
"""

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
from typing import Optional, Dict, Any, List

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_OUTPUT_PATH = os.path.join(BASE_DIR, "Mis_Rutas_80_20_UniversidadOnline.html")
ROOT_INDEX_HTML = os.path.join(BASE_DIR, "index.html")
APP_WEB_DIR = os.path.join(BASE_DIR, "app_web")
APP_WEB_HTML = os.path.join(APP_WEB_DIR, "index.html")
DATA_JSON_PATH = os.path.join(BASE_DIR, "data.json")
APP_WEB_DATA_JSON = os.path.join(APP_WEB_DIR, "data.json")
DATABASE_JSON_PATH = os.path.join(BASE_DIR, "database.json")
APP_WEB_DATABASE_JSON = os.path.join(APP_WEB_DIR, "database.json")


def sintetizar_flashcards(analisis: Dict[str, Any], titulo: str, transversal: str) -> List[Dict[str, str]]:
    """Garantiza que toda clase o cápsula tenga flashcards de estudio de alta calidad."""
    if analisis.get("flashcards") and isinstance(analisis["flashcards"], list) and len(analisis["flashcards"]) > 0:
        return analisis["flashcards"]

    flashcards = []

    # 1. Extraer desde infografía de pasos
    for p in analisis.get("infografia_pasos", []):
        t = p.get("titulo") or "Paso Clave"
        exp = p.get("explicacion") or ""
        if exp:
            flashcards.append({
                "pregunta": f"¿Cómo se implementa: {t}?",
                "respuesta": exp,
                "dificultad": "Intermedia",
            })

    # 2. Extraer desde checklist práctico
    for i, ch in enumerate(analisis.get("checklist_15_min", []), 1):
        flashcards.append({
            "pregunta": f"Acción Rápida #{i}: ¿Qué acción concreta se recomienda ejecutar?",
            "respuesta": ch,
            "dificultad": "Básica",
        })

    # 3. Extraer desde quiz práctico
    for q in analisis.get("quiz_practico", []):
        preg = q.get("pregunta") or ""
        exp = q.get("explicacion") or ""
        correcta = q.get("respuesta_correcta") or ""
        if preg and exp:
            flashcards.append({
                "pregunta": f"Pregunta de Maestría: {preg}",
                "respuesta": f"Opción correcta ({correcta}): {exp}",
                "dificultad": "Avanzada",
            })

    # Fallback con el resumen si no hubiera elementos
    if not flashcards:
        resumen = analisis.get("resumen_didactico") or f"Conceptos fundamentales de {titulo}."
        flashcards.append({
            "pregunta": f"¿Cuál es el objetivo y aprendizaje principal de '{titulo}'?",
            "respuesta": resumen,
            "dificultad": "Básica",
        })
        flashcards.append({
            "pregunta": f"¿En qué área estratégica se aplica este contenido?",
            "respuesta": f"Pertenece al eje de {transversal}. Aplícalo paso a paso en tu modelo de negocio.",
            "dificultad": "Intermedia",
        })

    return flashcards


def construir_datos_clases() -> List[Dict[str, Any]]:
    database.sincronizar_y_rescatar_grabaciones_locales()

    clases_bd = database.listar_clases()
    clases_reales = [
        c for c in clases_bd
        if (c.get("estado") in ("COMPLETADA", "ERROR_REMUXING") or (c.get("estado") == "PENDIENTE" and (c.get("ruta_archivo") or c.get("analisis_json")))) and "prueba" not in c.get("id_clase", "").lower()
    ]

    # Obtener lista de tareas encoladas en NotebookLM
    try:
        cola_nlm = {t["id_clase"] for t in database.obtener_reintentos_notebooklm_listos()}
    except Exception:
        cola_nlm = set()

    datos = []
    ids_vistos = set()
    for c in clases_reales:
        id_clase = c["id_clase"]
        titulo = c["titulo_original"]
        if id_clase in ids_vistos:
            continue
        ids_vistos.add(id_clase)

        fecha_raw = c.get("fecha_grabacion") or ""
        transversal = c.get("transversal") or "General"
        nivel = c.get("nivel") or 1
        notebook_url = c.get("notebook_url") or "https://notebooklm.google.com/"

        analisis = {}
        if c.get("analisis_json"):
            try:
                analisis = json.loads(c["analisis_json"])
            except Exception:
                pass

        # Extracción automática de Mentor
        mentor = c.get("mentor") or analisis.get("mentor_identificado") or ""
        if not mentor and "mentor:" in titulo.lower():
            m_ext = re.search(r"\(Mentor:\s*([^)]+)\)", titulo, flags=re.IGNORECASE)
            if m_ext:
                mentor = m_ext.group(1).strip()
        if not mentor and "mentoría" in titulo.lower():
            m_alt = re.search(r"mentor[ií]a(?:\s+en\s+vivo)?:\s*([^-:(]+)", titulo, flags=re.IGNORECASE)
            if m_alt:
                mentor = m_alt.group(1).strip()

        es_mentoria = (
            transversal == "Mentorías"
            or "mentoria" in id_clase.lower()
            or "mentoría" in titulo.lower()
            or bool(mentor and mentor not in ("General", "Universidad Online"))
        )

        fecha_legible = ""
        if fecha_raw and len(fecha_raw) >= 10:
            try:
                dt_f = datetime.datetime.fromisoformat(fecha_raw.replace("Z", "+00:00"))
                fecha_legible = dt_f.strftime("%d/%m/%Y")
            except Exception:
                fecha_legible = fecha_raw[:10]
        else:
            fecha_legible = "Reciente"

        # Audio / Podcast: Expansión total (eliminación del límite 20%)
        podcast_rel = ""
        podcast_path = c.get("podcast_archivo") or ""
        if not podcast_path:
            posibles = (
                glob.glob(os.path.join(BASE_DIR, "grabaciones", "**", f"*{id_clase}*.m4a"), recursive=True)
                + glob.glob(os.path.join(BASE_DIR, "grabaciones", "**", f"*{id_clase}*.mp3"), recursive=True)
            )
            if posibles:
                podcast_path = posibles[0]
        if podcast_path and os.path.exists(podcast_path):
            try:
                podcast_rel = os.path.relpath(podcast_path, BASE_DIR).replace("\\", "/")
            except Exception:
                podcast_rel = ""

        tiene_audio = bool(podcast_rel or (notebook_url and notebook_url != "https://notebooklm.google.com/"))
        audio_encolado = id_clase in cola_nlm

        vc = analisis.get("vertical_creacion", {})
        vcom = analisis.get("vertical_comercializacion", {})

        imp_creacion = c.get("importancia_creacion") or vc.get("porcentaje_importancia") or 75
        pareto_creacion = bool(c.get("pareto_creacion") if c.get("pareto_creacion") is not None else vc.get("es_pareto_20_vital", True))

        imp_com = c.get("importancia_comercializacion") or vcom.get("porcentaje_importancia") or 75
        pareto_com = bool(c.get("pareto_comercializacion") if c.get("pareto_comercializacion") is not None else vcom.get("es_pareto_20_vital", True))

        # Clase Clave (Impacto Alto): Distinción visual elegante
        es_clave = pareto_creacion or pareto_com or imp_creacion >= 85 or imp_com >= 85

        contenido_md = ""
        posibles_md = glob.glob(os.path.join(BASE_DIR, "grabaciones", "**", f"Ficha_Didactica_{id_clase}.md"), recursive=True)
        if posibles_md and os.path.exists(posibles_md[0]):
            try:
                with open(posibles_md[0], "r", encoding="utf-8") as f_md:
                    contenido_md = f_md.read()
            except Exception:
                pass

        if not contenido_md:
            contenido_md = f"# 🎓 {titulo}\n\n{analisis.get('resumen_didactico', 'Clase grabada y procesada en Universidad Online.')}"

        flashcards = sintetizar_flashcards(analisis, titulo, transversal)

        # Asignar a Fase del Mapa Panorámico
        fase_id = 1
        t_low = (transversal + " " + titulo).lower()
        if "mindset" in t_low or "mentalidad" in t_low or "onboarding" in t_low or nivel == 1:
            fase_id = 1
        elif "crea" in t_low or "producto" in t_low or "curso" in t_low or "canva" in t_low or pareto_creacion:
            fase_id = 2
        elif "comercializa" in t_low or "venta" in t_low or "objeci" in t_low or "prospecc" in t_low:
            fase_id = 3
        elif "lanzamiento" in t_low or "escala" in t_low or "funnel" in t_low or "factura" in t_low or pareto_com:
            fase_id = 4
        if es_mentoria or transversal == "Playbooks":
            fase_id = 5

        datos.append({
            "id": id_clase,
            "titulo": titulo,
            "fecha_iso": fecha_raw,
            "fecha": fecha_legible,
            "transversal": "Mentorías" if es_mentoria else transversal,
            "es_mentoria": es_mentoria,
            "mentor": mentor or ("Universidad Online" if not es_mentoria else "Mentor Experto"),
            "nivel": nivel,
            "fase_mapa": fase_id,
            "es_clave": es_clave,
            "notebook_url": notebook_url,
            "podcast_rel": podcast_rel,
            "tiene_audio": tiene_audio,
            "audio_encolado": audio_encolado,
            "creacion": {
                "importancia": imp_creacion,
                "motivo": vc.get("por_que_y_cuando_ver", "Estructuración y aplicación práctica de alto nivel."),
            },
            "comercializacion": {
                "importancia": imp_com,
                "motivo": vcom.get("por_que_y_cuando_ver", "Adquisición de clientes, cierre de ventas y conversión."),
            },
            "resumen": analisis.get("resumen_didactico", "Sesión grabada y procesada en tu plataforma."),
            "infografia": analisis.get("infografia_pasos", []),
            "checklist": analisis.get("checklist_15_min", []),
            "quiz": analisis.get("quiz_practico", []),
            "flashcards": flashcards,
            "mermaid": analisis.get("mapa_mental_mermaid", ""),
            "markdown": contenido_md,
            "telegram_url": c.get("telegram_url") or "",
            "telegram_app_url": c.get("telegram_app_url") or "",
            "telegram_web_url": c.get("telegram_web_url") or "",
            "video_nube_url": (c.get("telegram_url") or c.get("telegram_web_url") or c.get("telegram_app_url") or "").strip(),
        })

    return datos


def construir_datos_capsulas() -> List[Dict[str, Any]]:
    filas = database.listar_capsulas_mentores()
    resultado = []
    for r in filas:
        analisis = {}
        if r.get("analisis_json"):
            try:
                analisis = json.loads(r["analisis_json"])
            except Exception:
                pass

        titulo = r.get("titulo") or "Contenido de Mentor"
        mentor = r.get("mentor") or "Mentor"
        flashcards = sintetizar_flashcards(analisis, titulo, f"Mentor {mentor}")

        resultado.append({
            "id": r["id_capsula"],
            "mentor": mentor,
            "grupo": r.get("grupo_origen") or "",
            "tipo": r.get("tipo") or "TIP",
            "titulo": titulo,
            "resumen": r.get("contenido_resumen") or analisis.get("resumen_didactico") or "",
            "fecha_iso": r.get("fecha_mensaje_iso") or "",
            "fecha": r.get("fecha_legible") or "",
            "hora": r.get("hora_legible") or "",
            "infografia": analisis.get("infografia_pasos", []),
            "checklist": analisis.get("checklist_15_min", []),
            "quiz": analisis.get("quiz_practico", []),
            "flashcards": flashcards,
            "mermaid": analisis.get("mapa_mental_mermaid", ""),
            "notebook_url": r.get("notebook_url") or "https://notebooklm.google.com/",
        })
    return resultado


def publicar_en_github_pages() -> bool:
    print("\n[Publicador Web] Iniciando publicación de la App Web en GitHub Pages...")
    portable_git = os.path.join(BASE_DIR, "git", "cmd")
    if os.path.exists(portable_git) and portable_git not in os.environ.get("PATH", ""):
        os.environ["PATH"] = portable_git + os.pathsep + os.environ.get("PATH", "")

    try:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", "*"],
            cwd=BASE_DIR,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    cfg_file = os.path.join(BASE_DIR, "config.json")
    github_token = ""
    github_repo_url = "https://github.com/cursosfamiliaorellana-hue/universidad-online.git"
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                github_token = (cfg.get("github_token") or "").strip()
                github_repo_url = (cfg.get("github_repo_url") or github_repo_url).strip()
        except Exception:
            pass

    if github_token:
        url_autenticada = re.sub(r"https?://(?:[^@]+@)?", f"https://{github_token}@", github_repo_url)
        try:
            subprocess.run(
                ["git", "remote", "set-url", "origin", url_autenticada],
                cwd=BASE_DIR,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comandos = [
        "git add index.html app_web data.json database.json Mis_Rutas_80_20_UniversidadOnline.html sw.js manifest.json icon-192.png icon-512.png",
        f'git commit -m "Auto-update App Web LMS [{ts}]"',
        "git push origin main",
    ]
    exito_total = True
    for cmd in comandos:
        try:
            res = subprocess.run(
                cmd,
                cwd=BASE_DIR,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            salida = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            salida_lower = salida.lower()
            if res.returncode != 0:
                if "nothing to commit" in salida_lower or "nada para confirmar" in salida_lower or "clean" in salida_lower:
                    continue
                print(f"[Publicador Web] [AVISO] en '{cmd}': {salida}")
                if "git push" in cmd:
                    exito_total = False
        except Exception as e_cmd:
            print(f"[Publicador Web] [AVISO] Error ejecutando '{cmd}': {e_cmd}")
            exito_total = False

    if exito_total:
        print(f"[Publicador Web] [OK] ¡App Web publicada exitosamente en GitHub Pages! [{ts}]")
    return exito_total


def generar_html_plataforma(clases_data: List[Dict[str, Any]], capsulas_data: List[Dict[str, Any]], timestamp: str) -> str:
    clases_json = json.dumps(clases_data, ensure_ascii=False)
    capsulas_json = json.dumps(capsulas_data, ensure_ascii=False)
    fecha_generacion = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    mentores_set = sorted({
        m for m in (
            [c.get("mentor", "") for c in clases_data if c.get("es_mentoria")]
            + [cap.get("mentor", "") for cap in capsulas_data]
            + [m.get("nombre_mentor", "") for m in database.listar_mentores_grupos()]
        )
        if m and m not in ("General", "Universidad Online")
    })
    opciones_mentores_html = "\n".join([f'<option value="{m}">🎙️ Mentor: {m}</option>' for m in mentores_set])

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  
  <title>Universidad Online - LMS Interactivo, Flashcards & Mapa Panorámico</title>
  <link rel="manifest" href="manifest.json">
  <meta name="theme-color" content="#0b0f19">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{ startOnLoad: false, theme: 'dark' }});</script>
  <style>
    :root {{
      --bg: #0b0f19; --card-bg: #151d2e; --card-border: #243048;
      --text: #f8fafc; --text-muted: #94a3b8; --primary: #6366f1;
      --vital-color: #f59e0b; --vital-bg: rgba(245, 158, 11, 0.12);
      --success: #10b981; --success-bg: rgba(16, 185, 129, 0.15);
      --card-radius: 14px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 16px; line-height: 1.5; }}
    
    /* Header & Progress Tracker */
    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border); padding-bottom: 16px; margin-bottom: 18px; flex-wrap: wrap; gap: 12px; }}
    .logo-box h1 {{ font-size: 22px; font-weight: 800; display: flex; align-items: center; gap: 8px; }}
    .badge-lms {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 11px; font-weight: 800; padding: 3px 10px; border-radius: 999px; }}
    
    .progress-box {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 12px 18px; min-width: 280px; flex: 1; max-width: 480px; }}
    .progress-labels {{ display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; margin-bottom: 6px; color: var(--text-muted); }}
    .progress-bar-bg {{ background: rgba(255,255,255,0.08); border-radius: 999px; height: 10px; overflow: hidden; }}
    .progress-bar-fill {{ background: linear-gradient(90deg, #10b981, #6366f1); height: 100%; width: 0%; transition: width 0.4s ease; }}
    
    /* Mapa Panorámico (Roadmap de 5 Fases) */
    .panoramic-section {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 16px; padding: 18px; margin-bottom: 22px; }}
    .panoramic-header {{ display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }}
    .panoramic-title {{ font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px; color: #e2e8f0; }}
    .panoramic-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 14px; }}
    .phase-step {{ background: rgba(0,0,0,0.28); border: 1px solid var(--card-border); border-radius: 12px; padding: 12px; cursor: pointer; transition: all 0.2s; position: relative; }}
    .phase-step:hover, .phase-step.active {{ border-color: var(--primary); background: rgba(99, 102, 241, 0.12); }}
    .phase-num {{ font-size: 11px; font-weight: 800; color: #a5b4fc; text-transform: uppercase; margin-bottom: 4px; }}
    .phase-name {{ font-size: 13px; font-weight: 700; color: var(--text); line-height: 1.3; }}
    .phase-stat {{ font-size: 11px; color: var(--text-muted); margin-top: 6px; }}

    /* Toolbar & Filtros */
    .toolbar {{ display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }}
    .search-input, .filter-select {{ background: var(--card-bg); border: 1px solid var(--card-border); color: var(--text); padding: 11px 14px; border-radius: 10px; font-size: 14px; }}
    .search-input {{ flex: 1; min-width: 220px; }}
    
    /* Tabs */
    .tabs {{ display: flex; gap: 8px; border-bottom: 2px solid var(--card-border); margin-bottom: 20px; overflow-x: auto; padding-bottom: 4px; }}
    .tab-btn {{ background: transparent; border: none; color: var(--text-muted); padding: 10px 14px; font-size: 13px; font-weight: 700; cursor: pointer; border-bottom: 3px solid transparent; white-space: nowrap; }}
    .tab-btn.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
    .tab-content {{ display: none; }}
    .tab-content.active {{ display: block; }}
    .section-title {{ font-size: 16px; font-weight: 800; margin: 18px 0 12px; color: var(--primary); }}
    
    /* Tarjetas de Clase */
    .class-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}
    .class-card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--card-radius); padding: 18px; display: flex; flex-direction: column; justify-content: space-between; position: relative; transition: transform 0.15s, border-color 0.15s; }}
    .class-card:hover {{ border-color: rgba(99, 102, 241, 0.5); transform: translateY(-2px); }}
    
    /* Distintivo de Clase Clave */
    .class-card.vital {{ border: 1.5px solid var(--vital-color); background: linear-gradient(180deg, var(--vital-bg) 0%, var(--card-bg) 40%); }}
    .badge-vital {{ background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 6px; display: inline-flex; align-items: center; gap: 4px; margin-bottom: 8px; }}
    
    /* Estado Estudiada (Local Storage) */
    .class-card.estudiada {{ border-color: var(--success) !important; background: linear-gradient(180deg, var(--success-bg) 0%, var(--card-bg) 40%); }}
    .badge-estudiada {{ background: var(--success); color: #000; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 6px; margin-left: 6px; }}

    .card-top-row {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }}
    .card-meta {{ font-size: 12px; color: var(--text-muted); }}
    .card-title {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; line-height: 1.35; }}
    
    /* Tags de Mentor y Transversal */
    .tag-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
    .card-transversal {{ background: rgba(99, 102, 241, 0.18); color: #a5b4fc; font-size: 11px; padding: 3px 8px; border-radius: 6px; font-weight: 600; }}
    .card-mentor {{ background: rgba(16, 185, 129, 0.18); color: #34d399; font-size: 11px; padding: 3px 8px; border-radius: 6px; font-weight: 700; }}
    .card-date {{ background: rgba(255, 255, 255, 0.08); color: #cbd5e1; font-size: 11px; padding: 3px 8px; border-radius: 6px; font-weight: 600; }}
    
    .card-motivo {{ font-size: 13px; color: #cbd5e1; margin-bottom: 14px; background: rgba(0,0,0,0.25); padding: 10px; border-radius: 8px; border-left: 3px solid var(--primary); }}
    
    /* Acciones & Checklist */
    .card-actions {{ display: flex; gap: 8px; margin-top: auto; flex-wrap: wrap; }}
    .btn-detail {{ flex: 1; background: var(--primary); color: #fff; border: none; padding: 9px 12px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; text-align: center; }}
    .btn-card-tg {{ background: #0088cc; color: #fff; border: none; padding: 9px 12px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }}
    .btn-card-audio {{ background: #059669; color: #fff; border: none; padding: 9px 12px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; text-decoration: none; }}
    
    .chk-container {{ display: flex; align-items: center; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--card-border); font-size: 12px; color: var(--text-muted); cursor: pointer; user-select: none; }}
    .chk-input {{ width: 17px; height: 17px; accent-color: var(--success); cursor: pointer; }}

    /* Modal de Detalle LMS & Flashcards */
    .modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.88); z-index: 999; justify-content: center; align-items: center; padding: 12px; }}
    .modal-overlay.open {{ display: flex; }}
    .modal-card {{ background: var(--card-bg); border: 1px solid var(--card-border); width: 100%; max-width: 860px; max-height: 92vh; border-radius: 16px; overflow-y: auto; padding: 24px; position: relative; }}
    .modal-close {{ position: absolute; top: 14px; right: 16px; font-size: 26px; color: var(--text-muted); background: none; border: none; cursor: pointer; }}

    /* Flashcards Interactivas */
    .fc-section {{ background: rgba(0,0,0,0.3); border: 1px solid var(--card-border); border-radius: 14px; padding: 18px; margin: 20px 0; }}
    .fc-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .fc-counter {{ font-size: 12px; font-weight: 700; color: #a5b4fc; }}
    .flashcard-wrapper {{ perspective: 1000px; min-height: 180px; margin-bottom: 12px; }}
    .flashcard-inner {{ width: 100%; min-height: 180px; border-radius: 12px; border: 1.5px solid #4338ca; background: #1e1b4b; padding: 20px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; cursor: pointer; transition: transform 0.3s; user-select: none; }}
    .flashcard-inner.flipped {{ background: #064e3b; border-color: #059669; }}
    .fc-badge {{ font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 999px; margin-bottom: 10px; background: rgba(255,255,255,0.12); color: #fff; }}
    .fc-prompt {{ font-size: 15px; font-weight: 700; line-height: 1.4; color: #f8fafc; }}
    .fc-answer {{ font-size: 14px; line-height: 1.4; color: #a7f3d0; margin-top: 10px; display: none; }}
    .flashcard-inner.flipped .fc-answer {{ display: block; }}
    .flashcard-inner.flipped .fc-hint {{ display: none; }}
    .fc-hint {{ font-size: 11px; color: #94a3b8; margin-top: 10px; }}
    .fc-controls {{ display: flex; justify-content: center; gap: 10px; }}
    .fc-btn {{ background: rgba(255,255,255,0.08); color: var(--text); border: 1px solid var(--card-border); padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; }}
    .fc-btn:hover {{ background: var(--primary); }}

    .infografia-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 14px 0; }}
    .info-block {{ background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px; text-align: center; }}
    .quiz-box {{ background: rgba(0,0,0,0.25); border-radius: 10px; padding: 14px; margin: 12px 0; border: 1px solid var(--card-border); }}
    .quiz-opt {{ display: block; width: 100%; text-align: left; background: var(--card-bg); border: 1px solid var(--card-border); padding: 10px; margin-top: 6px; border-radius: 8px; color: var(--text); cursor: pointer; }}
    .quiz-opt.correct {{ background: rgba(16, 185, 129, 0.25); border-color: var(--success); }}
    .quiz-opt.wrong {{ background: rgba(239, 68, 68, 0.25); border-color: #ef4444; }}
  </style>
</head>
<body>
  <script>
    if ('serviceWorker' in navigator) {{
      window.addEventListener('load', () => {{
        navigator.serviceWorker.register('./sw.js?v={timestamp}').then(reg => reg.update());
      }});
    }}
  </script>

  <!-- Header con Progreso de Estudio -->
  <div class="header">
    <div class="logo-box">
      <h1>🎓 Universidad Online <span class="badge-lms">LMS Interactivo</span></h1>
      <p style="color:var(--text-muted); font-size:13px; margin-top:4px;">
        {len(clases_data)} Masterclasses & Mentorías • {len(capsulas_data)} Cápsulas IA • Actualizado: {fecha_generacion}
      </p>
    </div>
    
    <div class="progress-box">
      <div class="progress-labels">
        <span>🎯 TU PROGRESO DE ESTUDIO</span>
        <span id="progressText">0 / {len(clases_data)} (0%)</span>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="progressBarFill"></div>
      </div>
    </div>
  </div>

  <!-- MAPA PANORÁMICO DE ESTUDIO (Ruta Guiada de 5 Fases) -->
  <div class="panoramic-section">
    <div class="panoramic-header" onclick="togglePanoramic()">
      <div class="panoramic-title">
        <span>🗺️ MAPA PANORÁMICO DE ESTUDIO (Ruta Guiada Paso a Paso)</span>
      </div>
      <span style="font-size:12px; color:var(--text-muted);" id="panoramicToggleIcon">▼ Desplegar</span>
    </div>
    <div class="panoramic-grid" id="panoramicGrid">
      <div class="phase-step active" onclick="filtrarPorFase(0, this)">
        <div class="phase-num">Vista Global</div>
        <div class="phase-name">🌟 Todo el Ecosistema</div>
        <div class="phase-stat" id="stat-fase-0">{len(clases_data)} Clases</div>
      </div>
      <div class="phase-step" onclick="filtrarPorFase(1, this)">
        <div class="phase-num">Fase 1</div>
        <div class="phase-name">🧭 Fundamentos & Mindset</div>
        <div class="phase-stat" id="stat-fase-1">Bases del Negocio</div>
      </div>
      <div class="phase-step" onclick="filtrarPorFase(2, this)">
        <div class="phase-num">Fase 2</div>
        <div class="phase-name">🛠️ Creación & Oferta</div>
        <div class="phase-stat" id="stat-fase-2">Cursos & Empaquetado</div>
      </div>
      <div class="phase-step" onclick="filtrarPorFase(3, this)">
        <div class="phase-num">Fase 3</div>
        <div class="phase-name">📢 Comercialización & Ventas</div>
        <div class="phase-stat" id="stat-fase-3">Cierre & Embudos</div>
      </div>
      <div class="phase-step" onclick="filtrarPorFase(4, this)">
        <div class="phase-num">Fase 4</div>
        <div class="phase-name">🚀 Lanzamientos & Escala</div>
        <div class="phase-stat" id="stat-fase-4">Tráfico & Facturación</div>
      </div>
      <div class="phase-step" onclick="filtrarPorFase(5, this)">
        <div class="phase-num">Fase 5</div>
        <div class="phase-name">🎙️ Mentorías & Playbooks</div>
        <div class="phase-stat" id="stat-fase-5">Tácticas Avanzadas</div>
      </div>
    </div>
  </div>

  <!-- Buscador y Filtros -->
  <div class="toolbar">
    <input type="text" id="searchInput" class="search-input" placeholder="🔍 Buscar por tema, mentor, concepto clave..." oninput="filtrarTodo()">
    <select id="filterMentor" class="filter-select" onchange="filtrarTodo()">
      <option value="todos">👥 Todos los Mentores</option>
      {opciones_mentores_html}
    </select>
    <select id="filterTransversal" class="filter-select" onchange="filtrarTodo()">
      <option value="todos">🏷️ Todas las Categorías</option>
      <option value="Mentorías">🎙️ Mentorías</option>
      <option value="Inteligencia Artificial">Inteligencia Artificial</option>
      <option value="Marketing Digital">Marketing Digital</option>
      <option value="Ventas">Ventas y Comercialización</option>
      <option value="Playbooks">Playbooks & Guías</option>
    </select>
  </div>

  <!-- Pestañas Principales -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('tab-recientes', this)">🔥 Recientemente Subidas</button>
    <button class="tab-btn" onclick="switchTab('tab-mentorias', this)">🎙️ Mentorías Grabadas</button>
    <button class="tab-btn" onclick="switchTab('tab-capsulas', this)">💡 Tips & Cápsulas de Mentores</button>
    <button class="tab-btn" onclick="switchTab('tab-noticias', this)">📰 Noticias & Avisos</button>
    <button class="tab-btn" onclick="switchTab('tab-creacion', this)">✏️ Creación</button>
    <button class="tab-btn" onclick="switchTab('tab-comercializacion', this)">📈 Ventas</button>
  </div>

  <div id="tab-recientes" class="tab-content active">
    <div class="section-title">🔥 ÚLTIMAS SESIONES GRABADAS</div>
    <div class="class-grid" id="grid-recientes"></div>
  </div>

  <div id="tab-mentorias" class="tab-content">
    <div class="section-title">🎙️ MENTORÍAS EN VIVO Y SESIONES ESTRATÉGICAS</div>
    <div class="class-grid" id="grid-mentorias"></div>
  </div>

  <div id="tab-capsulas" class="tab-content">
    <div class="section-title">💡 CÁPSULAS EDUCATIVAS Y FLASHCARDS DE MENTORES</div>
    <div class="class-grid" id="grid-capsulas"></div>
  </div>

  <div id="tab-noticias" class="tab-content">
    <div class="section-title">📰 NOTICIAS, CAMBIOS DE HORARIO Y AVISOS</div>
    <div class="class-grid" id="grid-noticias"></div>
  </div>

  <div id="tab-creacion" class="tab-content">
    <div class="section-title">✏️ CREACIÓN DE PRODUCTOS Y ESTRUCTURA DIDÁCTICA</div>
    <div class="class-grid" id="grid-creacion"></div>
  </div>

  <div id="tab-comercializacion" class="tab-content">
    <div class="section-title">📈 COMERCIALIZACIÓN, TRÁFICO Y CIERRE DE VENTAS</div>
    <div class="class-grid" id="grid-comercializacion"></div>
  </div>

  <!-- Modal Detallado con Flashcards y Estudio -->
  <div class="modal-overlay" id="modalDetail" onclick="if(event.target===this) cerrarModal()">
    <div class="modal-card">
      <button class="modal-close" onclick="cerrarModal()">&times;</button>
      <div id="modalContent"></div>
    </div>
  </div>

  <script>
    let CLASES = {clases_json};
    let CAPSULAS = {capsulas_json};

    // Sincronización dinámica desde la Nube (Cloud Offloading & Serverless Hydration)
    async function sincronizarDesdeNube() {{
      try {{
        let resp = await fetch('data.json?v=' + Date.now());
        if (!resp.ok) {{
          resp = await fetch('database.json?v=' + Date.now());
        }}
        if (resp.ok) {{
          const payload = await resp.json();
          if (payload && payload.clases && payload.clases.length > 0) {{
            CLASES = payload.clases;
            CAPSULAS = payload.capsulas || [];
            if (typeof filtrarTodo === 'function') filtrarTodo();
            if (typeof actualizarContadoresFase === 'function') actualizarContadoresFase();
            if (typeof actualizarBarraProgreso === 'function') actualizarBarraProgreso();
          }}
        }}
      }} catch(e) {{
        console.log('[LMS Cloud] Operando en modo local/fallback.');
      }}
    }}
    window.addEventListener('DOMContentLoaded', sincronizarDesdeNube);

    let FASE_ACTIVA = 0;
    let FLASHCARDS_ACTUALES = [];
    let FC_INDEX = 0;

    // -------------------------------------------------------------
    // LOCAL STORAGE: CHECKLIST DE ESTUDIO
    // -------------------------------------------------------------
    function getEstudiadas() {{
      try {{
        return JSON.parse(localStorage.getItem('uo_estudiadas') || '{{}}');
      }} catch(e) {{
        return {{}};
      }}
    }}

    function toggleEstudiada(id, chk) {{
      const estudiadas = getEstudiadas();
      if (chk.checked) {{
        estudiadas[id] = true;
      }} else {{
        delete estudiadas[id];
      }}
      localStorage.setItem('uo_estudiadas', JSON.stringify(estudiadas));
      actualizarProgreso();
      actualizarEstilosEstudiadas();
    }}

    function actualizarProgreso() {{
      const estudiadas = getEstudiadas();
      const count = Object.keys(estudiadas).length;
      const total = CLASES.length;
      const pct = total > 0 ? Math.round((count / total) * 100) : 0;

      const txt = document.getElementById('progressText');
      const bar = document.getElementById('progressBarFill');
      if (txt) txt.innerText = `${{count}} / ${{total}} (${{pct}}%)`;
      if (bar) bar.style.width = `${{pct}}%`;
    }}

    function actualizarEstilosEstudiadas() {{
      const estudiadas = getEstudiadas();
      document.querySelectorAll('.class-card[data-id]').forEach(card => {{
        const cid = card.getAttribute('data-id');
        const chk = card.querySelector('.chk-input');
        if (estudiadas[cid]) {{
          card.classList.add('estudiada');
          if (chk) chk.checked = true;
        }} else {{
          card.classList.remove('estudiada');
          if (chk) chk.checked = false;
        }}
      }});
    }}

    // -------------------------------------------------------------
    // MAPA PANORÁMICO
    // -------------------------------------------------------------
    function togglePanoramic() {{
      const grid = document.getElementById('panoramicGrid');
      const icon = document.getElementById('panoramicToggleIcon');
      if (grid.style.display === 'none') {{
        grid.style.display = 'grid';
        icon.innerText = '▲ Ocultar';
      }} else {{
        grid.style.display = 'none';
        icon.innerText = '▼ Desplegar';
      }}
    }}

    function filtrarPorFase(faseNum, btn) {{
      FASE_ACTIVA = faseNum;
      document.querySelectorAll('.phase-step').forEach(s => s.classList.remove('active'));
      if (btn) btn.classList.add('active');
      filtrarTodo();
    }}

    function switchTab(tabId, btn) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(tabId).classList.add('active');
    }}

    // -------------------------------------------------------------
    // RENDERIZADO DE TARJETAS
    // -------------------------------------------------------------
    function cardClaseHtml(c) {{
      const estudiadas = getEstudiadas();
      const esEst = Boolean(estudiadas[c.id]);

      return `
        <div class="class-card ${{c.es_clave ? 'vital' : ''}} ${{esEst ? 'estudiada' : ''}}" data-id="${{c.id}}">
          <div>
            <div class="card-top-row">
              <div class="card-meta"><span>📅 ${{c.fecha}}</span> • <span>Nivel ${{c.nivel}}</span></div>
              ${{c.es_clave ? `<span class="badge-vital">⭐ Clase Clave</span>` : ''}}
            </div>
            
            <div class="card-title">${{c.titulo}}</div>
            
            <div class="tag-row">
              <span class="card-transversal">${{c.transversal}}</span>
              ${{c.mentor ? `<span class="card-mentor">🎙️ ${{c.mentor}}</span>` : ''}}
              ${{c.tiene_audio ? `<span class="card-date" style="background:#065f46; color:#6ee7b7;">🎧 Audio Listo</span>` : (c.audio_encolado ? `<span class="card-date" style="background:#854d0e; color:#fde047;">⏳ Audio en Cola</span>` : '')}}
            </div>

            <div class="card-motivo">${{c.resumen}}</div>
          </div>

          <div>
            <div class="card-actions">
              <button class="btn-detail" onclick="abrirModalClase('${{c.id}}')">🎨 Estudio & Flashcards</button>
              ${{(c.video_nube_url || c.telegram_url) ? `<a class="btn-card-tg" href="${{c.video_nube_url || c.telegram_url}}" target="_blank">🎬 Ver en Telegram</a>` : ''}}
            </div>

            <label class="chk-container">
              <input type="checkbox" class="chk-input" ${{esEst ? 'checked' : ''}} onchange="toggleEstudiada('${{c.id}}', this)">
              <span>Marcar como Estudiada / Completada</span>
            </label>
          </div>
        </div>
      `;
    }}

    function cardCapsulaHtml(cap) {{
      const icono = cap.tipo === 'NOTICIA' ? '📰 AVISO' : (cap.tipo === 'CAPSULA_PROFUNDA' ? '🧠 CÁPSULA IA' : '💡 TIP RÁPIDO');
      return `
        <div class="class-card">
          <div>
            <div class="card-top-row">
              <div class="card-meta"><span>📅 ${{cap.fecha}}</span> • <span>⏰ ${{cap.hora}}</span></div>
              <span class="card-transversal">${{icono}}</span>
            </div>
            <div class="card-title">${{cap.titulo}}</div>
            <div class="tag-row">
              <span class="card-mentor">🎙️ Mentor: ${{cap.mentor}}</span>
            </div>
            <div class="card-motivo">${{cap.resumen}}</div>
          </div>
          <div class="card-actions">
            <button class="btn-detail" onclick="abrirModalCapsula('${{cap.id}}')">🎨 Ver Flashcards & Quiz</button>
          </div>
        </div>
      `;
    }}

    // -------------------------------------------------------------
    // FILTRADO GLOBAL
    // -------------------------------------------------------------
    function filtrarTodo() {{
      const q = document.getElementById('searchInput').value.toLowerCase().trim();
      const mentorSel = document.getElementById('filterMentor').value.toLowerCase();
      const catSel = document.getElementById('filterTransversal').value.toLowerCase();

      const clasesFiltradas = CLASES.filter(c => {{
        const matchQ = !q || c.titulo.toLowerCase().includes(q) || c.resumen.toLowerCase().includes(q) || (c.mentor || '').toLowerCase().includes(q);
        const matchM = mentorSel === 'todos' || (c.mentor || '').toLowerCase().includes(mentorSel);
        const matchC = catSel === 'todos' || (c.transversal || '').toLowerCase().includes(catSel);
        const matchF = FASE_ACTIVA === 0 || c.fase_mapa === FASE_ACTIVA;
        return matchQ && matchM && matchC && matchF;
      }});

      const capsFiltradas = CAPSULAS.filter(cap => {{
        const matchQ = !q || cap.titulo.toLowerCase().includes(q) || cap.resumen.toLowerCase().includes(q) || cap.mentor.toLowerCase().includes(q);
        const matchM = mentorSel === 'todos' || cap.mentor.toLowerCase().includes(mentorSel);
        return matchQ && matchM;
      }});

      const recientes = [...clasesFiltradas].sort((a,b) => (b.fecha_iso || '').localeCompare(a.fecha_iso || ''));
      document.getElementById('grid-recientes').innerHTML = recientes.map(cardClaseHtml).join('') || '<p style="color:var(--text-muted); padding:16px;">No hay clases con este criterio.</p>';
      document.getElementById('grid-mentorias').innerHTML = recientes.filter(c => c.es_mentoria).map(cardClaseHtml).join('') || '<p style="color:var(--text-muted); padding:16px;">Sin mentorías encontradas.</p>';
      document.getElementById('grid-capsulas').innerHTML = capsFiltradas.filter(x => x.tipo !== 'NOTICIA').map(cardCapsulaHtml).join('') || '<p style="color:var(--text-muted); padding:16px;">Sin cápsulas registradas.</p>';
      document.getElementById('grid-noticias').innerHTML = capsFiltradas.filter(x => x.tipo === 'NOTICIA').map(cardCapsulaHtml).join('') || '<p style="color:var(--text-muted); padding:16px;">Sin noticias registradas.</p>';
      document.getElementById('grid-creacion').innerHTML = clasesFiltradas.filter(c => c.creacion && c.creacion.importancia >= 70).map(cardClaseHtml).join('') || '<p style="color:var(--text-muted); padding:16px;">Sin contenido de Creación.</p>';
      document.getElementById('grid-comercializacion').innerHTML = clasesFiltradas.filter(c => c.comercializacion && c.comercializacion.importancia >= 70).map(cardClaseHtml).join('') || '<p style="color:var(--text-muted); padding:16px;">Sin contenido de Ventas.</p>';

      actualizarProgreso();
      actualizarEstilosEstudiadas();
    }}

    // -------------------------------------------------------------
    // MODAL DE DETALLE LMS & FLASHCARDS
    // -------------------------------------------------------------
    function renderizarFlashcard(idx) {{
      if (!FLASHCARDS_ACTUALES || FLASHCARDS_ACTUALES.length === 0) return;
      FC_INDEX = (idx + FLASHCARDS_ACTUALES.length) % FLASHCARDS_ACTUALES.length;
      const fc = FLASHCARDS_ACTUALES[FC_INDEX];

      const box = document.getElementById('fcInner');
      const counter = document.getElementById('fcCounter');
      const badge = document.getElementById('fcBadge');
      const prompt = document.getElementById('fcPrompt');
      const ans = document.getElementById('fcAnswer');

      if (box) box.classList.remove('flipped');
      if (counter) counter.innerText = `Tarjeta ${{FC_INDEX + 1}} de ${{FLASHCARDS_ACTUALES.length}}`;
      if (badge) badge.innerText = fc.dificultad || 'Intermedia';
      if (prompt) prompt.innerText = fc.pregunta;
      if (ans) ans.innerText = fc.respuesta;
    }}

    function flipCard() {{
      const box = document.getElementById('fcInner');
      if (box) box.classList.toggle('flipped');
    }}

    function prevCard() {{
      renderizarFlashcard(FC_INDEX - 1);
    }}

    function nextCard() {{
      renderizarFlashcard(FC_INDEX + 1);
    }}

    function renderizarDetalleModal(item) {{
      FLASHCARDS_ACTUALES = item.flashcards || [];
      FC_INDEX = 0;

      let fcHtml = '';
      if (FLASHCARDS_ACTUALES.length > 0) {{
        fcHtml = `
          <div class="fc-section">
            <div class="fc-header">
              <span style="font-size:14px; font-weight:800; color:#a5b4fc;">🃏 FLASHCARDS DE APRENDIZAJE ACTIVO</span>
              <span class="fc-counter" id="fcCounter">Tarjeta 1 de ${{FLASHCARDS_ACTUALES.length}}</span>
            </div>
            <div class="flashcard-wrapper" onclick="flipCard()">
              <div class="flashcard-inner" id="fcInner">
                <span class="fc-badge" id="fcBadge">${{FLASHCARDS_ACTUALES[0].dificultad || 'Básica'}}</span>
                <div class="fc-prompt" id="fcPrompt">${{FLASHCARDS_ACTUALES[0].pregunta}}</div>
                <div class="fc-hint">💡 Clic para voltear y revelar la respuesta</div>
                <div class="fc-answer" id="fcAnswer">${{FLASHCARDS_ACTUALES[0].respuesta}}</div>
              </div>
            </div>
            <div class="fc-controls">
              <button class="fc-btn" onclick="prevCard()">⬅️ Anterior</button>
              <button class="fc-btn" onclick="flipCard()">🔄 Voltear</button>
              <button class="fc-btn" onclick="nextCard()">Siguiente ➡️</button>
            </div>
          </div>
        `;
      }}

      let infoHtml = '';
      if (item.infografia && item.infografia.length > 0) {{
        infoHtml = `<h3 style="margin-top:20px;">🎨 Infografía Paso a Paso</h3><div class="infografia-grid">` +
          item.infografia.map(p => `<div class="info-block"><div style="font-size:26px;">${{p.icono || '📌'}}</div><b>${{p.titulo}}</b><p style="font-size:12px; color:#94a3b8; margin-top:4px;">${{p.explicacion}}</p></div>`).join('') + `</div>`;
      }}

      let checkHtml = '';
      if (item.checklist && item.checklist.length > 0) {{
        checkHtml = `<h3 style="margin-top:20px;">⚡ Checklist de Implementación (15 Min)</h3>` +
          item.checklist.map(ch => `<div style="padding:10px; background:rgba(0,0,0,0.25); margin-top:6px; border-radius:8px;">✅ ${{ch}}</div>`).join('');
      }}

      let quizHtml = '';
      if (item.quiz && item.quiz.length > 0) {{
        quizHtml = `<h3 style="margin-top:20px;">🎯 Quiz de Autoevaluación Práctica</h3>` +
          item.quiz.map((q, i) => `
            <div class="quiz-box">
              <b>${{i+1}}. ${{q.pregunta}}</b>
              ${{(q.opciones || []).map(op => `<button class="quiz-opt" onclick="verificarOp(this, '${{op.trim().charAt(0)}}', '${{q.respuesta_correcta}}')">${{op}}</button>`).join('')}}
              <div class="exp-msg" style="display:none; margin-top:8px; font-size:12px; color:#34d399;">💡 Explicación: ${{q.explicacion || 'Respuesta correcta: ' + q.respuesta_correcta}}</div>
            </div>
          `).join('');
      }}

      let mermaidHtml = item.mermaid ? `<h3 style="margin-top:20px;">🗺️ Mapa Mental</h3><div class="mermaid">${{item.mermaid}}</div>` : '';

      // Reproductor de Audio
      let audioHtml = '';
      if (item.podcast_rel) {{
        audioHtml = `
          <div style="background:rgba(5, 150, 105, 0.15); border:1px solid #059669; border-radius:10px; padding:12px; margin:14px 0;">
            <b style="color:#34d399; font-size:13px;">🎧 Reproductor de Audio Resumen (NotebookLM):</b>
            <audio controls style="width:100%; margin-top:8px;" src="${{item.podcast_rel}}"></audio>
          </div>
        `;
      }}

      document.getElementById('modalContent').innerHTML = `
        <h2>${{item.titulo}}</h2>
        <p style="color:#94a3b8; font-size:13px; margin:6px 0 14px;">
          🎙️ ${{item.mentor || 'Universidad Online'}} • 📅 ${{item.fecha}} • 🏷️ ${{item.transversal}}
        </p>

        <div style="display:flex; gap:10px; margin: 12px 0 16px; flex-wrap:wrap;">
          ${{(item.video_nube_url || item.telegram_url) ? `<a class="btn-card-tg" style="padding:10px 16px; font-size:14px; border-radius:8px;" href="${{item.video_nube_url || item.telegram_url}}" target="_blank">🎬 Ver en Telegram (Nube)</a>` : ''}}
          ${{item.notebook_url && item.notebook_url.startsWith('http') ? `<a class="btn-card-tg" style="background:#4338ca; padding:10px 16px; font-size:14px; border-radius:8px;" href="${{item.notebook_url}}" target="_blank">🧠 Cuaderno NotebookLM</a>` : ''}}
        </div>

        ${{audioHtml}}
        ${{fcHtml}}

        <p style="background:rgba(0,0,0,0.3); padding:14px; border-radius:10px; line-height:1.6;">${{item.resumen}}</p>
        ${{infoHtml}}
        ${{checkHtml}}
        ${{mermaidHtml}}
        ${{quizHtml}}
      `;
      document.getElementById('modalDetail').classList.add('open');
      try {{ mermaid.run(); }} catch(e) {{}}
    }}

    function verificarOp(btn, elegida, correcta) {{
      const box = btn.parentElement;
      box.querySelectorAll('.quiz-opt').forEach(b => b.disabled = true);
      if (elegida.toUpperCase() === (correcta || 'A').toUpperCase()) btn.classList.add('correct');
      else btn.classList.add('wrong');
      const exp = box.querySelector('.exp-msg');
      if (exp) exp.style.display = 'block';
    }}

    function abrirModalClase(id) {{
      const c = CLASES.find(x => x.id === id);
      if (c) renderizarDetalleModal(c);
    }}

    function abrirModalCapsula(id) {{
      const cap = CAPSULAS.find(x => x.id === id);
      if (cap) renderizarDetalleModal(cap);
    }}

    function cerrarModal() {{
      document.getElementById('modalDetail').classList.remove('open');
    }}

    window.onload = () => {{
      filtrarTodo();
      actualizarProgreso();
    }};
  </script>
</body>
</html>"""


def actualizar_service_worker(version_ts: str):
    sw_code = f"""// sw.js - Service Worker LMS Anti-Caché (Versión {version_ts})
const CACHE_NAME = 'uo-lms-{version_ts}';

self.addEventListener('install', (e) => {{
  self.skipWaiting(); 
}});

self.addEventListener('activate', (e) => {{
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.map(k => k !== CACHE_NAME && caches.delete(k))
    ))
  );
  self.clients.claim();
}});

self.addEventListener('fetch', (e) => {{
  if (e.request.mode === 'navigate' || (e.request.headers.get('accept') && e.request.headers.get('accept').includes('text/html'))) {{
    e.respondWith(
      fetch(e.request, {{ cache: 'no-store' }})
      .catch(() => caches.match(e.request))
    );
    return;
  }}
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
}});
"""
    for folder in [BASE_DIR, APP_WEB_DIR]:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "sw.js"), "w", encoding="utf-8") as f:
            f.write(sw_code)


def generar_tablero_rutas(ruta_salida: Optional[str] = None, auto_deploy: bool = True) -> str:
    path = ruta_salida or HTML_OUTPUT_PATH
    clases_data = construir_datos_clases()
    capsulas_data = construir_datos_capsulas()
    ts_actual = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    html_content = generar_html_plataforma(clases_data, capsulas_data, ts_actual)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(ROOT_INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    os.makedirs(APP_WEB_DIR, exist_ok=True)
    with open(APP_WEB_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Cloud Offload: escribir payload JSON ligero para consumo dinámico serverless
    payload_json = {
        "clases": clases_data,
        "capsulas": capsulas_data,
        "updated_at": ts_actual,
        "total_clases": len(clases_data),
        "total_capsulas": len(capsulas_data),
        "fecha_generacion": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    json_bytes = json.dumps(payload_json, ensure_ascii=False).encode("utf-8")
    try:
        with open(DATA_JSON_PATH, "wb") as f_j:
            f_j.write(json_bytes)
        with open(APP_WEB_DATA_JSON, "wb") as f_j:
            f_j.write(json_bytes)
        with open(DATABASE_JSON_PATH, "wb") as f_j:
            f_j.write(json_bytes)
        with open(APP_WEB_DATABASE_JSON, "wb") as f_j:
            f_j.write(json_bytes)
    except Exception as e_json:
        print(f"[Route Builder] Aviso escribiendo data.json: {e_json}")

    actualizar_service_worker(ts_actual)

    print(f"\n[Route Builder] ✅ Plataforma LMS Interactiva regenerada con éxito:")
    print(f"  -> Clases y Mentorías activas: {len(clases_data)}")
    print(f"  -> Flashcards & Checklist LocalStorage activos")
    print(f"  -> Sello de versión anti-caché aplicado: {ts_actual}")

    if auto_deploy:
        publicar_en_github_pages()

    # Liberación de memoria en tiempo muerto tras compilar y desplegar JSON
    gc.collect()

    return path


if __name__ == "__main__":
    generar_tablero_rutas(auto_deploy=True)
