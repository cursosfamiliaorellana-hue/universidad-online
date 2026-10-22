# -*- coding: utf-8 -*-
"""
generar_documento_maestro.py
Genera el PDF exhaustivo de Arquitectura, Especificaciones y Super Prompt Maestro
para el sistema Bot Universidad Online y Auto-Sanación.
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Preformatted
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

PDF_OUTPUT_PATH = r"Z:\ARQUITECTURA_Y_SUPER_PROMPT_MAESTRO.pdf"

class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para numerar páginas exactamente como 'Página X de Y'."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_number(self, page_count):
        if self._pageNumber == 1:
            return  # Omitir número en portada
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header
        self.drawString(54, 750, "BOT UNIVERSIDAD ONLINE — ARQUITECTURA DISTRIBUIDA Y SUPER PROMPT")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 742, letter[0] - 54, 742)
        
        # Footer
        self.line(54, 45, letter[0] - 54, 45)
        self.drawString(54, 32, "Confidencial — Sistema Autónomo con Auto-Sanación (Dell <-> Acer)")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 54, 32, page_str)
        self.restoreState()


def construir_pdf():
    doc = SimpleDocTemplate(
        PDF_OUTPUT_PATH,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Paleta de colores
    c_primary = colors.HexColor("#1A365D")   # Deep navy
    c_secondary = colors.HexColor("#2B6CB0") # Medium blue
    c_accent = colors.HexColor("#319795")    # Teal
    c_dark = colors.HexColor("#2D3748")      # Charcoal
    c_light = colors.HexColor("#F7FAFC")     # Soft gray bg
    c_border = colors.HexColor("#E2E8F0")    # Border gray
    c_code_bg = colors.HexColor("#1A202C")   # Dark code bg
    c_code_text = colors.HexColor("#E2E8F0")

    # Estilos tipográficos
    style_cover_title = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=c_primary,
        alignment=1, # Center
        spaceAfter=15
    )

    style_cover_sub = ParagraphStyle(
        'CoverSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        alignment=1,
        spaceAfter=30
    )

    style_h1 = ParagraphStyle(
        'Header1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=c_primary,
        spaceBefore=18,
        spaceAfter=8,
        keepWithNext=True
    )

    style_h2 = ParagraphStyle(
        'Header2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    style_body = ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=6
    )

    style_bullet = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_dark,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    style_code = ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=c_code_text,
        spaceAfter=4
    )

    style_callout = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#2C5282")
    )

    elements = []

    # =========================================================================
    # PORTADA
    # =========================================================================
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("SISTEMA AUTÓNOMO UNIVERSIDAD ONLINE", style_cover_title))
    elements.append(Paragraph("DOCUMENTO MAESTRO DE ARQUITECTURA DISTRIBUIDA,<br/>INGENIERÍA DE SOFTWARE Y SUPER PROMPT DE RESTAURACIÓN INTEGRAL", style_cover_sub))
    elements.append(HRFlowable(width="80%", thickness=2, color=c_accent, spaceBefore=10, spaceAfter=25))

    meta_data = [
        [Paragraph("<b>Versión del Sistema:</b>", style_body), Paragraph("3.8 Enterprise (Auto-Sanación Activa)", style_body)],
        [Paragraph("<b>Fecha de Generación:</b>", style_body), Paragraph("21 de Octubre de 2026", style_body)],
        [Paragraph("<b>Topología de Hardware:</b>", style_body), Paragraph("Laptop Acer (Cliente/Ejecutor) &lt;--&gt; Laptop Dell (Agente IA Dell Antigravity)", style_body)],
        [Paragraph("<b>Directiva Perpetua:</b>", style_body), Paragraph("Cero Regresiones — Máxima Eficiencia — Preservación de Negocio", style_body)],
        [Paragraph("<b>Ubicación del Código:</b>", style_body), Paragraph("Red Local: <code>Z:\\ (\\\\192.168.100.229\\Bot_UniversidadOnline)</code>", style_body)],
    ]
    t_meta = Table(meta_data, colWidths=[160, 320])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_light),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_meta)
    
    elements.append(Spacer(1, 35))
    callout_box = [
        [Paragraph("<b>DIRECTIVA ESTRUCTURAL PERPETUA (CERO REGRESIONES):</b><br/>"
                   "Toda modificación, ampliación de interfaz o depuración tiene como único fin optimizar el flujo sin romper la base. "
                   "Queda terminantemente prohibido alterar la lógica de negocio (Orquestador, Playwright CDP, Vigía de Audio, Telethon, NotebookLM y Remuxing FFmpeg). "
                   "Cualquier fallo se aísla sin provocar caída en cascada del sistema.", style_callout)]
    ]
    t_call = Table(callout_box, colWidths=[480])
    t_call.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EBF8FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#90CDF4")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    elements.append(t_call)

    elements.append(PageBreak())

    # =========================================================================
    # SECCIÓN 1: ARQUITECTURA DISTRIBUIDA Y TOPOLOGÍA
    # =========================================================================
    elements.append(Paragraph("1. Arquitectura Distribuida y Topología de Red", style_h1))
    elements.append(Paragraph(
        "El sistema opera bajo un modelo maestro-agente cooperativo distribuido entre dos estaciones de trabajo conectadas a la red local:",
        style_body
    ))
    
    elements.append(Paragraph("<b>A. Laptop Acer (Nodo Cliente y Ejecutor Central):</b>", style_h2))
    elements.append(Paragraph("• Ejecuta el <b>Orquestador Concurrente</b> (<code>main.py</code>), responsable de programar grabaciones, vigilar eventos y procesar colas.", style_bullet))
    elements.append(Paragraph("• Ejecuta el motor <b>Playwright CDP</b> (<code>recorder.py</code>), controlando Google Chrome en <code>localhost:9222</code> para capturar transmisiones de Hotmart.", style_bullet))
    elements.append(Paragraph("• Aloja el <b>Dashboard Web Ultra-Ligero</b> (<code>dashboard_web.py</code>) en el puerto 5000, proporcionando la interfaz visual de 4 consolas sincronizadas.", style_bullet))
    elements.append(Paragraph("• Mantiene el <b>Buffer de Errores Offline-First</b> (<code>error_buffer.py</code>) en <code>registro_errores.json</code>.", style_bullet))
    elements.append(Paragraph("• Comparte su unidad de disco por red SMB como <code>Z:\\</code> hacia la laptop Dell.", style_bullet))

    elements.append(Paragraph("<b>B. Laptop Dell (Nodo Agente IA Autónomo - Antigravity):</b>", style_h2))
    elements.append(Paragraph("• Aloja al <b>Agente Inteligente Antigravity</b>, facultado para auto-sanar el código en tiempo real.", style_bullet))
    elements.append(Paragraph("• Expone un endpoint HTTP seguro en <code>192.168.100.126:8000/api/auto_heal</code> para recepción de alarmas automáticas.", style_bullet))
    elements.append(Paragraph("• Dispone de acceso de lectura y escritura directo sobre <code>Z:\\</code> para compilar, auditar y parchar scripts sin intervención humana.", style_bullet))

    elements.append(Spacer(1, 10))

    # =========================================================================
    # SECCIÓN 2: DESGLOSE DE MÓDULOS Y LÓGICA DE NEGOCIO
    # =========================================================================
    elements.append(Paragraph("2. Desglose Exhaustivo Módulo por Módulo", style_h1))

    modulos_data = [
        ("main.py", "Orquestador Central", "Coordina el bucle de eventos asyncio, sincronización cada 6h con Google Calendar/BD, worker de post-proceso, Sala de Espera (asyncio.Queue), anticipación de 10 min (600s), ventana tardía de 900s, corte a 0 min ante choques horarios, y salvaguarda anti-destrucción de WebM."),
        ("recorder.py", "Motor de Captura y Remuxing", "Controla Chrome mediante Playwright CDP (9222). Incorpora el Buscador Adaptativo con scoring semántico/fonético (alias, stemming, bonos En Vivo/Countdown), modo francotirador con sondeo de tracks de video (>0), remuxing FFmpeg a MP4 H.264/AAC."),
        ("dashboard_web.py", "Panel Web Ultra-Ligero (5000)", "Servidor ThreadingHTTPServer nativo. Muestra 4 consolas con timestamps en columna derecha y botones de copiado, desplegables de Cronograma Hoy/Mañana e Histórico, switch local/nube y control maestro sin fatiga de CPU."),
        ("error_buffer.py", "Protocolo de Auto-Sanación", "Almacena fallos en registro_errores.json con locking seguro y límite circular de 250 eventos. Transmite alarmas a Dell y alimenta la Consola 4 del panel web."),
        ("telegram_uploader.py", "Cargador MTProto", "Sube archivos de hasta 2GB por partes a canales privados de Telegram usando Telethon. Optimiza bitrate dinámicamente si el archivo supera el umbral."),
        ("notebooklm_bot.py", "Generador de Podcasts IA", "Crea audio podcasts y resúmenes ejecutivos vía Google NotebookLM. Mantiene cola de reintentos con backoff exponencial."),
        ("database.py", "Capa de Persistencia SQLite", "Gestiona 'clases.db' (tabla clases_grabadas). Garantiza atomicidad en transacciones y control de re-grabación segura (safe overwrite)."),
        ("scraper.py", "Extractor de Cronograma", "Descarga y analiza el calendario de Universidad Online, convirtiendo zona horaria Los Ángeles a hora Bolivia y detectando enlaces a Hotmart/Zoom."),
        ("calendar_sync.py", "Sincronizador Google Calendar", "Intercambio bidireccional mediante Webhook para reflejar estados ('🔴 [GRABANDO AHORA]', '✅ [COMPLETADA]')."),
        ("vigia_mentores.py", "Vigía de Voz y Zoom", "Monitorea canales de voz en Telegram y enlaces Zoom para mentorías espontáneas.")
    ]

    t_mod_rows = [[Paragraph(f"<b>{m[0]}</b><br/><i>{m[1]}</i>", style_body), Paragraph(m[2], style_body)] for m in modulos_data]
    t_mod = Table(t_mod_rows, colWidths=[150, 330])
    t_mod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_mod)

    elements.append(PageBreak())

    # =========================================================================
    # SECCIÓN 3: PREGUNTAS FRECUENTES Y RESPUESTAS OPERATIVAS
    # =========================================================================
    elements.append(Paragraph("3. Respuestas Operativas Clave del Sistema", style_h1))

    faq = [
        ("¿Por qué el Bloc de Notas (Notepad) no se abre al encender el bot?",
         "El Bloc de Notas es una herramienta de entrega visual que se dispara única y exclusivamente al concluir la grabación y post-procesamiento de una clase o mentoría. NotebookLM y Gemini generan la transcripción y el resumen ejecutivo en un archivo .txt, momento en el cual el bot lo abre en pantalla para lectura inmediata del usuario. Es completamente normal que al inicio no se abra ninguna ventana de Bloc de Notas."),
        
        ("¿Por qué Telegram no abre ninguna ventana visible en Windows?",
         "El módulo <code>telegram_uploader.py</code> y el vigía de canales se comunican directamente a través del protocolo MTProto de la librería Telethon utilizando los tokens de API (<code>telegram_api_id</code> y <code>telegram_api_hash</code>) de <code>config.json</code>. No se requiere ni se desea abrir la aplicación de escritorio de Telegram ni pestañas web, evitando consumo innecesario de memoria y garantizando operación en modo fantasma."),

        ("¿Cómo funciona el Buscador Adaptativo ante discrepancias de nombres?",
         "En plataformas como Hotmart, el título publicado ('En vivo - Imágenes impactantes con ChatGPT. Power Eight by Quique Cárdenas') difiere con frecuencia del título en el calendario ('Crea imágenes que impacten con IA - Kike Cadena'). El buscador adaptativo resuelve esto mediante: (1) Normalización y remoción de acentos, (2) Diccionario de sinónimos y alias fonéticos (kike=quique, cadena=cardenas, ia=chatgpt), (3) Raíces léxicas o stemming (impacten/impactantes), (4) Bonificación de +5 puntos por bandera 'En vivo' y +4 por cuenta regresiva. Si el título difiere, se asocia automáticamente y se reporta en Consola 4."),

        ("¿Qué hacer ante una alarma de clase no localizada?",
         "Si a la hora programada la clase no ha sido publicada por el instructor, el sistema emite una alerta roja en Consola 4 y registra el incidente en <code>registro_errores.json</code>. El Agente Dell recibe la notificación y verifica si hubo cambio de URL o si el stream aún no inició, reintentando de forma ordenada sin saturar la memoria.")
    ]

    for q, a in faq:
        elements.append(Paragraph(f"<b>P: {q}</b>", style_h2))
        elements.append(Paragraph(a, style_body))
        elements.append(Spacer(1, 4))

    elements.append(Spacer(1, 10))

    # =========================================================================
    # SECCIÓN 4: SUPER PROMPT DE RESTAURACIÓN INTEGRAL
    # =========================================================================
    elements.append(PageBreak())
    elements.append(Paragraph("4. SUPER PROMPT MAESTRO DE RESTAURACIÓN INTEGRAL", style_h1))
    elements.append(Paragraph(
        "El siguiente Super Prompt contiene la especificación completa, lógica de negocio y arquitectura inquebrantable del sistema. "
        "En caso de reinstalación completa, migración de equipo o pérdida accidental de archivos, copie y pegue este prompt en cualquier "
        "asistente de IA (Antigravity, Claude, Gemini o ChatGPT) para reconstruir o continuar el desarrollo con cero regresiones:",
        style_body
    ))
    elements.append(Spacer(1, 6))

    super_prompt_text = (
"""================================================================================
SUPER PROMPT MAESTRO: RESTAURACIÓN Y CONTINUIDAD TOTAL DEL BOT UNIVERSIDAD ONLINE
================================================================================
ROL Y CONTEXTO:
Eres el Arquitecto de Software Principal del sistema autónomo 'Bot Universidad Online'.
Tu misión es mantener, optimizar o reconstruir este sistema distribuido entre dos laptops:
- Laptop Acer (Cliente Ejecutor): Orquestador, Playwright CDP, Grabador FFmpeg, Panel Web (puerto 8000), Buffer de Errores y Base de Datos SQLite (clases.db).
- Laptop Dell (Agente IA Autónomo - Antigravity): Centinela Auditor 24 Horas (puerto 5005), auto-sanación proactiva y acceso a Z:\\ (\\\\192.168.100.229\\Bot_UniversidadOnline).

