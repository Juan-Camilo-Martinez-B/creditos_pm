"""Adaptador S3/SQS sobre LocalStack o AWS. [SA] (tareas SA-3 y SA-7)

Diseño:
    s3://credicheck-evaluaciones/evaluaciones/<id>.json   comprobante de cada evaluación (fuente de verdad)
    s3://credicheck-evaluaciones/indices/recientes.json   las 100 evaluaciones más recientes (optimización)
    SQS credicheck-eventos                                evento "evaluacion.creada"

Optimización del historial (SA-7, hallazgo de Locust de Rafael):
    Sin índice, listar() hace un list_objects y una lectura por objeto (patrón N+1): el tiempo crece
    con el número de evaluaciones. Con el índice, listar() hace UNA sola lectura.
    LISTADO_S3=escaneo fuerza el modo N+1 para poder medir el "antes" en las pruebas de carga.

Acuerdo con Juan Camilo: lo que se guarda incluye el campo "comprobante" (la misma referencia que retorna).
"""
import json
import os
import threading
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.storage.base import RepositorioEvaluaciones

PREFIJO = "evaluaciones/"
CLAVE_INDICE = "indices/recientes.json"
TAMANO_INDICE = 100  # coincide con el máximo de ?limite= de la API
TIPO_EVENTO = "evaluacion.creada"


class RepositorioS3Sqs(RepositorioEvaluaciones):
    def __init__(self, cliente_s3=None, cliente_sqs=None, bucket: str = None, cola: str = None,
                 usar_indice: bool = None) -> None:
        parametros = {"endpoint_url": settings.AWS_ENDPOINT_URL, "region_name": settings.AWS_REGION}
        self._s3 = cliente_s3 or boto3.client("s3", **parametros)
        self._sqs = cliente_sqs or boto3.client("sqs", **parametros)
        self._bucket = bucket or settings.BUCKET_EVALUACIONES
        self._cola = cola or settings.COLA_EVENTOS
        if usar_indice is None:
            usar_indice = os.getenv("LISTADO_S3", "indice").strip().lower() != "escaneo"
        self._usar_indice = usar_indice
        self._url_cola: Optional[str] = None
        # uvicorn atiende las peticiones en varios hilos: el índice es leer-modificar-escribir.
        self._candado_indice = threading.Lock()

    # ---------- S3 ----------
    @staticmethod
    def _clave(evaluacion_id: str) -> str:
        return f"{PREFIJO}{evaluacion_id}.json"

    def _leer_json(self, clave: str):
        try:
            respuesta = self._s3.get_object(Bucket=self._bucket, Key=clave)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(respuesta["Body"].read())

    def _escribir_json(self, clave: str, contenido) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=clave,
            Body=json.dumps(contenido, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    def guardar(self, evaluacion: dict) -> str:
        referencia = f"s3://{self._bucket}/{self._clave(evaluacion['id'])}"
        documento = {**evaluacion, "comprobante": referencia}
        self._escribir_json(self._clave(evaluacion["id"]), documento)
        if self._usar_indice:
            self._actualizar_indice(documento)
        return referencia

    def obtener(self, evaluacion_id: str) -> Optional[dict]:
        if not evaluacion_id or "/" in evaluacion_id:  # el id nunca debe salir del prefijo evaluaciones/
            return None
        return self._leer_json(self._clave(evaluacion_id))

    def listar(self, limite: int = 20) -> list[dict]:
        if self._usar_indice:
            indice = self._leer_indice()
            if indice is not None:
                return indice[:limite]
        return self._listar_escaneando()[:limite]

    # ---------- índice de recientes ----------
    def _leer_indice(self) -> Optional[list]:
        try:
            indice = self._leer_json(CLAVE_INDICE)
        except ValueError:  # índice corrupto: se reconstruye desde los comprobantes
            indice = None
        return indice if isinstance(indice, list) else None

    def _actualizar_indice(self, documento: dict) -> None:
        with self._candado_indice:
            indice = self._leer_indice()
            if indice is None:
                indice = self._listar_escaneando()  # primera vez o índice dañado
            sin_repetidos = [e for e in indice if e.get("id") != documento["id"]]
            ordenado = sorted([documento, *sin_repetidos], key=lambda e: e["fecha"], reverse=True)
            self._escribir_json(CLAVE_INDICE, ordenado[:TAMANO_INDICE])

    def _listar_escaneando(self) -> list[dict]:
        """Modo N+1: una lectura por cada comprobante. Se conserva como respaldo y para medir el 'antes'."""
        evaluaciones = []
        paginador = self._s3.get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=self._bucket, Prefix=PREFIJO):
            for objeto in pagina.get("Contents", []):
                evaluacion = self._leer_json(objeto["Key"])
                if evaluacion is not None:
                    evaluaciones.append(evaluacion)
        return sorted(evaluaciones, key=lambda e: e["fecha"], reverse=True)

    # ---------- SQS ----------
    def _obtener_url_cola(self) -> str:
        if self._url_cola is None:
            self._url_cola = self._sqs.get_queue_url(QueueName=self._cola)["QueueUrl"]
        return self._url_cola

    def publicar_evento(self, evaluacion: dict) -> None:
        self._sqs.send_message(
            QueueUrl=self._obtener_url_cola(),
            MessageBody=json.dumps({"tipo": TIPO_EVENTO, "evaluacion": evaluacion}, ensure_ascii=False),
            MessageAttributes={"tipo": {"DataType": "String", "StringValue": TIPO_EVENTO}},
        )
