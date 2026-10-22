# SISTEMA AUTOMATIZADO DE GRABACIÓN, ANÁLISIS CON IA Y AUTO-SANACIÓN
## UNIVERSIDAD ONLINE - MANIFIESTO MAESTRO Y SUPER PROMPT DE RESTAURACIÓN TOTAL (DISASTER RECOVERY)

> **Documento Confidencial de Arquitectura y Restauración Integral**  
> **Fecha de Emisión:** 21 de Octubre de 2026  
> **Autor:** Arquitecto de Software Principal & Antigravity AI Agent  
> **Hardware:** Laptop Acer (Cliente Operativo / Hotmart / Chrome) & Laptop Dell (Agente Antigravity / IA)

---

## ÍNDICE GENERAL
1. **Visión General y Filosofía de Arquitectura (Cero Regresiones)**
2. **Topología de Red y Comunicación Bidireccional (Acer <-> Dell)**
3. **Catálogo de Archivos y Responsabilidades de Módulos**
4. **Esquema Completo de Base de Datos SQLite (clases.db)**
5. **Configuración de Variables y Conexiones Externas (config.json)**
6. **Lógica de Negocio y Reglas Operativas Inquebrantables**
7. **Arquitectura de Consolas, UX y Auto-Sanación (Offline-First)**
8. **Scripts de Lanzamiento y Control (.bat)**
9. **SUPER PROMPT MAESTRO DE RESTAURACIÓN TOTAL (Copia y Pega para Antigravity)**

---

## 1. VISIÓN GENERAL Y FILOSOFÍA DE ARQUITECTURA
El **Bot Universidad Online** es una suite empresarial de automatización desatendida diseñada para la captura, procesamiento pedagógico y distribución multi-canal de contenidos educativos (Masterclasses de Hotmart y Mentorías grupales en Zoom y Telegram).

### Principios Rectores:
- **Modo Fantasma 100% Invisible:** Todos los motores de fondo (`pythonw.exe`) operan sin ventanas negras de consola en el escritorio del usuario.
- **Aislamiento Estricto de Pestañas:** Cada grabación se ejecuta en una pestaña aislada de Chrome mediante Chrome DevTools Protocol (CDP puerto 9222), permitiendo grabaciones concurrentes sin colisión.
- **Semáforo de Red y CPU:** Durante una grabación en vivo, el semáforo pasa a **ROJO**, pausando tareas intensivas (subidas pesadas a Telegram, peticiones a NotebookLM) para garantizar 0% de buffering en el video.
- **Auto-Sanación (Self-Healing):** Todo fallo se almacena localmente en `registro_errores.json` (Offline-First) y se sincroniza en segundo plano hacia la Laptop Dell para diagnóstico y resolución inmediata.

---

