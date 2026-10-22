# 📖 MANUAL OFICIAL: Bot Universidad Online

> **Sistema Autónomo de Automatización, Scraping, Procesamiento Pedagógico con IA, LMS Interactivo y Despliegue Web**  
> *Versión del Sistema:* 5.0 Pro — Modo Fantasma, Panel Web Responsive & Nube Definitiva  
> *Entorno Operativo:* Windows 8.1 Pro (Python 3.8) | Estación de Control Remoto en Red Local (`Z:\`)

---

## 1. 🌍 Visión General del Ecosistema

El sistema **Bot Universidad Online** es una infraestructura de ingeniería distribuida diseñada para funcionar 24/7 en piloto automático, dividida estratégicamente en cuatro capas colaborativas:

```mermaid
flowchart TD
    ACER["💻 Laptop Acer (Motor Físico)
Windows 8 Pro + Python 3.8
Chrome CDP + FFmpeg + Telethon + Playwright"]
    DELL["💻 Laptop Dell (Estación de Control)
Acceso remoto por red local (Unidad Z:\)
Panel Web Responsive + Ingesta Manual + Edición"]
    TG["☁️ Telegram (Nube de Almacenamiento Definitiva)
Canal Privado: Masterclasses, Mentorías y Podcasts
Streaming Directo e Ilimitado"]
    GH["📱 GitHub Pages (App Web LMS Interactivo)
https://cursosfamiliaorellana-hue.github.io/universidad-online/
Flashcards 3D, Checklist LocalStorage, Mapa Panorámico"]

    DELL -->|Gestiona vía Red Z:\| ACER
    ACER -->|Graba y Sube Multimedia| TG
    ACER -->|Sube Metadatos e index.html| GH
    GH -->|Reproducción Streaming| TG
```

1. **💻 Laptop Acer (El Motor de Grabación y Procesamiento):**
   - Es la máquina física donde reside el repositorio compartido en red (`\\192.168.100.229\Bot_UniversidadOnline`).
   - Ejecuta los servicios y centinelas autónomos en **Modo Fantasma (100% invisible con `pythonw.exe`)**: Google Chrome en puerto CDP 9222, FFmpeg para captura en segundo plano con bajo consumo de CPU, el Vigía de Telegram con barrido histórico y captura en vivo vía Telegram Web, y el motor de IA Gemini / NotebookLM.
2. **💻 Laptop Dell (La Estación de Control y Monitoreo):**
   - Conectada a la Acer mediante la unidad de red mapeada `Z:\`.
   - Permite al usuario acceder al **Panel de Control Web (`http://127.0.0.1:8000`)** o ejecutar el Programador Manual, agendar clases, colocar archivos en las carpetas de Ingesta Manual, supervisar logs en vivo mediante consolas virtuales plegables o pausar el Vigía sin intervenir físicamente en la pantalla de la Acer.
3. **☁️ Telegram (La Nube de Almacenamiento Definitiva):**
   - Funciona como el almacén multimedia definitivo, ilimitado y de alta disponibilidad.
   - Cada clase grabada o procesada manualmente se sube a tu canal privado y se enlaza directamente. Esto permite purgar los gigabytes de videos locales (`.mp4`, `.m4a`) de la Acer sin que las clases desaparezcan de la App Web ni de Telegram.
4. **📱 GitHub Pages (La App Web LMS Interactiva en tu Celular):**
   - Despliegue web disponible en: **`https://cursosfamiliaorellana-hue.github.io/universidad-online/`**
   - Transforma tus grabaciones en una experiencia de aprendizaje completa: Flashcards interactivas con giro 3D, Checklist de estudio persistente con LocalStorage, Mapa Panorámico en 5 Fases, insignias de mentor/fecha y reproductor de audio/video directo.

---

## 2. 🚀 Los Archivos Ejecutables (.bat y .vbs)

Todos los componentes del sistema se inician mediante scripts por lotes y lanzadores silenciosos situados en la raíz de la carpeta:

| Archivo Ejecutable | Función y Descripción Técnica |
| :--- | :--- |
| **`1_ENCENDIDO_MAESTRO.bat`** | **🔥 Encendido Maestro en Modo Fantasma:** Lanza simultáneamente `main.py`, `vigia_mentorias.py` y `dashboard_web.py` de forma 100% invisible con `pythonw.exe` (0% de CPU gráfica) y abre automáticamente el Panel de Control Web en `http://127.0.0.1:8000`. |
| **`1_ENCENDIDO_MAESTRO.vbs`** | **Lanzador Invisible Total:** Ejecuta `1_ENCENDIDO_MAESTRO.bat` sin mostrar ninguna ventana de consola negra (cero parpadeo en el escritorio). |
| **`0_Instalar_Requisitos_Nueva_PC.bat`** | Script de aprovisionamiento inicial. Instala las librerías de Python (`requirements.txt`), descarga el motor Chromium para Playwright y verifica la presencia de `ffmpeg.exe`. Solo se ejecuta una vez al configurar una máquina nueva. |
| **`1_Abrir_Chrome_Hotmart.bat`** | **Imprescindible:** Inicia Google Chrome en el puerto de depuración remota `9222` usando un perfil independiente (`perfil_chrome`). Abre Hotmart y NotebookLM. Incluye banderas para evitar que Windows suspenda las pestañas en segundo plano. |
| **`2_Iniciar_Bot_Automatico.bat`** | **El Cerebro del Sistema (`main.py`):** Lanza el orquestador principal de forma individual. Sincroniza horarios con Google Calendar, espera silenciosamente las clases, ejecuta la grabación en vivo sin robar foco, analiza con IA, sube a Telegram y actualiza GitHub Pages. |
| **`3_Panel_Control_Web.bat`** | **Panel de Control Web Interactivo (`dashboard_web.py`):** Servidor Flask en `http://127.0.0.1:8000`. Permite ver la tabla en tiempo real de clases, consolas virtuales plegables de logs, Hot-Cancel inmediato, Re-grabación (Safe Overwrite), forzar subida a Telegram y borrado granular. |
| **`3_Reintentar_o_Repetir_Clase.bat`** | Lanza `gestor_regrabacion.py`. Permite seleccionar una clase fallida o repetida, aplicando Safe Overwrite para reactivarla en estado `PENDIENTE` sin borrar archivos previos hasta finalizar la nueva versión. |
| **`iniciar_sistema_silencioso.vbs`** | **Ejecutor Silencioso en Segundo Plano:** Lanza el orquestador automático de forma invisible sin desplegar ventanas negras de consola en el escritorio. |
| **`detener_sistema.bat`** | **Frenado Seguro del Sistema:** Detiene limpiamente procesos en segundo plano (FFmpeg, instancias de Python y túneles locales) sin dejar procesos zombi. |
| **`backup_cerebro.bat`** | **Respaldo Anti-Desastres (Disaster Recovery):** Genera copias timestamped de `clases.db` y `config.json` en `_backups_db/` y realiza push automático a GitHub para resguardar la memoria del sistema. |
| **`4_Abrir_App_en_Celular_Wifi.bat`** | Inicia un servidor web local en el puerto `8080` (`python -m http.server 8080`) para acceder a la PWA a través de la misma red Wi-Fi doméstica. |
| **`4_Programador_Manual.bat`** | **Centro de Control Interactivo CLI (`programador_manual.py`):** Interfaz CLI con Dashboard Operativo, Gestión Individual de Clases, Ingesta Manual, Hot-Cancel en tiempo real y administración de almacenamiento. |
| **`5_Abrir_App_en_Celular_Internet.bat`** | Muestra en pantalla el enlace público permanente de la App Web en GitHub Pages, ofrece instrucciones para instalar la PWA en el celular y abre el navegador web automáticamente. |
| **`5_Vigia_Mentorias.bat`** | **El Centinela Autónomo (`vigia_mentorias.py`):** Escucha en tiempo real canales privados y grupos de Telegram mediante Telethon. Incorpora barrido histórico al arrancar (Catch-Up), captura en vivo de llamadas vía Telegram Web y deduplicación inteligente cuando el mentor sube la grabación oficial. |
| **`6_Conectar_Con_GitHub.bat`** | Asistente de configuración Git. Aplica `safe.directory "*"` para evitar errores de permisos en Windows 8, configura el Personal Access Token (PAT) y vincula el repositorio remoto. |
| **`Login_Telegram.bat`** | Script interactivo para iniciar sesión en Telegram con Telethon una sola vez por SMS o código de app (`telegram_uploader.py --login`). Genera el archivo de sesión local. |
| **`Prueba_30_Segundos.bat`** | Prueba de integración rápida de 60 segundos (`prueba_30_segundos.py`). Graba la clase actual de Hotmart, procesa con Gemini y Telegram, validando que todo el ecosistema funcione correctamente. |

---

### ⏱️ Secuencia Recomendada para un Día Normal de Trabajo

Para encender la estación de trabajo y dejarla 100% operativa:

1. **Paso 1:** Enciende la laptop **Acer** y ejecuta **`1_Abrir_Chrome_Hotmart.bat`**. (Asegúrate de haber iniciado sesión en Hotmart).
2. **Paso 2:** Ejecuta **`1_ENCENDIDO_MAESTRO.vbs`** (o `1_ENCENDIDO_MAESTRO.bat`). Este comando único levantará en segundo plano invisible:
   - El Orquestador (`main.py`)
   - El Vigía de Telegram con Barrido Histórico (`vigia_mentorias.py`)
   - El Panel de Control Web (`dashboard_web.py`)
   - Y abrirá automáticamente el navegador en **`http://127.0.0.1:8000`**.
3. **Paso 3:** Desde tu laptop **Dell**, accede a través de la red local o abre el navegador en cualquier momento para monitorear las clases, agendar nuevas masterclasses o consultar las consolas de logs en vivo.

---

## 3. 🎛️ El Panel de Control Web Responsive (`dashboard_web.py`)

El nuevo Panel de Control Web centraliza el 100% de las funciones de gestión, control operativo y borrado granular en una interfaz web reactiva, moderna y compatible con pantallas de escritorio y teléfonos móviles (`http://127.0.0.1:8000`):

### 📊 Métricas Globales (KPIs en Tiempo Real)
- **Total Clases Registradas:** Contador global de contenidos en la biblioteca.
- **🔴 Grabando Ahora:** Detecta grabaciones activas con indicador visual parpadeante.
- **✅ En Telegram & Web:** Clases procesadas con éxito y disponibles en la nube.
- **⏳ Pendientes / Overwrite:** Sesiones agendadas o marcadas para re-grabación segura.
- **🎙️ Mentores Registrados:** Total de mentores vinculados a canales y grupos del Vigía.

### 🗑️ Gestión Granular de Borrado (3 Botones Independientes)
Para garantizar el control absoluto del almacenamiento y evitar pérdidas accidentales, cada fila de la tabla cuenta con tres botones de borrado con propósitos estrictamente diferenciados:
1. **`🗑️ Video Local`:**
   - Elimina **únicamente** el archivo físico pesado (`.mp4`, `.webm`, `.mkv`) del disco duro de la laptop.
   - Actualiza la base de datos dejando `ruta_archivo = ''`.
   - **Garantía:** El enlace a Telegram (`telegram_url`) y la ficha interactiva en la Web LMS permanecen 100% intactos. Puedes reproducir la clase en streaming desde Telegram en cualquier momento.
2. **`🗑️ Material IA`:**
   - Elimina los archivos de texto, infografías `.png`, quizzes y audios temporales generados localmente.
   - Mantiene la clase registrada en la base de datos y conserva el video y el post de Telegram.
3. **`🗑️ Eliminar Clase del Sistema`:**
   - Elimina el registro de la clase en la base de datos SQLite `clases.db` y purga su carpeta local.
   - Regenera automáticamente la App Web LMS en GitHub Pages para retirar la tarjeta del catálogo.
   - **Garantía Inquebrantable:** **NUNCA** realiza peticiones de borrado a la API de Telegram. Tu material grabado permanece a salvo en tu canal privado de Telegram.

### 📜 Consolas Virtuales Plegables al Pie (`<details>/<summary>`)
El panel integra tres consolas de terminal virtuales plegables que leen en vivo y en streaming los archivos de registro generados por los procesos en segundo plano:
1. **Consola 1: ⚡ Orquestador en Vivo (`main.py`)**: Monitorea la sala de espera, la detección de clases y el proceso de grabación con FFmpeg (`logs_orquestador.txt`).
2. **Consola 2: 🦅 Vigía de Telegram & Voice Chats (`vigia_mentorias.py`)**: Muestra los eventos de Telethon, detección de enlaces Zoom, barrido histórico y captura DOM con Playwright (`logs_vigia.txt`).
3. **Consola 3: 🖥️ Sistema Web & Dashboard (`dashboard_web.py`)**: Registra las peticiones HTTP, operaciones de borrado y sincronizaciones (`logs_sistema.txt`).

Cada consola incluye:
- Interruptor de **Auto-Scroll** para seguir los logs automáticamente.
- Botón de **Recargar** para actualización instantánea.
- Botón de **Limpiar** para vaciar el historial de la consola.

---

## 4. 🛠️ Operaciones CRUD Completas Integradas en la Web

Todas las capacidades del script de consola (`programador_manual.py`) están disponibles desde la barra de herramientas del Panel Web:

### 1. ➕ Programar Masterclass de Hotmart
Permite agendar una clase con URL directa de Hotmart o por búsqueda inteligente de título. Incluye selector para clases divididas en partes (Parte 1, Parte 2, etc.), cálculo automático de horario (si la hora ya pasó hoy, se programa para mañana) y duración estimada en minutos.

### 2. 🎙️ Programar o Iniciar Mentoría (Zoom / Chat de Voz Telegram)
Agenda o arranca inmediatamente una sesión de mentoría en vivo. Permite especificar el enlace de Zoom o dejarlo como `chat_voz_telegram` para que Playwright y FFmpeg capturen la sesión automáticamente como oyente silencioso ("David Herbas" con mic/cam off).

### 3. 🛑 Freno de Emergencia Inmediato
Escribe la señal `STOP` en `DETENER_GRABACION.txt`. El grabador en vivo intercepta la señal en menos de 1 segundo y cierra el archivo de video limpiamente mediante FFmpeg, preservando todo lo grabado hasta ese instante.

### 4. ⏸️ Pausar / Reanudar Vigía de Telegram
Silencia el Vigía de Telegram hasta las 23:59:59 del día en curso. Ideal cuando deseas asistir a tus clases o reuniones desde tu laptop personal sin que el bot de la laptop Acer interfiera ni grabe la llamada. Al día siguiente (o al hacer clic en `▶️ Reanudar Vigía`), el centinela vuelve a escuchar automáticamente.

### 5. ✏️ Modificar Mentor ("Efecto Dominó")
Corrige el nombre de un mentor en una clase grabada y propaga el cambio en cascada de forma automática:
- Renombra el archivo físico `.mp4` en el disco local.
- Actualiza el registro, el título y los metadatos en SQLite `clases.db`.
- Edita el pie de mensaje (caption) del post original en Telegram mediante la API de Telethon.
- Reconstruye y publica la App Web actualizada en GitHub Pages.

### 6. 👥 Gestión de Mentores y Grupos Privados
Permite añadir nuevos mentores, asignarles sus palabras clave de identificación para Telegram, clasificar su especialidad (Tráfico, Ventas, Copywriting) o dar de alta canales generales para barrido histórico.

### 7. 📥 Escanear Ingesta Manual y Playbooks
Dispara en segundo plano el escaneo de las cuatro carpetas de ingesta (`Z:\Ingesta_Manual\Masterclasses`, `Mentorias`, `Grabaciones_Independientes` y `Playbooks_Externos`), procesando videos, audios y PDFs nuevos con análisis de IA y subida directa a Telegram.

### 8. 🔍 Auditar y Rescatar Procesos Incompletos
Examina la base de datos y el disco en busca de grabaciones que hayan quedado pendientes de subida a Telegram (por cortes de energía o internet) o tareas encoladas de NotebookLM, reanudando su procesamiento automáticamente.

### 9. 🔁 Re-grabar Seguro (Safe Overwrite)
Marca una clase para ser re-grabada en el siguiente horario disponible, manteniendo intactos los videos y enlaces actuales en la App Web hasta que la nueva grabación termine satisfactoriamente.

### 10. 🛑 Hot-Cancel en Tiempo Real
Permite cancelar una grabación en curso o una tarea pendiente de la cola sin necesidad de reiniciar procesos ni apagar el sistema.

---

## 5. 📥 Guía de Ingesta Manual y Playbooks Externos

Si tienes clases grabadas con OBS, Zoom, podcasts descargados o guías en PDF que no fueron capturadas por el bot automático, puedes agregarlas al sistema en cuestión de segundos usando las 4 carpetas de ingesta:

```text
Z:\
├── Ingesta_Manual\
│   ├── Masterclasses\                 <-- Coloca videos (.mp4, .mkv, .webm) de clases formales
│   ├── Mentorias\                     <-- Coloca sesiones de mentoría (.mp4, .m4a, .mp3)
│   └── Grabaciones_Independientes\    <-- Entrevistas, talleres o llamadas sueltas
└── Playbooks_Externos\                 <-- PDFs, documentos .md, resúmenes o playbooks estratégicos
```

### 📋 Paso a Paso para Ingestar Material:
1. Copia tus archivos multimedia o documentos en la carpeta correspondiente dentro de `Z:\Ingesta_Manual\` o `Z:\Playbooks_Externos\`.
2. Puedes nombrarlos con claridad, por ejemplo:
   - `Z:\Ingesta_Manual\Masterclasses\2026-10-20_Copywriting_Persuasivo.mp4`
   - `Z:\Ingesta_Manual\Mentorias\Marcos_Mentalidad_Ganadora.m4a`
   - `Z:\Playbooks_Externos\Playbook_Lanzamientos_2026.pdf`
3. Desde el Panel Web, haz clic en el botón **`📥 Escanear Ingesta`** (o usa la Opción 3 en `4_Programador_Manual.bat`).
4. **¿Qué hace el bot automáticamente?**
   - Registra el hash del archivo en la tabla de **Memoria Viva** (`ingesta_manual_registro`) para evitar duplicaciones futuras.
   - Envía el audio o documento a la API de **Gemini / NotebookLM** para generar: Resumen ejecutivo, Infografía de pasos, Checklist de 15 minutos, Quiz de autoevaluación y **Flashcards interactivas**.
   - Sube el archivo multimedia a tu canal privado de **Telegram** generando su enlace de streaming directo.
   - Regenera la App Web y la publica en **GitHub Pages**.

---

## 6. 🦅 El Vigía de Telegram Avanzado (`vigia_mentorias.py`)

El Vigía de Telegram no solo escucha mensajes entrantes; cuenta con tres mecanismos de inteligencia autónoma:

### 1. Barrido Histórico (Catch-Up) al Iniciar
Cada vez que se inicia el Vigía:
- Consulta la tabla `configuracion_vigia` en SQLite para conocer la fecha y hora exacta de la última desconexión.
- Si la PC estuvo apagada o sin internet durante horas o días, el Vigía ejecuta un barrido con `client.iter_messages` revisando todos los canales y grupos de mentores registrados.
- Procesa cualquier link de Zoom, cápsula de valor o aviso emitido durante la ausencia, evitando que te pierdas información valiosa.
- Actualiza la marca temporal de última ejecución para el siguiente reinicio.

### 2. Captura en Vivo de Llamadas vía Telegram Web
Cuando un mentor o el grupo "Universidad Online" inicia una llamada de voz o video chat en vivo:
- Si Telethon no puede capturar el stream nativo, el Vigía activa el módulo de grabación de **Playwright** (`recorder.grabar_llamada_telegram_web`).
- Playwright conecta con Google Chrome mediante CDP (`localhost:9222`), abre una pestaña aislada en `web.telegram.org` e ingresa al grupo de la llamada.
- **Seguridad Garantizada:** Bloquea por completo el micrófono y la cámara para que el bot entre en modo oyente 100% silencioso.
- Inicia la captura de audio/pantalla con FFmpeg y vigila constantemente el DOM de Telegram Web.
- Cuando la llamada finaliza (o la UI muestra "Llamada finalizada"), detiene la grabación limpiamente, envía el audio a NotebookLM/Gemini y publica la sesión.

### 3. Deduplicación Inteligente y Sustitución Oficial
- Es común que un mentor primero transmita una llamada en vivo y, horas después, suba al grupo el archivo de video oficial en alta calidad.
- Si el Vigía detecta que el mentor subió la grabación oficial correspondiente a una sesión que ya había sido grabada en vivo de forma preliminar:
  - **No duplica la clase:** Localiza el registro previo en SQLite mediante `buscar_mentoria_por_mentor_y_fecha`.
  - Reemplaza el audio preliminar por el archivo oficial de alta fidelidad.
  - Sube la versión definitiva a Telegram, re-analiza con IA y actualiza la App Web sin generar clases duplicadas.

---

## 7. 📱 Plataforma LMS Interactiva y App Web (GitHub Pages)

La App Web alojada en **`https://cursosfamiliaorellana-hue.github.io/universidad-online/`** es una plataforma de aprendizaje activo:

### 🎴 Flashcards Interactivas con Giro 3D
- Cada clase, mentoría o cápsula cuenta con tarjetas de memoria para repasar conceptos críticos.
- Al hacer clic o tocar una flashcard, la tarjeta realiza una animación de giro 3D (flip card) revelando la respuesta estratégica.
- Incluye indicadores de dificultad (*Básica*, *Intermedia*, *Avanzada*) para optimizar tus sesiones de estudio.

### ✅ Checklist de Estudio con Persistencia en LocalStorage
- En la cabecera de cada tarjeta de clase encontrarás un botón interactivo: **`Marcar como Estudiada`**.
- Al activarlo, el estado se guarda inmediatamente en el almacenamiento local de tu navegador (`localStorage`), de modo que tus progresos se mantienen intactos aunque recargues la página o cierres el navegador.
- La barra superior de progreso te muestra el porcentaje dinámico de clases completadas y el número exacto de sesiones dominadas.

### 🗺️ Mapa Panorámico de Estudio (Roadmap en 5 Fases)
El aprendizaje se organiza en una ruta secuencial y estructurada en 5 fases progresivas:
1. **Fase 1: Fundamentos y Estrategia Base**
2. **Fase 2: Creación y Oferta Irresistible**
3. **Fase 3: Tráfico y Adquisición de Prospectos**
4. **Fase 4: Ventas, Cierres y Conversión**
5. **Fase 5: Escalamiento y Automatización**

Al hacer clic en cualquier fase del mapa, la plataforma filtra instantáneamente las clases correspondientes.

### ⭐ Insignia de Clase Clave
Las clases con mayor potencial e impacto práctico se destacan con la insignia **`⭐ Clase Clave`**.

---

## 8. 🛡️ Centinela y Auditor Proactivo 24 Horas & Optimización Visual de Zoom

El sistema cuenta con un **Centinela y Auditor Proactivo 24 Horas** ejecutándose de forma ininterrumpida en la Laptop Dell (puerto `5005`):

### 👁️ Vigilancia y Auto-Sanación Inmediata
- **Auditoría de Horarios:** Verifica cada 25 segundos que las clases y mentorías agendadas en `clases.db` arranquen puntualmente. Si una clase en horario no ha iniciado, dispara automáticamente re-grabación forzada y notifica al Orquestador.
- **Protección de Grabaciones en Vivo:** Si el Orquestador o el grabador se encuentran en estado `GRABANDO`, el Centinela protege el proceso activo garantizando 0% de interrupciones.
- **Vigilancia de Anuncios en Telegram:** Inspecciona continuamente los registros de Telegram. Si se detecta un enlace de Zoom en los últimos minutos que no haya sido agendado, el Centinela lo rescata y lo agenda vía API inmediatamente.
- **Matriz de Inmunidad Permanente (`registro_inmunidad.json`):** Todo error resuelto se documenta estructuralmente (INM-001 a INM-008) para que no vuelva a ocurrir nunca más.

### 🎥 Optimización Visual Automática de Zoom Web
Durante la captura de cualquier mentoría de Zoom, el motor ejecuta `optimizar_entorno_zoom()` cada 10 segundos:
1. **Presentación Maximizada ('Lado a lado: orador'):** Conmuta la vista de Zoom para que la pantalla compartida o diapositivas queden en formato grande y legible, mientras el mentor expositor permanece visible de forma compacta a un costado o arriba.
2. **Conexión de Audio Post-Sala de Espera:** Contempla el tiempo de espera (1 a 2 minutos) hasta que el bot anfitrión admite la entrada. Al ser admitido, detecta el diálogo modal y conecta automáticamente *"Audio por computadora"* (*"Join Audio by Computer"*).
3. **Supresión de Banners de Aceleración y Notificaciones:** Inyecta reglas de estilo persistentes y presiona los botones de cierre 'X' para descartar avisos de aceleración de gráficos por hardware, alertas flotantes y cookies que tapen el video grabado.
4. **Privacidad Blindada:** Garantiza en todo momento que el Micrófono y la Cámara del bot permanezcan estrictamente en **OFF/MUTED**.
5. **Deduplicación de Pestañas:** Inspecciona el navegador y cierra limpiamente cualquier pestaña huérfana o duplicada de Zoom.

---

## 9. 🛡️ Protocolo de Recuperación ante Desastres (Disaster Recovery)

El sistema implementa una arquitectura de **Resiliencia Total y Desacoplamiento de Datos**:
- **El Almacén Multimedia:** Los videos residen en los canales privados de Telegram (almacenamiento ilimitado y gratuito de alta velocidad con Telethon y `cryptg`).
- **El Cerebro del Sistema (`clases.db`):** Es una base de datos SQLite ultraligera que almacena toda la metadata histórica, URLs de streaming en Telegram, cuadernos de NotebookLM, clasificaciones Pareto 80/20, checklists y flashcards.
- **La Interfaz Web Serverless (`index.html` + `data.json`):** Desplegada en GitHub Pages, hidrata la App Web de forma asíncrona sin consumir CPU de tu equipo.

### 💾 Respaldo Automático de la Memoria
1. Ejecuta **`backup_cerebro.bat`** cuando desees generar un punto de restauración seguro o antes de formatear/cambiar de equipo.
2. El script genera una copia de seguridad timestamped en la carpeta local `_backups_db/` (ej. `_backups_db\clases_backup_20261020_174328.db`).
3. Sube automáticamente los metadatos y la base de datos a tu repositorio privado en GitHub.

### 💻 Restaurar en una Laptop Nueva (Desde Cero)
1. **Paso 1:** Clonar el repositorio desde GitHub (`git clone https://github.com/cursosfamiliaorellana-hue/universidad-online.git`).
2. **Paso 2:** Ejecutar `0_Instalar_Requisitos_Nueva_PC.bat` para instalar dependencias de Python y Playwright.
3. **Paso 3:** Colocar tu archivo `config.json` con tokens y credenciales.
4. **Paso 4:** Iniciar sesión en Telegram con `Login_Telegram.bat` y en Chrome con `1_Abrir_Chrome_Hotmart.bat`.
5. **Paso 5:** Ejecutar `1_ENCENDIDO_MAESTRO.vbs` para encender el sistema en Modo Fantasma y acceder a `http://127.0.0.1:8000`.

---
> **Documento Oficial de Ingeniería:** Bot Universidad Online Pro  
> Todos los derechos reservados © 2026.
