"""Modelos Pydantic de petición y respuesta (contrato de la sección 7). [JC]

Los tipos estrictos hacen que un score "700" (texto) se rechace con 422 antes de llegar a la lógica;
los valores fuera de dominio los rechaza reglas_credito.py con 400 (defensa en profundidad).
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

Decision = Literal["APROBADO", "APROBADO_PARCIAL", "RECHAZADO"]
Motivo = Literal["CUMPLE_REQUISITOS", "MONTO_AJUSTADO", "SCORE_INSUFICIENTE", "INGRESOS_INSUFICIENTES"]


class SolicitudEvaluacion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    solicitante: str = Field(min_length=3, max_length=80, examples=["Ana Gómez"])
    score: StrictInt = Field(examples=[700])
    ingresos: StrictInt | StrictFloat = Field(examples=[2000.0])
    monto_solicitado: StrictInt | StrictFloat = Field(examples=[10000.01])


class EvaluacionRespuesta(BaseModel):
    id: str
    solicitante: str
    score: int
    ingresos: float
    monto_solicitado: float
    decision: Decision
    motivo: Motivo
    monto_maximo: float
    monto_aprobado: float
    comprobante: str
    fecha: str
    version_api: str


class SaludRespuesta(BaseModel):
    status: Literal["healthy", "unhealthy"]
    version: str
    entorno: str


class RangoScore(BaseModel):
    minimo: int
    maximo: int
    aprobacion_minima: int


class RangoMonto(BaseModel):
    minimo: float
    maximo: float


class Multiplicador(BaseModel):
    desde: int
    hasta: int
    multiplicador: int


class ReglasRespuesta(BaseModel):
    score: RangoScore
    ingresos_minimos: float
    monto: RangoMonto
    multiplicadores: list[Multiplicador]


class ErrorRespuesta(BaseModel):
    detail: str
