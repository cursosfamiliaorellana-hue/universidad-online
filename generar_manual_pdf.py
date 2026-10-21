"""
generar_manual_pdf.py - Generador de Manual Corporativo Oficial en PDF
Convierte MANUAL_USUARIO.md en MANUAL_UNIVERSIDAD_ONLINE_OFICIAL.pdf
utilizando ReportLab 5 con diseño ejecutivo de alta calidad:
- Encabezados y pie de página con numeración "Página X de Y"
- Paleta ejecutiva: Navy Corporativo, Acento Cyan, Cajas estilizadas
- Formato de tablas, bloques de código, listas y citas
"""

import os
import re
import sys
from typing import List

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(BASE_DIR, "MANUAL_USUARIO.md")
PDF_PATH = os.path.join(BASE_DIR, "MANUAL_UNIVERSIDAD_ONLINE_OFICIAL.pdf")

# Paleta Corporativa
COLOR_PRIMARY = colors.HexColor("#0B192C")      # Azul Marino Profundo
COLOR_SECONDARY = colors.HexColor("#1E293B")    # Slate Oscuro
COLOR_ACCENT = colors.HexColor("#0284C7")       # Cyan Corporativo
COLOR_SUCCESS = colors.HexColor("#10B981")      # Verde Éxito
COLOR_BG_CARD = colors.HexColor("#F8FAFC")      # Fondo Cajas / Tablas
COLOR_BORDER = colors.HexColor("#CBD5E1")       # Borde Suave
COLOR_TEXT = colors.HexColor("#0F172A")         # Texto Principal
COLOR_MUTED = colors.HexColor("#64748B")        # Texto Secundario
COLOR_CODE_BG = colors.HexColor("#F1F5F9")      # Fondo Código


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasos para imprimir el número total de páginas y encabezado corporativo."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        width, height = letter

        # Encabezado (Páginas 2 en adelante)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(COLOR_ACCENT)
            self.drawString(54, height - 36, "BOT UNIVERSIDAD ONLINE")
            self.setFont("Helvetica", 8)
            self.setFillColor(COLOR_MUTED)
            self.drawString(180, height - 36, "-  MANUAL OFICIAL DE INGENIERIA Y OPERACIONES")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(54, height - 42, width - 54, height - 42)

        # Pie de página (Todas las páginas)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(54, 42, width - 54, 42)

        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_MUTED)
        self.drawString(54, 30, "Documento Confidencial - Sistema Autonomo v5.0 Pro")

        page_str = f"Pagina {self._pageNumber} de {page_count}"
        self.drawRightString(width - 54, 30, page_str)

        self.restoreState()


EMOJI_REPLACEMENTS = {
    "⭐": "[Clase Clave]",
    "✅": "[OK]",
    "🛑": "[STOP]",
    "⏳": "[Pendiente]",
    "🔴": "[EN VIVO]",
    "📁": "[Carpeta]",
    "💻": "[PC]",
    "📱": "[Movil]",
    "☁️": "[Nube]",
    "🚀": "[Inicio]",
    "⚙️": "[Proceso]",
    "🧠": "[IA]",
    "🎙️": "[Voz]",
    "🦅": "[Vigia]",
    "🗑️": "[Borrar]",
    "✏️": "[Editar]",
    "👥": "[Grupo]",
    "📥": "[Ingesta]",
    "🔍": "[Auditoria]",
    "🔁": "[Re-grabar]",
    "⚡": "[Evento]",
    "🔥": "[Destacado]",
    "📖": "[Manual]",
    "🌍": "[Ecosistema]",
    "🎛️": "[Control]",
    "🛠️": "[Operaciones]",
    "🛡️": "[Seguridad]",
    "📊": "[Metricas]",
    "📜": "[Logs]",
    "🎴": "[Flashcards]",
    "🗺️": "[Mapa]",
    "⏱️": "[Tiempo]",
    "📋": "[Pasos]",
    "💾": "[Almacenamiento]",
    "👁️": "[Visibilidad]",
    "💥": "[Eliminar]",
    "▶️": "[Reanudar]",
    "⏸️": "[Pausa]",
    "🎉": "[Exito]",
    "⚠️": "[Aviso]",
    "🚨": "[Alerta]",
    "💡": "[Tip]",
}

