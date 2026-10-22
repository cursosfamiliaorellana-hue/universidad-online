# -*- coding: utf-8 -*-
"""
sentinela_daemon.py - Wrapper de compatibilidad retroactiva.
Redirige la ejecución hacia el módulo oficial: sentinela_auditor.py (Centinela Auditor 24 Horas).
"""
import sentinela_auditor

if __name__ == "__main__":
    sentinela_auditor.iniciar_servidor()
