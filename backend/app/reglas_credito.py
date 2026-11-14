"""Reglas de negocio puras de CrediCheck. [JC]

Fuente de verdad: sección 4 del documento de propuesta. Este módulo no conoce FastAPI ni boto3,
por eso se prueba completo en milisegundos.
"""
import math
from dataclasses import asdict, dataclass

SCORE_MIN, SCORE_MAX, SCORE_APROBACION = 300, 850, 600
INGRESOS_MINIMOS = 2000.0
MONTO_MIN, MONTO_MAX = 500.0, 100000.0
MULTIPLICADORES = [(600, 699, 3), (700, 799, 5), (800, 850, 8)]

APROBADO = "APROBADO"
APROBADO_PARCIAL = "APROBADO_PARCIAL"
RECHAZADO = "RECHAZADO"

CUMPLE_REQUISITOS = "CUMPLE_REQUISITOS"
MONTO_AJUSTADO = "MONTO_AJUSTADO"
SCORE_INSUFICIENTE = "SCORE_INSUFICIENTE"
INGRESOS_INSUFICIENTES = "INGRESOS_INSUFICIENTES"


@dataclass(frozen=True)
class ResultadoEvaluacion:
    decision: str
    motivo: str
    monto_maximo: float
    monto_aprobado: float

    def a_dict(self) -> dict:
        return asdict(self)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def validar_entradas(score, ingresos, monto_solicitado) -> None:
    """Valida tipos (TypeError) y dominios (ValueError) antes de tomar cualquier decisión."""
    if not isinstance(score, int) or isinstance(score, bool):
        raise TypeError("El score debe ser un número entero.")
    if not _es_numero(ingresos):
        raise TypeError("Los ingresos deben ser numéricos.")
    if not _es_numero(monto_solicitado):
        raise TypeError("El monto solicitado debe ser numérico.")
    if score < SCORE_MIN or score > SCORE_MAX:
        raise ValueError(f"Score fuera de rango permitido ({SCORE_MIN}-{SCORE_MAX}).")
    if not math.isfinite(ingresos) or ingresos < 0:
        raise ValueError("Los ingresos no pueden ser negativos.")
    if not math.isfinite(monto_solicitado) or not MONTO_MIN <= monto_solicitado <= MONTO_MAX:
        raise ValueError(f"El monto debe estar entre {MONTO_MIN:.0f} y {MONTO_MAX:.0f}.")


def multiplicador_para(score: int) -> int:
    """Multiplicador de ingresos según la banda del score (solo existe para scores aprobables)."""
    for desde, hasta, multiplicador in MULTIPLICADORES:
        if desde <= score <= hasta:
            return multiplicador
    raise ValueError(f"El score {score} no pertenece a ninguna banda de aprobación.")


def calcular_monto_maximo(score: int, ingresos: float) -> float:
    return round(ingresos * multiplicador_para(score), 2)


def evaluar_prestamo(score, ingresos, monto_solicitado) -> ResultadoEvaluacion:
    validar_entradas(score, ingresos, monto_solicitado)

    if score < SCORE_APROBACION:
        return ResultadoEvaluacion(RECHAZADO, SCORE_INSUFICIENTE, 0.0, 0.0)
    if ingresos < INGRESOS_MINIMOS:
        return ResultadoEvaluacion(RECHAZADO, INGRESOS_INSUFICIENTES, 0.0, 0.0)

    monto_maximo = calcular_monto_maximo(score, ingresos)
    if monto_solicitado <= monto_maximo:
        return ResultadoEvaluacion(APROBADO, CUMPLE_REQUISITOS, monto_maximo, round(monto_solicitado, 2))
    return ResultadoEvaluacion(APROBADO_PARCIAL, MONTO_AJUSTADO, monto_maximo, monto_maximo)


def reglas_publicas() -> dict:
    """Umbrales del negocio para GET /api/v1/reglas (el frontend no tiene números quemados)."""
    return {
        "score": {"minimo": SCORE_MIN, "maximo": SCORE_MAX, "aprobacion_minima": SCORE_APROBACION},
        "ingresos_minimos": INGRESOS_MINIMOS,
        "monto": {"minimo": MONTO_MIN, "maximo": MONTO_MAX},
        "multiplicadores": [
            {"desde": desde, "hasta": hasta, "multiplicador": multiplicador}
            for desde, hasta, multiplicador in MULTIPLICADORES
        ],
    }