EMOJI_CLEANER = re.compile(
    r"[\U00010000-\U0010ffff]|[\u200d\u200c\u2060\ufe0f]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u2190-\u21ff]",
    flags=re.UNICODE
)


def sanitizar_texto_para_reportlab(texto: str) -> str:
    """Reemplaza emojis por equivalentes legibles y limpia caracteres no compatibles con fuentes estándar."""
    for em, rep in EMOJI_REPLACEMENTS.items():
        if em in texto:
            texto = texto.replace(em, rep)
    # Limpiar cualquier emoji residual que no tenga fuente en Helvetica
    texto = EMOJI_CLEANER.sub("", texto)
    return texto


def formatear_linea_md(texto: str) -> str:
    """Escapa entidades y convierte marcas básicas de Markdown a tags compatibles con ReportLab."""
    t = sanitizar_texto_para_reportlab(texto)
    t = t.replace("&", "&amp;")
    t = t.replace("<", "&lt;").replace(">", "&gt;")

    # Restaurar tags permitidos
    # Convertir backticks simples a Courier coloreado
    t = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#0369a1"><b>\1</b></font>', t)
    # Negritas
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    # Cursivas
    t = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", t)
    return t


def parsear_markdown_a_flowables(md_text: str, styles: dict) -> list:
    flowables = []
    lineas = md_text.splitlines()
    i = 0
    total = len(lineas)

    in_code_block = False
    code_lines = []

    in_table = False
    table_rows = []

    while i < total:
        line = lineas[i]
        line_s = line.strip()

        # Bloque de Código (```)
        if line_s.startswith("```"):
            if in_code_block:
                code_text = "<br/>".join(
                    sanitizar_texto_para_reportlab(l)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace(" ", "&nbsp;")
                    for l in code_lines
                )
                p_code = Paragraph(f"<font name='Courier' size='7.5'>{code_text}</font>", styles["CodeBox"])
                t_code = Table([[p_code]], colWidths=[504])
                t_code.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), COLOR_CODE_BG),
                    ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(t_code)
                flowables.append(Spacer(1, 8))
                in_code_block = False
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Tablas Markdown (| col1 | col2 | ...)
        if line_s.startswith("|") and line_s.endswith("|"):
            if not in_table:
                in_table = True
                table_rows = []

            # Ignorar separadores como | :--- | :--- |
            if re.match(r"^\|(\s*:?-+:?\s*\|)+$", line_s):
                i += 1
                continue

            celdas = [c.strip() for c in line_s[1:-1].split("|")]
            table_rows.append(celdas)
            i += 1
            continue
        elif in_table:
            # Procesar tabla acumulada
            if table_rows:
                num_cols = max(len(r) for r in table_rows)
                clean_rows = []
                for row_idx, r in enumerate(table_rows):
                    while len(r) < num_cols:
                        r.append("")
                    row_pars = []
                    for c_idx, cell in enumerate(r):
                        style = styles["TableHeader"] if row_idx == 0 else styles["TableCell"]
                        row_pars.append(Paragraph(formatear_linea_md(cell), style))
                    clean_rows.append(row_pars)

                if num_cols == 2:
                    col_widths = [140, 364]
                elif num_cols == 3:
                    col_widths = [110, 180, 214]
                else:
                    w = 504 / num_cols
                    col_widths = [w] * num_cols

                t = Table(clean_rows, colWidths=col_widths, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_CARD]),
                ]))
                flowables.append(Spacer(1, 6))
                flowables.append(t)
                flowables.append(Spacer(1, 10))

            in_table = False
            table_rows = []

        # Regla Horizontal (---)
        if line_s == "---":
            flowables.append(Spacer(1, 6))
            flowables.append(HRFlowable(width="100%", thickness=0.8, color=COLOR_BORDER, spaceAfter=8))
            i += 1
            continue

        # Citas / Callouts (> ...)
        if line_s.startswith(">"):
            quote_text = line_s.lstrip(">").strip()
            p_q = Paragraph(formatear_linea_md(quote_text), styles["CalloutText"])
            t_q = Table([[p_q]], colWidths=[504])
            t_q.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_CARD),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3.5, COLOR_ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            flowables.append(Spacer(1, 3))
            flowables.append(t_q)
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        # Encabezado 1 (# ...)
        if line_s.startswith("# "):
            txt = line_s[2:].strip()
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(formatear_linea_md(txt), styles["Heading1Custom"]))
            flowables.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_ACCENT, spaceAfter=10))
            i += 1
            continue

        # Encabezado 2 (## ...)
        if line_s.startswith("## "):
            txt = line_s[3:].strip()
            flowables.append(Spacer(1, 8))
            flowables.append(Paragraph(formatear_linea_md(txt), styles["Heading2Custom"]))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Encabezado 3 (### ...)
        if line_s.startswith("### "):
            txt = line_s[4:].strip()
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(formatear_linea_md(txt), styles["Heading3Custom"]))
            flowables.append(Spacer(1, 3))
            i += 1
            continue

        # Listas con viñetas (- ... o * ...)
        if line_s.startswith("- ") or line_s.startswith("* "):
            txt = line_s[2:].strip()
            p_bullet = Paragraph(f"&bull; &nbsp; {formatear_linea_md(txt)}", styles["BulletCustom"])
            flowables.append(p_bullet)
            i += 1
            continue

        # Listas numeradas (1. ... 2. ...)
        match_num = re.match(r"^(\d+)\.\s+(.*)$", line_s)
        if match_num:
            num = match_num.group(1)
            txt = match_num.group(2)
            p_num = Paragraph(f"<b>{num}.</b> &nbsp; {formatear_linea_md(txt)}", styles["BulletCustom"])
            flowables.append(p_num)
            i += 1
            continue

        # Línea en blanco
        if not line_s:
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Párrafo normal
        flowables.append(Paragraph(formatear_linea_md(line_s), styles["BodyCustom"]))
        flowables.append(Spacer(1, 4))
        i += 1

    return flowables


