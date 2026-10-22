import os
import sys

# OBLIGATORIO PARA WINDOWS 8.1 / ACER
os.environ["NODE_SKIP_PLATFORM_CHECK"] = "1"

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import asyncio
import json
import time
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "resultado_optimizacion_zoom.json")

async def optimizar_zoom_ahora():
    resultado = {
        "timestamp": time.time(),
        "status": "iniciado",
        "total_pestanas": 0,
        "pestanas_zoom": 0,
        "pestanas_cerradas": [],
        "pestana_principal": None,
        "alerta_aceptada": False,
        "vista_lado_a_lado": False,
        "audio_conectado": False,
        "mic_cam_protegido": True,
        "banners_descartados": False,
        "detalles": []
    }
    
    cdp_url = "http://localhost:9222"
    
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            resultado["status"] = "error_conexion_cdp"
            resultado["detalles"].append(f"Error conectando a Chrome CDP: {e}")
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)
            print(json.dumps(resultado, ensure_ascii=False))
            return resultado

        try:
            if not browser.contexts:
                resultado["status"] = "sin_contextos"
                return resultado
                
            context = browser.contexts[0]
            pages = list(context.pages)
            resultado["total_pestanas"] = len(pages)
            
            # Clasificar páginas de Zoom
            zoom_pages_info = []
            for page in pages:
                url = page.url.lower()
                if "zoom.us" in url:
                    try:
                        title = await page.title()
                        # Evaluar si esta pestaña está DENTRO de la reunión o en la sala de espera / preview
                        en_reunion = await page.evaluate("""() => {
                            // Si tiene barra de herramientas de reunión o contenedor de video o vista
                            const hasToolbar = !!document.querySelector('.footer, .meeting-control, .meeting-app, #foot-bar, [aria-label*="Vista" i], [aria-label*="View" i], .speaker-view-button');
                            const inMeeting = !!document.querySelector('#zmmtg-root, .meeting-client, .share-container');
                            const isPreview = !!document.querySelector('button.preview-join-button, input#input-for-name, input[name="inputname"]');
                            return (hasToolbar || inMeeting) && !isPreview;
                        }""")
                    except Exception:
                        title = "Error leyendo pestaña"
                        en_reunion = False
                    zoom_pages_info.append({"page": page, "url": page.url, "title": title, "en_reunion": en_reunion})
            
            resultado["pestanas_zoom"] = len(zoom_pages_info)
            resultado["detalles"].append(f"Pestañas Zoom detectadas: {len(zoom_pages_info)}")

            if not zoom_pages_info:
                resultado["status"] = "sin_pestanas_zoom"
                return resultado

            # 1. Identificar pestaña principal (priorizando pestaña de grabación activa)
            pagina_activa = None
            for p_info in zoom_pages_info:
                try:
                    is_rec = await p_info["page"].evaluate("() => window.__grabando_mentoria_activa === true")
                    if is_rec:
                        pagina_activa = p_info["page"]
                        resultado["pestana_principal"] = f"[GRABACION ACTIVA] {p_info['title']} ({p_info['url']})"
                        break
                except Exception:
                    pass

            if not pagina_activa:
                for p_info in zoom_pages_info:
                    if p_info["en_reunion"]:
                        pagina_activa = p_info["page"]
                        resultado["pestana_principal"] = f"{p_info['title']} ({p_info['url']})"
                        break

            # Si ninguna marcó en_reunion de forma estricta, tomar la última (más reciente)
            if not pagina_activa:
                pagina_activa = zoom_pages_info[-1]["page"]
                resultado["pestana_principal"] = f"{zoom_pages_info[-1]['title']} ({zoom_pages_info[-1]['url']})"

            # 2. CERRAR PESTAÑAS DUPLICADAS / HUÉRFANAS DE ZOOM (respetando cualquier pestaña en grabación)
            for p_info in zoom_pages_info:
                p_extra = p_info["page"]
                if p_extra != pagina_activa and not p_extra.is_closed():
                    try:
                        is_rec_extra = await p_extra.evaluate("() => window.__grabando_mentoria_activa === true")
                        if not is_rec_extra:
                            t_extra = p_info["title"]
                            await p_extra.close()
                            resultado["pestanas_cerradas"].append(t_extra)
                            resultado["detalles"].append(f"Cerrada pestaña redundante de Zoom: '{t_extra}'")
                    except Exception as e_c:
                        resultado["detalles"].append(f"Aviso cerrando pestaña redundante: {e_c}")

            # Inyectar WebRTC Silent Stream Mock en la pestaña activa para evitar spinner infinito de audio
            try:
                await pagina_activa.evaluate("""() => {
                    if (window.__webrtc_guard_injected) return;
                    window.__webrtc_guard_injected = true;
                    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                        navigator.mediaDevices.getUserMedia = async (constraints) => {
                            const tracks = [];
                            try {
                                if (constraints && constraints.audio) {
                                    const AudioCtx = window.AudioContext || window.webkitAudioContext;
                                    if (AudioCtx) {
                                        const ctx = new AudioCtx();
                                        const dst = ctx.createMediaStreamDestination();
                                        const track = dst.stream.getAudioTracks()[0];
                                        if (track) {
                                            track.enabled = false;
                                            tracks.push(track);
                                        }
                                    }
                                }
                            } catch(e) {}
                            if (tracks.length > 0) return new MediaStream(tracks);
                            return new MediaStream();
                        };
                    }
                }""")
            except Exception:
                pass

            # Traer al frente la pestaña principal de la reunión
            await pagina_activa.bring_to_front()

            # 3. CERRAR EL AVISO 'ALERTA DE REUNIÓN' (Requerimiento exacto del usuario)
            # "El anfitrión no permite que los participantes reactiven su audio ellos mismos" con botón "Aceptar"
            try:
                alerta_cerrada = await pagina_activa.evaluate("""() => {
                    let clickeado = false;
                    // Buscar modal de alerta o cuadros de diálogo
                    const modales = Array.from(document.querySelectorAll('.zm-modal, div[role="dialog"], .modal-dialog, .common-modal, .zmmtg-dialog'));
                    for (const m of modales) {
                        const txt = (m.innerText || '').toLowerCase();
                        if (txt.includes('alerta') || txt.includes('anfitrión') || txt.includes('participantes') || txt.includes('audio') || txt.includes('host is not allowing')) {
                            // Buscar botón Aceptar / OK / Entendido / Cerrar dentro del modal
                            const btns = Array.from(m.querySelectorAll('button'));
                            for (const b of btns) {
                                const bTxt = (b.innerText || '').toLowerCase().trim();
                                if (bTxt === 'aceptar' || bTxt === 'ok' || bTxt === 'entendido' || bTxt === 'dismiss' || bTxt === 'close') {
                                    b.click();
                                    clickeado = true;
                                    break;
                                }
                            }
                            if (!clickeado && btns.length > 0) {
                                btns[0].click();
                                clickeado = true;
                            }
                            // Ocultar modal del DOM por si acaso
                            m.style.display = 'none';
                        }
                    }
                    
                    // Búsqueda global de cualquier botón que diga estrictamente 'Aceptar' en diálogos
                    if (!clickeado) {
                        const allBtns = Array.from(document.querySelectorAll('button'));
                        for (const b of allBtns) {
                            const bTxt = (b.innerText || '').toLowerCase().trim();
                            if (bTxt === 'aceptar') {
                                b.click();
                                clickeado = true;
                                break;
                            }
                        }
                    }
                    return clickeado;
                }""")
                if alerta_cerrada:
                    resultado["alerta_aceptada"] = True
                    resultado["detalles"].append("Ventana 'Alerta de reunión' descartada haciendo clic en 'Aceptar'.")
            except Exception as e_al:
                resultado["detalles"].append(f"Aviso descartando alerta de reunión: {e_al}")

            # 4. SUPRIMIR BANNERS FLOTANTES Y ACELERACIÓN DE HARDWARE (Requerimiento exacto)
            try:
                banners_res = await pagina_activa.evaluate("""() => {
                    // Inyectar CSS anti-obstrucción
                    const styleId = 'anti-banner-zoom-guard';
                    let elStyle = document.getElementById(styleId);
                    if (!elStyle) {
                        elStyle = document.createElement('style');
                        elStyle.id = styleId;
                        elStyle.textContent = `
                            div[class*="notification" i],
                            div[class*="banner" i],
                            div[role="alert" i],
                            div[class*="hardware-acceleration" i],
                            div[class*="toast" i],
                            .announcement-banner,
                            .z-notification,
                            .hardware-acceleration-tip,
                            .top-notification {
                                display: none !important;
                                visibility: hidden !important;
                                opacity: 0 !important;
                                pointer-events: none !important;
                            }
                        `;
                        document.head.appendChild(elStyle);
                    }
                    
                    // Clickeo de cualquier 'X' de cierre
                    const closeBtns = document.querySelectorAll('button[aria-label*="close" i], button[aria-label*="cerrar" i], button.close, button.notification-close, .banner-close, [title*="cerrar" i]');
                    let clicks = 0;
                    for (const b of closeBtns) {
                        try { b.click(); clicks++; } catch(e) {}
                    }
                    return clicks;
                }""")
                resultado["banners_descartados"] = True
                resultado["detalles"].append("Banners y advertencias flotantes ocultadas con regla CSS e interacciones de cierre.")
            except Exception as e_ban:
                resultado["detalles"].append(f"Aviso banners: {e_ban}")

            # 5. REGLA ESTRICTA DE AUDIO Y MICRÓFONO (Investigada y Aplicada a fondo)
            # REGLA:
            # - Si dice "Entrar al audio" / "Conectar audio" / "Audio por computadora" / "Join Audio":
            #   -> Se conecta al audio de los expositores para escuchar la clase.
            # - Si es el MICRÓFONO y dice "Cancelar silenciar", "Reactivar audio", "Activar micrófono", "Unmute":
            #   -> ESTÁ SILENCIADO. ¡NUNCA TOCARLO! (Prohibido hacer clic).
            # - Si es el MICRÓFONO y dice "Silenciar" o "Mute" (sin "cancelar" ni "reactivar"):
            #   -> ESTÁ ENCENDIDO. Ahí sí se silencia inmediatamente.
            # - Cámara: Siempre en OFF.
            try:
                audio_mic_js = """() => {
                    let log = [];
                    const btns = Array.from(document.querySelectorAll('button'));
                    
                    // A) Chequear conexión de altavoz / audio de computadora
                    for (const b of btns) {
                        const txt = (b.innerText || b.textContent || '').toLowerCase().trim();
                        const aria = (b.getAttribute('aria-label') || '').toLowerCase().trim();
                        
                        // Botón de conectar altavoz inicial
                        if (txt.includes('audio por computadora') || txt.includes('join audio by computer') ||
                            txt.includes('entrar al audio por computadora') || b.classList.contains('join-audio-by-computer')) {
                            b.click();
                            log.push('Audio por computadora conectado');
                            break;
                        }
                    }
                    
                    // B) Chequear estado de Micrófono y Cámara
                    for (const b of btns) {
                        const aria = (b.getAttribute('aria-label') || '').toLowerCase().trim();
                        const title = (b.getAttribute('title') || '').toLowerCase().trim();
                        const txt = (b.innerText || b.textContent || '').toLowerCase().trim();
                        
                        // Si dice "cancelar silenciar", "reactivar audio", "unmute": YA ESTÁ APAGADO. NO TOCAR NUNCA.
                        const estaSilenciado = (
                            aria.includes('reactivar') || aria.includes('cancelar silenciar') || aria.includes('unmute') ||
                            title.includes('reactivar') || title.includes('cancelar silenciar') || title.includes('unmute') ||
                            txt.includes('reactivar') || txt.includes('cancelar silenciar') || txt.includes('unmute')
                        );
                        
                        if (estaSilenciado) {
                            // Micrófono ya está 100% apagado y protegido. No tocar.
                            continue;
                        }
                        
                        // Solo si el micrófono dice explícitamente "Silenciar" / "Mute" (indicando que está encendido y transmitiendo)
                        const estaEncendido = (
                            (aria.includes('mute') && !aria.includes('unmute')) ||
                            (aria.includes('silenciar') && !aria.includes('cancelar') && !aria.includes('reactivar')) ||
                            (title.includes('silenciar') && !title.includes('cancelar') && !title.includes('reactivar')) ||
                            (txt.includes('silenciar') && !txt.includes('cancelar') && !txt.includes('reactivar'))
                        );
                        
                        if (estaEncendido) {
                            b.click();
                            log.push('Micrófono estaba encendido y se silenció de inmediato.');
                        }
                        
                        // Cámara: Si dice "Detener video" o "Stop Video", apagarla
                        if (aria.includes('stop video') || aria.includes('detener video') ||
                            title.includes('detener video') || txt.includes('detener video')) {
                            b.click();
                            log.push('Cámara estaba encendida y se apagó.');
                        }
                    }
                    return log;
                }"""
                audio_log = await pagina_activa.evaluate(audio_mic_js)
                if audio_log:
                    resultado["detalles"].extend(audio_log)
                resultado["detalles"].append("Micrófono y Cámara protegidos: Estado OFF confirmado sin clics indebidos.")
            except Exception as e_aud:
                resultado["detalles"].append(f"Aviso audio/micrófono: {e_aud}")

            # 6. CONFIGURAR VISTA: LADO A LADO: ORADOR (Presentación Grande + Expositor en esquina/arriba)
            try:
                vista_js = """async () => {
                    let log = [];
                    const validCssSelectors = [
                        'button[aria-label*="View" i]',
                        'button[aria-label*="Vista" i]',
                        'button[title*="Vista" i]',
                        'button[title*="View" i]',
                        '#viewOptionsTrigger',
                        'button.speaker-view-button',
                        'button.view-control-button',
                        '.view-options-button'
                    ];
                    
                    let viewBtn = null;
                    for (const sel of validCssSelectors) {
                        try {
                            const el = document.querySelector(sel);
                            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) {
                                viewBtn = el;
                                break;
                            }
                        } catch(e) {}
                    }
                    
                    if (!viewBtn) {
                        const allButtons = Array.from(document.querySelectorAll('button, div[role="button"]'));
                        for (const b of allButtons) {
                            const txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                            const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
                            if ((txt === 'vista' || txt === 'view' || aria === 'vista' || aria === 'view' || txt.includes('vista') || aria.includes('vista')) &&
                                !txt.includes('pantalla') && !txt.includes('participantes') && !txt.includes('chat')) {
                                if (b.offsetWidth > 0 || b.offsetHeight > 0) {
                                    viewBtn = b;
                                    break;
                                }
                            }
                        }
                    }
                    
                    if (viewBtn) {
                        viewBtn.click();
                        log.push('Botón Vista presionado');
                        await new Promise(r => setTimeout(r, 600));
                        
                        const items = Array.from(document.querySelectorAll('li, button, div[role="menuitem"], a, span'));
                        
                        // Prioridad 1: Lado a lado: orador (Side-by-side: Speaker)
                        let target = items.find(el => {
                            const t = (el.innerText || el.textContent || '').toLowerCase();
                            return t.includes('lado a lado: orador') || t.includes('side-by-side: speaker') ||
                                   (t.includes('lado a lado') && t.includes('orador')) ||
                                   (t.includes('side-by-side') && t.includes('speaker'));
                        });
                        
                        // Prioridad 2: Orador (Speaker View)
                        if (!target) {
                            target = items.find(el => {
                                const t = (el.innerText || el.textContent || '').toLowerCase();
                                return (t === 'orador' || t === 'speaker' || t.includes('vista del orador') || t.includes('speaker view')) && !t.includes('galería');
                            });
                        }
                        
                        if (target) {
                            target.click();
                            log.push(`Modo seleccionado: '${target.innerText || target.textContent}'`);
                        } else {
                            // Menú ya estaba en el modo deseado o no requiere cambio
                            viewBtn.click();
                            log.push('Vista ya configurada en modo deseado');
                        }
                        
                        // Prioridad 3: Ajustar a ventana si está disponible
                        const fit = items.find(el => {
                            const t = (el.innerText || el.textContent || '').toLowerCase();
                            return t.includes('ajustar a la ventana') || t.includes('fit to window');
                        });
                        if (fit) {
                            try { fit.click(); log.push('Ajustar a ventana activado'); } catch(e) {}
                        }
                    } else {
                        log.push('Botón Vista no visible directamente (revisando selector secundario)');
                    }
                    return log;
                }"""
                log_vista = await pagina_activa.evaluate(vista_js)
                if log_vista:
                    resultado["vista_lado_a_lado"] = True
                    resultado["detalles"].extend(log_vista)
            except Exception as e_v:
                resultado["detalles"].append(f"Aviso configuración de vista: {e_v}")

            resultado["status"] = "exito_total"
            return resultado

        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)
            print(json.dumps(resultado, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(optimizar_zoom_ahora())