⚠️ DIRECTIVA ESTRUCTURAL PERPETUA (CERO REGRESIONES):
Toda instrucción de mejora, depuración o cambio visual tiene como único objetivo optimizar el flujo sin romper la base.
Tienes ESTRICTAMENTE PROHIBIDO alterar, eliminar o modificar la Lógica de Negocio ya establecida:
1. MOTORES BASE: Orquestador (main.py), Grabador Playwright (recorder.py), Vigía de Audio (vigia_mentores.py), Telegram (telegram_uploader.py), y NotebookLM (notebooklm_bot.py) DEBEN mantener su comportamiento intacto.
2. PRESERVACIÓN DE VIDEO CRUDO: Nunca eliminar grabaciones intermedias .webm si el remuxing a .mp4 falla; salvar en estado 'ERROR_REMUXING' para salvaguardar el contenido.
3. CONEXIÓN A CHROME VÍA CDP: Se conecta exclusivamente a Chrome en http://localhost:9222 mediante Playwright CDP, inyectando el sello 'window.__clase_id' para garantizar una sola pestaña aislada por clase.
4. BUSCADOR ADAPTATIVO HOTMART: Si el título en Hotmart difiere del cronograma, se aplica similitud fuzzy inteligente con alias fonéticos (kike<->quique, cadena<->cardenas, ia<->chatgpt), stemming de palabras y bonus masivo a banderas 'En vivo' y cuenta regresiva.
5. ANTICIPACIÓN Y MARGEN DINÁMICO: Ingreso 5 minutos antes (300s) a Hotmart para verificar lección/reproductor. Margen final de 5 minutos adicionales, reducible a 0 minutos si otra clase comienza inmediatamente después (evitar choques).
6. AUTO-SANACIÓN OFFLINE-FIRST E INMUNIDAD: Cualquier excepción se registra en 'registro_errores.json' vía error_buffer.py y se sincroniza con el Centinela Auditor de la Laptop Dell, aplicando soluciones definitivas registradas en 'registro_inmunidad.json'.
7. RENDIMIENTO: Cero parpadeos, cero bucles infinitos de CPU, uso de servidores nativos en Python (ThreadingHTTPServer) y llamadas no bloqueantes.