def generar_pdf():
    print(f"Leyendo manual desde: {MD_PATH}")
    if not os.path.exists(MD_PATH):
        print(f"[!] Error: No se encontro {MD_PATH}")
        sys.exit(1)

    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    doc = SimpleDocTemplate(
        PDF_PATH,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    sample_styles = getSampleStyleSheet()

    styles = {
        "Heading1Custom": ParagraphStyle(
            "Heading1Custom",
            parent=sample_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=COLOR_PRIMARY,
            spaceAfter=4,
        ),
        "Heading2Custom": ParagraphStyle(
            "Heading2Custom",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=COLOR_PRIMARY,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "Heading3Custom": ParagraphStyle(
            "Heading3Custom",
            parent=sample_styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=COLOR_ACCENT,
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "BodyCustom": ParagraphStyle(
            "BodyCustom",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=COLOR_TEXT,
        ),
        "BulletCustom": ParagraphStyle(
            "BulletCustom",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            leftIndent=14,
            textColor=COLOR_TEXT,
            spaceAfter=2,
        ),
        "CalloutText": ParagraphStyle(
            "CalloutText",
            parent=sample_styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=COLOR_SECONDARY,
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader",
            parent=sample_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10.5,
            textColor=COLOR_TEXT,
        ),
        "CodeBox": ParagraphStyle(
            "CodeBox",
            parent=sample_styles["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=10,
            textColor=COLOR_SECONDARY,
        ),
    }

    print("Analizando estructura y maquetando elementos en ReportLab Platypus...")
    story = parsear_markdown_a_flowables(md_text, styles)

    print(f"Construyendo PDF con NumberedCanvas ({len(story)} elementos)...")
    doc.build(story, canvasmaker=NumberedCanvas)

    tam_kb = round(os.path.getsize(PDF_PATH) / 1024, 1)
    print(f"[OK] MANUAL PDF GENERADO CON EXITO!")
    print(f"Ruta: {PDF_PATH}")
    print(f"Tamano: {tam_kb} KB")


if __name__ == "__main__":
    generar_pdf()
