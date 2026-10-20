"""
visual_generator.py - Generador de Recursos Visuales para Telegram (Infografías + Mapas Mentales)
Renderiza imágenes .PNG en alta resolución usando Playwright vía CDP (localhost:9222)
Compatible con Python 3.8 y 3.10+ (Windows 8 / 10 / 11).
"""

import asyncio
import os
import re
import sys
from typing import Optional, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CDP_URL_DEFAULT = "http://localhost:9222"


def construir_html_infografia(analisis: Dict[str, Any], titulo_clase: str) -> str:
    """Construye un diseño HTML moderno y elegante para la infografía y el checklist."""
    transversal = analisis.get("transversal", "General")
    nivel = analisis.get("nivel", 1)

    vc = analisis.get("vertical_creacion", {})
    pct_creacion = vc.get("porcentaje_importancia", 0)
    badge_creacion = "🔥 20% VITAL" if vc.get("es_pareto_20_vital") else "💡 80% COMPLEMENTARIO"

    vcom = analisis.get("vertical_comercializacion", {})
    pct_com = vcom.get("porcentaje_importancia", 0)
    badge_com = "🔥 20% VITAL" if vcom.get("es_pareto_20_vital") else "💡 80% COMPLEMENTARIO"

    pasos = analisis.get("infografia_pasos", [])
    pasos_html = ""
    for p in pasos[:6]:
        icono = p.get("icono", "📌")
        titulo = p.get("titulo", "Paso")
        desc = p.get("explicacion", "")
        pasos_html += f"""
        <div class="step-card">
          <div class="step-icon">{icono}</div>
          <div class="step-content">
            <div class="step-title">{titulo}</div>
            <div class="step-desc">{desc}</div>
          </div>
        </div>
        """

    checklist = analisis.get("checklist_15_min", [])
    chk_html = ""
    for i, chk in enumerate(checklist[:3], 1):
        chk_html += f"""
        <div class="chk-item">
          <div class="chk-num">{i}</div>
          <div class="chk-text">{chk}</div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 30px;
      background: #090d16;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #f1f5f9;
      width: 900px;
    }}
    .container {{
      background: linear-gradient(145deg, #131b2e 0%, #0d1322 100%);
      border: 1px solid #1e293b;
      border-radius: 20px;
      padding: 32px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    .badges {{
      display: flex;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .badge {{
      display: inline-block;
      padding: 5px 12px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .badge-transversal {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }}
    .badge-nivel {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }}
    
    h1 {{
      font-size: 26px;
      font-weight: 800;
      margin: 0;
      color: #ffffff;
      line-height: 1.3;
    }}
    .sub-brand {{
      font-size: 13px;
      font-weight: 600;
      color: #38bdf8;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-top: 6px;
    }}

    .pareto-summary {{
      display: flex;
      gap: 12px;
    }}
    .pareto-box {{
      background: #090d16;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 10px 14px;
      text-align: center;
      min-width: 140px;
    }}
    .pareto-label {{
      font-size: 11px;
      color: #94a3b8;
      margin-bottom: 4px;
    }}
    .pareto-val {{
      font-size: 13px;
      font-weight: bold;
      color: #f59e0b;
    }}

    .section-title {{
      font-size: 16px;
      font-weight: 700;
      color: #38bdf8;
      margin: 20px 0 14px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .steps-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    .step-card {{
      background: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 14px;
      padding: 16px;
      display: flex;
      gap: 14px;
      align-items: flex-start;
    }}
    .step-icon {{
      font-size: 24px;
      line-height: 1;
      padding: 8px;
      background: #131d33;
      border-radius: 10px;
    }}
    .step-content {{
      flex: 1;
    }}
    .step-title {{
      font-size: 14px;
      font-weight: 700;
      color: #f8fafc;
      margin-bottom: 6px;
    }}
    .step-desc {{
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.45;
    }}

    .checklist-box {{
      margin-top: 24px;
      background: linear-gradient(145deg, rgba(16, 185, 129, 0.08) 0%, rgba(6, 78, 59, 0.15) 100%);
      border: 1px solid rgba(16, 185, 129, 0.4);
      border-radius: 16px;
      padding: 20px 24px;
    }}
    .chk-title {{
      font-size: 15px;
      font-weight: 800;
      color: #34d399;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .chk-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .chk-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(0, 0, 0, 0.3);
      padding: 10px 14px;
      border-radius: 10px;
      border-left: 3px solid #10b981;
    }}
    .chk-num {{
      background: #10b981;
      color: #042f2e;
      font-size: 11px;
      font-weight: 900;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}
    .chk-text {{
      font-size: 13px;
      color: #e2e8f0;
      font-weight: 500;
    }}

    .footer {{
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid #1e293b;
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <div class="badges">
          <span class="badge badge-transversal">{transversal}</span>
          <span class="badge badge-nivel">Nivel {nivel}</span>
        </div>
        <h1>{titulo_clase}</h1>
        <div class="sub-brand">Universidad Online · Sistema Didáctico Pareto 80/20</div>
      </div>
      <div class="pareto-summary">
        <div class="pareto-box">
          <div class="pareto-label">Creación de Producto</div>
          <div class="pareto-val">{pct_creacion}% · {badge_creacion}</div>
        </div>
        <div class="pareto-box">
          <div class="pareto-label">Comercialización</div>
          <div class="pareto-val">{pct_com}% · {badge_com}</div>
        </div>
      </div>
    </div>

    <div class="section-title">📊 Pasos Clave del Método</div>
    <div class="steps-grid">
      {pasos_html}
    </div>

    <div class="checklist-box">
      <div class="chk-title">⚡ Checklist de Acción en 15 Minutos</div>
      <div class="chk-list">
        {chk_html}
      </div>
    </div>

    <div class="footer">
      <span>🎓 Masterclass Grabada & Analizada Automáticamente</span>
      <span>🤖 Generado con Gemini AI & NotebookLM</span>
    </div>
  </div>
</body>
</html>"""
    return html


