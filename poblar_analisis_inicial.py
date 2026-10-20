"""
poblar_analisis_inicial.py - Analiza las clases existentes en clases.db con Gemini
y genera el tablero interactivo 'Mis_Rutas_80_20_UniversidadOnline.html'.
"""

import json
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import ai_analyzer
import database
import route_builder

def main():
    database.init_db()
    clases = database.listar_clases()
    print(f"Total de clases registradas: {len(clases)}")

    sin_analizar = [c for c in clases if not c.get("transversal") or not c.get("analisis_json")]
    print(f"Clases pendientes de análisis didáctico: {len(sin_analizar)}")

    for i, c in enumerate(sin_analizar, 1):
        id_clase = c["id_clase"]
        titulo = c["titulo_original"]
        print(f"\n[{i}/{len(sin_analizar)}] Analizando: '{titulo}'...")

        try:
            analisis = ai_analyzer.analizar_clase_con_gemini(titulo)
            if analisis:
                database.guardar_analisis_clase(id_clase, analisis)
                print(f"   -> Clasificada en: {analisis.get('transversal')} | Nivel {analisis.get('nivel')}")
                vc = analisis.get("vertical_creacion", {})
                vcom = analisis.get("vertical_comercializacion", {})
                print(f"   -> Creación: {vc.get('porcentaje_importancia')}% (Vital: {vc.get('es_pareto_20_vital')}) | Comercialización: {vcom.get('porcentaje_importancia')}% (Vital: {vcom.get('es_pareto_20_vital')})")
            else:
                print(f"   [!] No se pudo obtener análisis para '{titulo}'")
        except Exception as e:
            print(f"   [!] Excepción analizando '{titulo}': {e}")

        # Pequeña pausa de cortesía para la API gratuita
        time.sleep(2)

    # Generar el tablero HTML actualizado
    print("\n" + "=" * 80)
    print("Generando Tablero Interactivo Mis_Rutas_80_20_UniversidadOnline.html...")
    ruta_html = route_builder.generar_tablero_rutas()
    print(f"✅ ¡Tablero generado con éxito en: {ruta_html}")
    print("=" * 80)

if __name__ == "__main__":
    main()
