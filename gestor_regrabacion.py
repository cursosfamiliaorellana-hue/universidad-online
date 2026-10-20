"""
gestor_regrabacion.py - Gestor de Re-grabación y Repeticiones de Masterclasses
Aplica la política de Seguridad de Datos (Safe Overwrite / Reemplazo Diferido):
NO borra archivos multimedia ni análisis previo de la BD, y mantiene la clase
visible en la App Web hasta que la nueva grabación termine con éxito.
"""

import os
import sys
import sqlite3
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database
import route_builder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "clases.db")
DIR_GRABACIONES = os.path.join(BASE_DIR, "grabaciones")


def programar_regrabacion_segura(id_clase: str, titulo: str):
    """
    Programa la re-grabación de una clase aplicando Safe Overwrite:
    - Estado pasa a 'PENDIENTE' con regrabacion_activa = 1.
    - NO borra videos físicos locales ni transcripciones.
    - NO borra registros ni enlaces de Telegram ni NotebookLM.
    - Mantiene la clase 100% visible en la App Web hasta que la nueva grabación finalice.
    """
    database.marcar_regrabacion_segura(id_clase)
    print(f"  🛡️ [Safe Overwrite] Re-grabación diferida programada para: '{titulo}' (ID: {id_clase}).")
    print(f"     Los videos, enlaces y fichas actuales se conservan intactos en la App Web.")
    print(f"     El reemplazo se ejecutará automáticamente solo cuando la nueva grabación termine con éxito.")


def listar_todas_las_clases():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM clases_grabadas ORDER BY rowid ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def mostrar_menu():
    while True:
        clases = listar_todas_las_clases()
        print("\n" + "=" * 80)
        print("   GESTOR DE RE-GRABACIÓN Y REINTENTOS SEGUROS DE MASTERCLASSES")
        print("   Universidad Online - Sistema Automatizado (Safe Overwrite)")
        print("=" * 80)
        print(f"Total de clases en el sistema: {len(clases)}\n")

        for idx, c in enumerate(clases, 1):
            es_regrab = c.get("regrabacion_activa") == 1
            if es_regrab:
                estado_marcado = "🔄 RE-GRABACIÓN PENDIENTE (Safe Overwrite)"
            elif c["estado"] == "COMPLETADA":
                estado_marcado = "🟢 COMPLETADA"
            elif c["estado"] == "GRABANDO":
                estado_marcado = "🔴 GRABANDO"
            else:
                estado_marcado = f"⏳ {c['estado']}"
            print(f"[{idx:2d}] {c['titulo_original']}")
            print(f"     Estado: {estado_marcado} | Transversal: {c.get('transversal', 'Sin clasificar')}")

        print("\n" + "-" * 80)
        print("Opciones disponibles:")
        print("  [Número] -> Programar re-grabación segura para esa clase")
        print("  [B]      -> Buscar clase por palabra clave para re-grabar")
        print("  [T]      -> Programar re-grabación segura para TODAS las clases")
        print("  [S]      -> Salir")
        print("-" * 80)

        opcion = input("\n👉 Elige una opción: ").strip().lower()

        if opcion == 's':
            print("Saliendo del gestor...")
            break
            
        elif opcion == 't':
            print("\n🛡️ ATENCIÓN: Esto programará la re-grabación segura de TODAS las clases.")
            print("   Tus grabaciones y fichas actuales NO se borrarán: seguirán en la App Web")
            print("   hasta que el bot complete cada nueva grabación.")
            conf = input("Escribe 'CONFIRMAR' para proceder:\n> ").strip()
            if conf == "CONFIRMAR":
                print("\n⏳ Programando re-grabaciones seguras...")
                for c in clases:
                    programar_regrabacion_segura(c["id_clase"], c["titulo_original"])
                print("\n🌐 Sincronizando estado con la App Web en GitHub Pages...")
                route_builder.generar_tablero_rutas(auto_deploy=True)
                print("\n✅ ¡TODAS LAS CLASES PROGRAMADAS PARA RE-GRABACIÓN SEGURA!")
            else:
                print("Operación cancelada.")
                
        elif opcion == 'b':
            palabra = input("\nEscribe una palabra clave a buscar:\n> ").strip().lower()
            encontradas = [c for c in clases if palabra in c['titulo_original'].lower() or palabra in c['id_clase'].lower()]
            if encontradas:
                print(f"\nSe encontraron {len(encontradas)} clases:")
                for c in encontradas:
                    print(f" - {c['titulo_original']} (Estado: {c['estado']})")
                
                react_op = input("\nEscribe el ID (o fragmento) de la clase a re-grabar (o Enter para cancelar):\n> ").strip().lower()
                if react_op:
                    for c in encontradas:
                        if react_op in c['id_clase'].lower() or react_op in c['titulo_original'].lower():
                            programar_regrabacion_segura(c["id_clase"], c["titulo_original"])
                            print("🌐 Sincronizando con App Web...")
                            route_builder.generar_tablero_rutas(auto_deploy=True)
                            print(f"✅ Clase '{c['titulo_original']}' marcada para re-grabación segura.")
                            break
            else:
                print("\n[!] No se encontraron clases con esa palabra clave.")
                
        elif opcion.isdigit():
            idx = int(opcion)
            if 1 <= idx <= len(clases):
                c = clases[idx - 1]
                programar_regrabacion_segura(c["id_clase"], c["titulo_original"])
                print("🌐 Sincronizando con App Web...")
                route_builder.generar_tablero_rutas(auto_deploy=True)
                print(f"✅ Clase '{c['titulo_original']}' marcada para re-grabación segura.")
            else:
                print("\n[!] Número fuera de rango.")


if __name__ == "__main__":
    database.init_db()
    mostrar_menu()