## 2. TOPOLOGÍA DE RED Y PROTOCOLO DE AUTO-SANACIÓN
- **Laptop Acer (Cliente de Ejecución):**
  - IP Local: `192.168.100.229`
  - Carpeta Raíz Compartida: `\192.168.100.229\Bot_UniversidadOnline` (montada en Dell como unidad `Z:\`)
  - Ejecuta: Google Chrome con `--remote-debugging-port=9222`, perfil local `perfil_chrome`, Flask Web Dashboard en puerto 8000, Orquestador (`main.py`) y Vigía (`vigia_mentorias.py`).
- **Laptop Dell (Agente Antigravity IA):**
  - IP Local: `192.168.100.243`
  - Acceso directo al código, base de datos y logs a través de `Z:\`.
  - Endpoint de sincronización HTTP: `http://192.168.100.243:5005/api/antigravity/sync_errores`
  - Hilo en segundo plano en Flask envía errores pendientes cada 5 minutos de forma silenciosa.

---

## 3. CATÁLOGO DE ARCHIVOS Y RESPONSABILIDADES
- **`main.py`:** Orquestador principal del sistema. Sincroniza calendarios con Google Calendar Webhook, monitorea horarios, acciona grabaciones de Hotmart, gestiona el Semáforo de Red/CPU y la cola de post-procesamiento.
- **`recorder.py`:** Motor de captura de video y audio. Se conecta vía Playwright CDP al puerto 9222 de Chrome, localiza la clase en Hotmart, maneja Zoom Web como 'David Herbas', graba con FFmpeg en WebM crudo y remuxea a MP4 con salvaguarda anti-destrucción.
- **`vigia_mentorias.py`:** Agente de escucha continua conectado a la API de Telegram (Telethon). Detecta inicio de llamadas de voz / videochats en canales monitoreados y dispara capturas automáticas.
- **`dashboard_web.py`:** Servidor web Flask (puerto 8000) con interfaz responsiva, control de clases, borrado granular (local vs nube), modales de programación manual y 4 consolas virtuales en vivo.
- **`error_buffer.py`:** Módulo offline-first para registro atómico de fallos en `registro_errores.json` e hilo de sincronización cada 5 minutos con la laptop Dell.
- **`database.py`:** Capa de abstracción SQLite con funciones para consultas, creación de tablas, bloqueo de concurrencia y actualización de estados.
- **`telegram_uploader.py`:** Gestor de envíos asíncronos a Telegram con división inteligente de archivos grandes, miniaturas automáticas y plantillas con formato didáctico.
- **`notebooklm_bot.py`:** Automatizador de Google NotebookLM para carga de audios/transcripciones y generación de podcasts interactivos y guías de estudio.
- **`route_builder.py`:** Generador del tablero interactivo de rutas de aprendizaje pedagógicas y sincronizador con Netlify y GitHub Pages.
- **`scraper.py`:** Extractor inteligente de lecciones y enlaces directamente del HTML de la membresía de Hotmart.
- **`calendar_sync.py`:** Cliente HTTP para sincronización con el Webhook de Google Apps Script.
- **`sentinela_auditor.py`:** Centinela y Auditor Proactivo 24 Horas ejecutándose en la Laptop Dell (puerto 5005). Vigila omisiones de horarios, caídas de procesos, reanima el orquestador vía API y administra las reglas de inmunidad permanente.
- **`registro_inmunidad.json`:** Matriz de conocimiento acumulado que documenta las curas estructurales definitivas (INM-001 a INM-006) para garantizar que los errores resueltos nunca se repitan.

---

## 4. ESQUEMA DE BASE DE DATOS SQLITE (clases.db)
La base de datos contiene las siguientes tablas maestras:
- **`clases_grabadas`:**
  - `id_clase` (TEXT PRIMARY KEY)
  - `titulo_original` (TEXT)
  - `fecha_grabacion` (TEXT - ISO format con offset -04:00)
  - `estado` (TEXT - PENDIENTE, GRABANDO, COMPLETADA, OCULTA, ERROR_REMUXING)
  - `ruta_archivo` (TEXT - Ruta local al video .mp4)
  - `transversal` (TEXT)
  - `nivel` (INTEGER)
  - `duracion_min` (INTEGER)
  - `analisis_json` (TEXT)
  - `notebook_url` (TEXT)
  - `podcast_archivo` (TEXT)
  - `url_hotmart` (TEXT)
  - `telegram_url` / `telegram_web_url` (TEXT)
  - `mentor` (TEXT)
  - `regrabacion_activa` (INTEGER)
- **`mentores_grupos`:** Registro de mentores, palabras clave y canales vinculados.
- **`notebooklm_cola_reintentos`:** Tareas pendientes de podcast para reanudación automática.
- **`configuracion_vigia`:** Estado de pausa temporal del vigía de Telegram.

---

## 5. REGLAS DE NEGOCIO INQUEBRANTABLES
1. **Entrada Anticipada (5 Minutos):** El orquestador activa la captura 300 segundos antes del horario oficial de la clase para no perder el saludo ni la introducción.
2. **Margen Dinámico Posterior (5 Minutos):** Se añaden 5 minutos al final de la grabación por si la clase se extiende. Si existe una clase inmediatamente posterior (diferencia menor a 300 segundos), el margen se reduce automáticamente a 0 para evitar solapamientos.
3. **Delay de Seguridad (Cooldown 10 Min):** Si una captura falla o se aborta, se activa un delay de seguridad de 600 segundos para dicha clase, evitando que el bot cree pestañas infinitas y sature la memoria RAM.
4. **Preservación Cruda Anti-Destrucción:** Si la conversión de WebM a MP4 sufriera una interrupción, el archivo `.webm` nunca se borra y se preserva en disco con estado `ERROR_REMUXING`.
5. **Borrado Granular Independiente:** El borrado de un video pesado local en el panel jamás elimina el enlace en Telegram ni la ficha en la App Web.
6. **Inmunidad Estructural Permanente:** Todo error resuelto se repara de raíz en el código fuente, se registra en `registro_inmunidad.json` y se compila sin regresiones para evitar recurrencias.
7. **Auditoría Semántica Proactiva 24/7:** El servicio `sentinela_auditor.py` en Dell audita que las clases inicien a tiempo y auto-sana omisiones de forma inmediata.

---

## 6. SUPER PROMPT MAESTRO DE RESTAURACIÓN TOTAL (DISASTER RECOVERY)

```markdown
====================================================================================================
               SUPER PROMPT DE RESTAURACIÓN TOTAL - BOT UNIVERSIDAD ONLINE
====================================================================================================
INSTRUCCIÓN PARA ANTIGRAVITY:
Actúa como el Arquitecto de Software Principal. He perdido mi entorno de desarrollo local y necesito
que reconstruyas el Sistema Completo del "Bot Universidad Online" exactamente con su arquitectura
empresarial, modular, resiliente y libre de regresiones.

DIRECTIVAS ARQUITECTÓNICAS CRÍTICAS:
1. PLATAFORMA Y COMUNICACIÓN:
   - Laptop Acer (Cliente Operativo: Hotmart, Chrome CDP 9222, Panel Web Flask puerto 8000).
   - Laptop Dell (Agente Antigravity / IA, IP 192.168.100.243, Centinela Auditor puerto 5005).
   - Ruta base de trabajo: Carpeta compartida montada o directorio local del bot.
2. DEPENDENCIAS REQUERIDAS:
   - Python 3.8+ a 3.12, Flask, Flask-CORS, Playwright 1.28.0 (Windows 8 Node 16 compat), Telethon,
     requests, pytz, schedule, ffmpeg-python (o ejecutable ffmpeg.exe local), reportlab.
3. MÓDULOS OBLIGATORIOS QUE DEBES RECREAR:
   a) 'error_buffer.py': Sistema de buffer de errores Offline-First en 'registro_errores.json'.
   b) 'sentinela_auditor.py': Centinela y Auditor Proactivo 24 Horas en Dell (puerto 5005) con bucle de auditoría
      integral de horarios, salud del orquestador y gestión de 'registro_inmunidad.json'.
   c) 'registro_inmunidad.json': Matriz de reglas de inmunidad permanente (INM-001 a INM-006).
   d) 'database.py': Gestión completa de SQLite ('clases.db') con tabla 'clases_grabadas'.
   e) 'main.py': Orquestador concurrente con detección de horarios (-300s entrada anticipada),
      margen dinámico, semáforo de Red/CPU, latido continuo y cola asíncrona de post-procesamiento.
   f) 'recorder.py': Motor Playwright CDP puerto 9222 con buscador adaptativo (Score > 15),
      aislamiento de pestañas, modo francotirador, play ante pausas y remuxing seguro.
   g) 'vigia_mentorias.py': Monitoreo invisible con Telethon en segundo plano para llamadas de voz
      y videochats en canales de Telegram.
   h) 'telegram_uploader.py': Subida asíncrona de videos a Telegram con división y portadas.
   i) 'notebooklm_bot.py': Automatización de Google NotebookLM para audios de estudio.
   j) 'route_builder.py': Generador del tablero LMS interactivo y publicador a GitHub Pages.
   k) 'dashboard_web.py': Servidor web Flask puerto 8000 con watchdog de 120s, borrado granular,
      4 consolas con timestamps en columna derecha y botones de copiado y sincronización web.
   l) '1_ENCENDIDO_MAESTRO.bat': Script de arranque unificado en un clic.

REGLAS DE NEGOCIO:
- Modo Fantasma: Procesos en segundo plano sin ventanas emergentes de consola.
- Semáforo de Red: 0% descargas/subidas pesadas mientras haya grabaciones activas.
- Zero Regressions: Toda la lógica de negocio se preserva íntegra.

Genera cada uno de estos archivos con código limpio, robusto y listo para producción inmediata.
====================================================================================================
```
