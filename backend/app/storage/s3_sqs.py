"""Adaptador S3/SQS sobre LocalStack o AWS. [SA] — Esqueleto de la Fase 0: implementar en SA-3."""
from typing import Optional

from app.storage.base import RepositorioEvaluaciones


class RepositorioS3Sqs(RepositorioEvaluaciones):
    def guardar(self, evaluacion: dict) -> str:
        raise NotImplementedError("Pendiente SA-3")

    def obtener(self, evaluacion_id: str) -> Optional[dict]:
        raise NotImplementedError("Pendiente SA-3")

    def listar(self, limite: int = 20) -> list[dict]:
        raise NotImplementedError("Pendiente SA-3")

    def publicar_evento(self, evaluacion: dict) -> None:
        raise NotImplementedError("Pendiente SA-3")
