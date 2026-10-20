"""
ai_analyzer.py - Módulo de Inteligencia Artificial (Gemini API en la Nube)
Extracción de audio ligero para NotebookLM + Análisis Pareto 80/20 + Infografías + Quizzes + Fichas Didácticas.
Compatible con Python 3.8 y 3.10+ (Windows 8 / 10 / 11) sin consumo de GPU/CPU local.
"""

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

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")

MODELOS_GEMINI = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
]


def cargar_config() -> Dict[str, Any]:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extraer_audio_ligero(ruta_mp4: str) -> Optional[str]:
    """
    Extrae un archivo MP3 comprimido para voz (mono, 32 kbps, 22050 Hz) desde el video grabado.
    Genera ~15 MB por hora, ideal para cumplir holgadamente el límite de 200 MB de NotebookLM.
    """
    if not os.path.exists(ruta_mp4):
        print(f"[!] No existe el video MP4 para extraer audio: {ruta_mp4}")
        return None

    if not os.path.exists(FFMPEG_EXE):
        raise FileNotFoundError(f"No se encontró ffmpeg.exe en: {FFMPEG_EXE}")

    ruta_mp3 = os.path.splitext(ruta_mp4)[0] + "_audio.mp3"

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", ruta_mp4,
        "-vn",
        "-ac", "1",
        "-b:a", "32k",
        "-ar", "22050",
        ruta_mp3,
    ]

    print(f"\n[AI Analyzer] Extrayendo audio ligero para NotebookLM y Gemini...")
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if os.path.exists(ruta_mp3) and os.path.getsize(ruta_mp3) > 1024:
        mb = os.path.getsize(ruta_mp3) / (1024 * 1024)
        print(f"[AI Analyzer] ✅ Audio extraído: {ruta_mp3} ({mb:.2f} MB)")
        return ruta_mp3
    else:
        print(f"[!] Error extrayendo audio con FFmpeg: {res.stderr[-300:]}")
        return None


