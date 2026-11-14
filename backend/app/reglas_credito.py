"""Reglas de negocio puras de CrediCheck. [JC] — Esqueleto de la Fase 0: implementar en JC-1.

Fuente de verdad: sección 4 del documento de propuesta.
"""
SCORE_MIN, SCORE_MAX, SCORE_APROBACION = 300, 850, 600
INGRESOS_MINIMOS = 2000.0
MONTO_MIN, MONTO_MAX = 500.0, 100000.0
MULTIPLICADORES = [(600, 699, 3), (700, 799, 5), (800, 850, 8)]