def construir_html_mapa_mental(analisis: Dict[str, Any], titulo_clase: str) -> str:
    """Construye un documento HTML con Mermaid.js renderizando el mapa mental estructurado."""
    mermaid_code = analisis.get("mapa_mental_mermaid", "")
    if not mermaid_code or "graph" not in mermaid_code:
        mermaid_code = f"""graph TD
    A["{titulo_clase}"] --> B["Fundamentos y Estrategia"]
    A --> C["Implementación Paso a Paso"]
    B --> D["Acción Clave 15 Min"]
    C --> E["Escalado Comercial"]"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{ startOnLoad: true, theme: 'dark', securityLevel: 'loose' }});</script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 30px;
      background: #090d16;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #f1f5f9;
      width: 900px;
    }}
    .container {{
      background: linear-gradient(145deg, #131b2e 0%, #0d1322 100%);
      border: 1px solid #1e293b;
      border-radius: 20px;
      padding: 32px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
      text-align: center;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 800;
      margin: 0 0 6px 0;
      color: #38bdf8;
    }}
    .sub {{
      font-size: 13px;
      color: #94a3b8;
      margin-bottom: 24px;
    }}
    .diagram-wrap {{
      background: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 14px;
      padding: 24px;
      display: inline-block;
      min-width: 80%;
    }}
    .mermaid svg {{
      max-width: 100% !important;
      height: auto !important;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>🗺 Mapa Mental de Estructura</h1>
    <div class="sub">{titulo_clase}</div>
    <div class="diagram-wrap">
      <div class="mermaid">
{mermaid_code}
      </div>
    </div>
  </div>
</body>
</html>"""
    return html