def subir_audio_gemini(ruta_mp3: str, api_key: str) -> Optional[str]:
    """
    Sube el archivo MP3 a la File API de Gemini usando HTTP requests (resumable protocol).
    Retorna la URI del archivo en la nube de Google.
    """
    if not os.path.exists(ruta_mp3):
        return None

    tamano = os.path.getsize(ruta_mp3)
    nombre = os.path.basename(ruta_mp3)
    print(f"[AI Analyzer] Subiendo {nombre} ({tamano / (1024*1024):.1f} MB) a Gemini File API...")

    start_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(tamano),
        "X-Goog-Upload-Header-Content-Type": "audio/mp3",
        "Content-Type": "application/json",
    }
    body = json.dumps({"file": {"display_name": nombre}})

    try:
        r_start = requests.post(start_url, headers=headers, data=body, timeout=30)
        if r_start.status_code != 200:
            print(f"[!] Error iniciando upload a Gemini: {r_start.status_code} - {r_start.text[:200]}")
            return None

        upload_url = r_start.headers.get("x-goog-upload-url")
        if not upload_url:
            print("[!] No se recibió x-goog-upload-url de Gemini.")
            return None

        # Subir audio por streaming directo desde disco (0% RAM)
        upload_headers = {
            "Content-Length": str(tamano),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        with open(ruta_mp3, "rb") as f_stream:
            r_upload = requests.put(upload_url, headers=upload_headers, data=f_stream, timeout=180)
        if r_upload.status_code != 200:
            print(f"[!] Error enviando bytes a Gemini: {r_upload.status_code} - {r_upload.text[:200]}")
            return None

        file_info = r_upload.json()
        file_uri = file_info.get("file", {}).get("uri")
        print(f"[AI Analyzer] ✅ Audio cargado en Gemini. File URI: {file_uri}")
        return file_uri
    except Exception as exc:
        print(f"[!] Excepción en subir_audio_gemini: {exc}")
        return None


PROMPT_SISTEMA_PARETO = """Eres el Director Académico y Estratega de Negocios Digitales de Universidad Online.
Tu misión es analizar a fondo la Masterclass grabada y estructurar su valor de aprendizaje con la regla de Pareto 80/20 y metodología didáctica de alto impacto.

⚠️ REGLA SUPREMA DE VERACIDAD Y RIGOR ACADÉMICO (CERO ALUCINACIÓN):
- REGLA DE AUDIO MUDO: Si detectas que el audio es puro silencio, ruido estático o no hay un profesor enseñando activamente, DEBES detener tu análisis inmediatamente y devolver ÚNICAMENTE este JSON: {"error": "AUDIO_MUDO"}. No inventes absolutamente nada.
- Todo el resumen, los pasos de la infografía, el mapa mental, el checklist de 15 minutos y las preguntas del quiz DEBEN derivarse EXCLUSIVAMENTE de lo que el instructor explica y enseña en el contenido grabado de la clase.
- ESTÁ ESTRICTAMENTE PROHIBIDO inventar herramientas, pasos, anécdotas o metodologías que no se mencionen en la clase grabada. Si una herramienta o paso no se enseñó en la clase, NO la incluyas.
- Las 5 preguntas del quiz deben evaluar situaciones prácticas reales basadas en los casos y enseñanzas expuestas por el profesor en la clase.

Debes clasificar la clase en dos grandes Verticales:
1. "Vertical 1: Creación de Productos Digitales para monetizar el conocimiento" (Creación de cursos, ebooks, mentorías, membresías, empaquetado de conocimiento, estructura de contenido).
2. "Vertical 2: Comercialización de Educación (Ventas)" (Tráfico, lanzamientos, funnels, webinars, copywriting, cierre de ventas, anuncios, afiliados, escalado comercial).

También debes clasificar la clase en una "Transversal" principal (ejemplos: "Marketing Digital", "Inteligencia Artificial", "Ventas y Negociación", "Marca Personal", "Tráfico y Publicidad", "Automatizaciones y No-Code", "Mentalidad Emprendedora", "Comunicación Persuasiva", "Finanzas y Negocios", "Inglés para Negocios").

Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
{
  "transversal": "Nombre de la transversal",
  "nivel": 1, // 1: Fundamentos/Base, 2: Implementación Paso a Paso, 3: Optimización/Escala
  "resumen_didactico": "Resumen ejecutivo claro de 2 párrafos con las ideas fuerza y el objetivo de la clase.",
  "vertical_creacion": {
    "porcentaje_importancia": 85, // 0 a 100 de relevancia para crear productos digitales
    "es_pareto_20_vital": true, // true si es del 20% indispensable que da 80% resultados, o false si es 80% complementario
    "por_que_y_cuando_ver": "Explicación directa de por qué verla y en qué momento de la ruta verla."
  },
  "vertical_comercializacion": {
    "porcentaje_importancia": 90, // 0 a 100 de relevancia para comercializar y vender educación
    "es_pareto_20_vital": true, // true o false
    "por_que_y_cuando_ver": "Explicación directa."
  },
  "mapa_mental_mermaid": "graph TD\\n  A[Tema Central] --> B[Pilar 1]\\n  A --> C[Pilar 2]\\n  B --> D[Acción Clave]\\n  C --> E[Herramienta]",
  "infografia_pasos": [
    {
      "icono": "🎯",
      "titulo": "Paso 1: [Nombre corto]",
      "explicacion": "Explicación de 2 líneas sobre cómo ejecutar este paso de forma práctica."
    },
    {
      "icono": "⚙️",
      "titulo": "Paso 2: [Nombre corto]",
      "explicacion": "Explicación de 2 líneas."
    },
    {
      "icono": "🚀",
      "titulo": "Paso 3: [Nombre corto]",
      "explicacion": "Explicación de 2 líneas."
    },
    {
      "icono": "💰",
      "titulo": "Paso 4: [Nombre corto]",
      "explicacion": "Explicación de 2 líneas."
    }
  ],
  "checklist_15_min": [
    "Acción práctica 1 aplicable en 5 minutos.",
    "Acción práctica 2 aplicable en 5 minutos.",
    "Acción práctica 3 aplicable en 5 minutos."
  ],
  "quiz_practico": [
    {
      "pregunta": "¿Situación práctica planteada basada en la clase?",
      "opciones": [
        "A) Opción descriptiva",
        "B) Opción descriptiva",
        "C) Opción descriptiva"
      ],
      "respuesta_correcta": "A",
      "explicacion": "Por qué la opción A es la mejor decisión según lo enseñado."
    },
    {
      "pregunta": "Pregunta 2...",
      "opciones": ["A) ...", "B) ...", "C) ..."],
      "respuesta_correcta": "B",
      "explicacion": "..."
    },
    {
      "pregunta": "Pregunta 3...",
      "opciones": ["A) ...", "B) ...", "C) ..."],
      "respuesta_correcta": "C",
      "explicacion": "..."
    },
    {
      "pregunta": "Pregunta 4...",
      "opciones": ["A) ...", "B) ...", "C) ..."],
      "respuesta_correcta": "A",
      "explicacion": "..."
    },
    {
      "pregunta": "Pregunta 5...",
      "opciones": ["A) ...", "B) ...", "C) ..."],
      "respuesta_correcta": "B",
      "explicacion": "..."
    }
  ]
}
"""


def analizar_clase_con_gemini(
    titulo_clase: str,
    ruta_mp3: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Analiza una clase con Gemini (analizando el audio MP3 real si está disponible,
    o en base al título temático si se está preconstruyendo el tablero).
    Retorna el diccionario JSON con Pareto, Infografía, Quiz y Rutas.
    """
    cfg = cargar_config()
    key = api_key or cfg.get("gemini_api_key")
    if not key:
        print("[!] No se configuró gemini_api_key en config.json.")
        return None

    # Subir audio si se proporcionó
    file_uri = None
    if ruta_mp3 and os.path.exists(ruta_mp3):
        file_uri = subir_audio_gemini(ruta_mp3, key)

    parts: List[Dict[str, Any]] = []
    if file_uri:
        parts.append({"file_data": {"mime_type": "audio/mp3", "file_uri": file_uri}})
        texto_usuario = f"Analiza en detalle este audio de la Masterclass titulada: '{titulo_clase}'. Extrae todo el conocimiento real enseñado."
    else:
        texto_usuario = f"Analiza la Masterclass titulada: '{titulo_clase}' de Universidad Online según los estándares de la industria digital y educación online."

    parts.append({"text": PROMPT_SISTEMA_PARETO + "\n\n" + texto_usuario})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }

    print(f"\n[AI Analyzer] Consultando a Gemini para análisis Pareto 80/20 de: '{titulo_clase}'...")

    for modelo in MODELOS_GEMINI:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={key}"
        try:
            r = requests.post(url, json=payload, timeout=90)
            if r.status_code == 200:
                resp_json = r.json()
                candidatos = resp_json.get("candidates", [])
                if candidatos:
                    texto_salida = candidatos[0]["content"]["parts"][0]["text"]
                    data = json.loads(texto_salida)
                    print(f"[AI Analyzer] ✅ Análisis completado con éxito usando {modelo}.")
                    return data
            elif r.status_code == 404 or r.status_code == 503:
                print(f"[AI Analyzer] Modelo {modelo} devolvió {r.status_code}, probando alternativo...")
                continue
            else:
                print(f"[!] Gemini devolvió código {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[!] Error invocando Gemini con modelo {modelo}: {e}")

    return None


def generar_ficha_markdown(analisis: Dict[str, Any], titulo: str, fecha: str, ruta_salida: str) -> str:
    """
    Crea un documento Markdown didáctico y enriquecido con el análisis completo de la clase,
    listo para subir a NotebookLM como fuente textual complementaria.
    """
    transversal = analisis.get("transversal", "General")
    nivel = analisis.get("nivel", 1)
    resumen = analisis.get("resumen_didactico", "")

    vc = analisis.get("vertical_creacion", {})
    vc_pct = vc.get("porcentaje_importancia", 0)
    vc_pareto = "🔥 20% VITAL (Indispensable)" if vc.get("es_pareto_20_vital") else "💡 80% Complementario"
    vc_motivo = vc.get("por_que_y_cuando_ver", "")

    vcom = analisis.get("vertical_comercializacion", {})
    vcom_pct = vcom.get("porcentaje_importancia", 0)
    vcom_pareto = "🔥 20% VITAL (Indispensable)" if vcom.get("es_pareto_20_vital") else "💡 80% Complementario"
    vcom_motivo = vcom.get("por_que_y_cuando_ver", "")

    pasos = analisis.get("infografia_pasos", [])
    checklist = analisis.get("checklist_15_min", [])
    quiz = analisis.get("quiz_practico", [])
    mermaid = analisis.get("mapa_mental_mermaid", "")

    md = f"""# 🎓 Ficha Académica: {titulo}

**📅 Fecha:** {fecha}  
**🏷️ Transversal:** {transversal}  
**📊 Nivel:** Nivel {nivel} (1=Fundamentos, 2=Implementación, 3=Escala)

---

## 📝 Resumen Didáctico
{resumen}

---

## ⚖️ Análisis Estratégico Pareto 80/20

### ✏️ Vertical 1: Creación de Productos Digitales
- **Importancia:** {vc_pct}%
- **Clasificación:** {vc_pareto}
- **Aplicación Práctica:** {vc_motivo}

### 📈 Vertical 2: Comercialización y Ventas
- **Importancia:** {vcom_pct}%
- **Clasificación:** {vcom_pareto}
- **Aplicación Práctica:** {vcom_motivo}

---

## 🎨 Infografía del Método (Paso a Paso)
"""
    for p in pasos:
        md += f"### {p.get('icono', '📌')} {p.get('titulo', 'Paso')}\n{p.get('explicacion', '')}\n\n"

    md += "\n---\n\n## ⚡ Checklist de Acción Rápida (15 Minutos)\n"
    for item in checklist:
        md += f"- [ ] {item}\n"

    md += "\n---\n\n## 🗺️ Mapa Mental (Mermaid)\n```mermaid\n"
    md += mermaid.strip() + "\n```\n\n"

    md += "---\n\n## 🎯 Quiz Práctico de Autoevaluación\n"
    for i, q in enumerate(quiz, 1):
        md += f"### {i}. {q.get('pregunta')}\n\n"
        for op in q.get("opciones", []):
            md += f"- {op}\n"
        correcta = q.get("respuesta_correcta", "A")
        explicacion = q.get("explicacion", "")
        md += f"\n<details>\n<summary>💡 <b>Ver respuesta correcta y explicación</b></summary>\n\n"
        md += f"> **Respuesta Correcta:** Opción {correcta}\n"
        md += f"> \n"
        md += f"> **Explicación Didáctica:** {explicacion}\n"
        md += f"</details>\n\n"

    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida)), exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[AI Analyzer] ✅ Ficha Markdown generada en: {ruta_salida}")
    return ruta_salida


if __name__ == "__main__":
    print("=== TEST AI_ANALYZER.PY ===")
    test_title = "Estrategias de Venta de Infoproductos con IA"
    resultado = analizar_clase_con_gemini(test_title)
    if resultado:
        print("\nResultado JSON:")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        md_file = os.path.join(BASE_DIR, "grabaciones", "test", "ficha_test.md")
        generar_ficha_markdown(resultado, test_title, "16/10/2026", md_file)