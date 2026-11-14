"""Adaptador en memoria de RepositorioEvaluaciones. [JC]

Se usa en las pruebas unitarias y en desarrollo local (STORAGE_BACKEND=memoria).
Guarda la evaluación ya con su campo "comprobante", igual que debe hacerlo el adaptador S3/SQS.
"""
from typing import Optional

from app.storage.base import RepositorioEvaluaciones


class RepositorioMemoria(RepositorioEvaluaciones):
    def __init__(self) -> None:
        self._evaluaciones: dict[str, dict] = {}
        self._orden_llegada: list[str] = []
        self.eventos_publicados: list[dict] = []

    def guardar(self, evaluacion: dict) -> str:
        evaluacion_id = evaluacion["id"]
        referencia = f"memoria://evaluaciones/{evaluacion_id}.json"
        if evaluacion_id not in self._evaluaciones:
            self._orden_llegada.append(evaluacion_id)
        self._evaluaciones[evaluacion_id] = {**evaluacion, "comprobante": referencia}
        return referencia

    def obtener(self, evaluacion_id: str) -> Optional[dict]:
        evaluacion = self._evaluaciones.get(evaluacion_id)
        return dict(evaluacion) if evaluacion is not None else None

    def listar(self, limite: int = 20) -> list[dict]:
        # Más recientes primero; ante fechas iguales gana la que llegó después (orden estable).
        recientes_primero = [self._evaluaciones[i] for i in reversed(self._orden_llegada)]
        ordenadas = sorted(recientes_primero, key=lambda e: e["fecha"], reverse=True)
        return [dict(e) for e in ordenadas[:limite]]

    def publicar_evento(self, evaluacion: dict) -> None:
        self.eventos_publicados.append({"tipo": "evaluacion.creada", "evaluacion": dict(evaluacion)})
