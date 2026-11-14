"""Adaptador en memoria. [JC] — Esqueleto de la Fase 0: implementar en JC-5."""
from typing import Optional

from app.storage.base import RepositorioEvaluaciones


class RepositorioMemoria(RepositorioEvaluaciones):
    def __init__(self) -> None:
        self._evaluaciones: dict[str, dict] = {}
        self.eventos_publicados: list[dict] = []

    def guardar(self, evaluacion: dict) -> str:  # pragma: no cover - pendiente JC-5
        raise NotImplementedError("Pendiente JC-5")

    def obtener(self, evaluacion_id: str) -> Optional[dict]:  # pragma: no cover - pendiente JC-5
        raise NotImplementedError("Pendiente JC-5")

    def listar(self, limite: int = 20) -> list[dict]:  # pragma: no cover - pendiente JC-5
        raise NotImplementedError("Pendiente JC-5")

    def publicar_evento(self, evaluacion: dict) -> None:  # pragma: no cover - pendiente JC-5
        raise NotImplementedError("Pendiente JC-5")