async def renderizar_html_a_png(html_content: str, ruta_salida_png: str, selector: str = ".container", cdp_url: str = CDP_URL_DEFAULT) -> bool:
    """Abre una pestaña en Chrome vía CDP, renderiza el HTML y toma una captura nítida."""
    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida_png)), exist_ok=True)
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
            page = await context.new_page()
            await page.set_viewport_size({"width": 960, "height": 1100})
            await page.set_content(html_content)

            # Si hay mermaid, esperar a que el SVG esté renderizado
            if "mermaid" in html_content:
                try:
                    await page.wait_for_selector(".mermaid svg", timeout=12000)
                except Exception:
                    pass

            target = page.locator(selector).first
            if await target.count() > 0:
                await target.screenshot(path=ruta_salida_png)
            else:
                await page.screenshot(path=ruta_salida_png)

            await page.close()
            return os.path.exists(ruta_salida_png) and os.path.getsize(ruta_salida_png) > 1000
        except Exception as e:
            print(f"[Visual Generator] [Aviso] Error renderizando imagen vía CDP: {e}")
            return False


async def generar_recursos_visuales(
    analisis: Dict[str, Any],
    titulo_clase: str,
    id_clase: str,
    carpeta_destino: str,
    cdp_url: str = CDP_URL_DEFAULT,
) -> Dict[str, Optional[str]]:
    """
    Genera los dos archivos de imagen PNG:
    1. Infografia_[id].png
    2. Mapa_Mental_[id].png
    """
    os.makedirs(carpeta_destino, exist_ok=True)
    ruta_infografia = os.path.join(carpeta_destino, f"Infografia_{id_clase}.png")
    ruta_mapa = os.path.join(carpeta_destino, f"Mapa_Mental_{id_clase}.png")

    resultados = {
        "infografia_png": None,
        "mapa_mental_png": None,
    }

    # 1. Infografía
    try:
        html_info = construir_html_infografia(analisis, titulo_clase)
        ok_info = await renderizar_html_a_png(html_info, ruta_infografia, selector=".container", cdp_url=cdp_url)
        if ok_info:
            resultados["infografia_png"] = ruta_infografia
            print(f"[Visual Generator] ✅ Infografía generada: {os.path.basename(ruta_infografia)}")
    except Exception as e:
        print(f"[Visual Generator] Error generando infografía: {e}")

    # 2. Mapa Mental
    try:
        html_mapa = construir_html_mapa_mental(analisis, titulo_clase)
        ok_mapa = await renderizar_html_a_png(html_mapa, ruta_mapa, selector=".container", cdp_url=cdp_url)
        if ok_mapa:
            resultados["mapa_mental_png"] = ruta_mapa
            print(f"[Visual Generator] ✅ Mapa mental generado: {os.path.basename(ruta_mapa)}")
    except Exception as e:
        print(f"[Visual Generator] Error generando mapa mental: {e}")

    return resultados


if __name__ == "__main__":
    analisis_dummy = {
        "transversal": "Marketing Digital",
        "nivel": 2,
        "vertical_creacion": {"porcentaje_importancia": 85, "es_pareto_20_vital": True},
        "vertical_comercializacion": {"porcentaje_importancia": 95, "es_pareto_20_vital": True},
        "infografia_pasos": [
            {"icono": "🎯", "titulo": "1. Identificar Dolor", "explicacion": "Mapea el problema más urgente."},
            {"icono": "⚙️", "titulo": "2. Crear la Oferta", "explicacion": "Estructura un producto irresistible."},
            {"icono": "🚀", "titulo": "3. Lanzamiento Rápido", "explicacion": "Vende antes de grabar todo."},
            {"icono": "💰", "titulo": "4. Escala de Ventas", "explicacion": "Aumenta la inversión en tráfico."},
        ],
        "checklist_15_min": [
            "Definir el titular de tu oferta en 1 frase.",
            "Elegir el precio y formato (curso o mentoría).",
            "Publicar una encuesta de validación en tus historias.",
        ],
        "mapa_mental_mermaid": "graph TD\n  A[Monetizar] --> B[Crear]\n  A --> C[Vender]",
    }
    res = asyncio.run(generar_recursos_visuales(analisis_dummy, "Monetiza tu Conocimiento", "test_clase", BASE_DIR))
    print("Resultado:", res)
