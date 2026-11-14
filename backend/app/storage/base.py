"""Contrato entre el adaptador en memoria (Juan Camilo) y el de S3/SQS (Saray).

[BASE] — NO modificar sin acuerdo de los tres integrantes.
"""
from abc import ABC, abstractmethod
from typing import Optional


class RepositorioEvaluaciones(ABC):
    @abstractmethod
    def guardar(self, evaluacion: dict) -> str:
        """Persiste la evaluación y retorna la referencia del comprobante."""

    @abstractmethod
    def obtener(self, evaluacion_id: str) -> Optional[dict]:
        """Retorna la evaluación o None si no existe."""

    @abstractmethod
    def listar(self, limite: int = 20) -> list[dict]:
        """Retorna las evaluaciones más recientes primero (orden por 'fecha' desc)."""

    @abstractmethod
    def publicar_evento(self, evaluacion: dict) -> None:
        """Publica el evento 'evaluacion.creada'. En memoria solo lo registra."""