ESTRUCTURA DE ARCHIVOS ESENCIALES EN Z:\\:
- main.py: Orquestador principal, colas asyncio, bucle con latido de bajo CPU cada 5 min.
- recorder.py: Capturador CDP, extractor de candidatos DOM, remuxing FFmpeg, francotirador de video.
- dashboard_web.py: Servidor web en puerto 8000 con 4 consolas (timestamps a la derecha), desplegables de Hoy/Mañana e Histórico.
- error_buffer.py: Registro seguro de errores y sincronizador HTTP con la laptop Dell.
- sentinela_auditor.py: Centinela y Auditor Proactivo 24 Horas en Dell (puerto 5005) con auto-sanación inmediata e inmunidad permanente.
- registro_inmunidad.json: Catálogo de vacunas estructurales definitivas (INM-001 a INM-006).
- database.py: Manejo de SQLite 'clases.db', tabla 'clases_grabadas'.
- telegram_uploader.py: Subida por bloques a canales privados vía Telethon MTProto.
- notebooklm_bot.py: Transcripción y podcasts ejecutivos con reintentos.
- config.json: Credenciales de Telegram, Calendar Webhook, IPs de red local y tokens.
- 1_ENCENDIDO_MAESTRO.bat: Script batch de arranque ordenado para la laptop Acer.

INSTRUCCIÓN OPERATIVA:
Al recibir cualquier instrucción futura, verifica siempre primero la compatibilidad estructural, compila con 'python -m py_compile', preserva la lógica de negocio y aplica modificaciones quirúrgicas garantizando CERO REGRESIONES.
================================================================================"""
    )

    p_super = [
        [Preformatted(super_prompt_text, style_code)]
    ]
    t_super = Table(p_super, colWidths=[480])
    t_super.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#4A5568")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_super)

    # Construir documento final
    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente en: {PDF_OUTPUT_PATH}")

if __name__ == '__main__':
    construir_pdf()
