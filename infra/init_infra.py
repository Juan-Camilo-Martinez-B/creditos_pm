"""Aprovisionamiento IaC de CrediCheck en LocalStack (o AWS). [SA] (tarea SA-1)

Declarativo e idempotente: describe el estado deseado y solo crea lo que falta.
Se puede ejecutar N veces seguidas y el resultado es siempre el mismo:

    Bucket  credicheck-evaluaciones   versionado + cifrado AES256 + sin acceso público
    Cola    credicheck-eventos-dlq    retiene 14 días los mensajes que fallaron
    Cola    credicheck-eventos        redrive a la DLQ tras 3 recepciones fallidas

Uso:  python infra/init_infra.py   (lo ejecuta el servicio infra-init de docker-compose)
"""
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

BUCKET = os.getenv("BUCKET_EVALUACIONES", "credicheck-evaluaciones")
COLA = os.getenv("COLA_EVENTOS", "credicheck-eventos")
COLA_DLQ = f"{COLA}-dlq"
MAX_RECEPCIONES = 3  # intentos antes de mandar el mensaje a la DLQ
RETENCION_DLQ_S = 14 * 24 * 3600


def crear_clientes():
    parametros = {
        "endpoint_url": os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        "region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    }
    return boto3.client("s3", **parametros), boto3.client("sqs", **parametros)


def esperar_servicio(s3, intentos: int = 10, pausa_s: float = 2.0) -> None:
    """LocalStack puede tardar unos segundos en aceptar peticiones aunque el healthcheck esté OK."""
    for intento in range(1, intentos + 1):
        try:
            s3.list_buckets()
            return
        except (EndpointConnectionError, ClientError) as error:
            print(f" -> Esperando a S3 ({intento}/{intentos}): {type(error).__name__}")
            time.sleep(pausa_s)
    raise RuntimeError("S3 no respondió; ¿LocalStack está en ejecución?")


def asegurar_bucket(s3, nombre: str) -> str:
    """Crea el bucket si no existe y aplica su configuración (aplicarla dos veces no cambia nada)."""
    try:
        s3.head_bucket(Bucket=nombre)
        estado = "YA EXISTE"
    except ClientError as error:
        if error.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
            raise
        s3.create_bucket(Bucket=nombre)
        estado = "CREADO"

    s3.put_bucket_versioning(Bucket=nombre, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_encryption(
        Bucket=nombre,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    s3.put_public_access_block(
        Bucket=nombre,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    return estado


def _url_si_existe(sqs, nombre: str):
    try:
        return sqs.get_queue_url(QueueName=nombre)["QueueUrl"]
    except ClientError as error:
        if "NonExistentQueue" in error.response["Error"]["Code"]:
            return None
        raise


def asegurar_cola(sqs, nombre: str, atributos: dict) -> tuple[str, str]:
    """Crea la cola si no existe; si existe, solo sincroniza sus atributos. Retorna (estado, url)."""
    url = _url_si_existe(sqs, nombre)
    if url is None:
        url = sqs.create_queue(QueueName=nombre, Attributes=atributos)["QueueUrl"]
        return "CREADA", url
    sqs.set_queue_attributes(QueueUrl=url, Attributes=atributos)
    return "YA EXISTE", url


def aprovisionar(s3, sqs) -> dict:
    estado_bucket = asegurar_bucket(s3, BUCKET)
    print(f" -> Bucket {BUCKET}: {estado_bucket} (versionado, AES256, sin acceso público)")

    estado_dlq, url_dlq = asegurar_cola(sqs, COLA_DLQ, {"MessageRetentionPeriod": str(RETENCION_DLQ_S)})
    print(f" -> Cola {COLA_DLQ}: {estado_dlq}")

    arn_dlq = sqs.get_queue_attributes(QueueUrl=url_dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    redrive = json.dumps({"deadLetterTargetArn": arn_dlq, "maxReceiveCount": str(MAX_RECEPCIONES)})
    estado_cola, url_cola = asegurar_cola(sqs, COLA, {"RedrivePolicy": redrive, "VisibilityTimeout": "30"})
    print(f" -> Cola {COLA}: {estado_cola} (DLQ tras {MAX_RECEPCIONES} intentos)")

    return {"bucket": estado_bucket, "dlq": estado_dlq, "cola": estado_cola, "url_cola": url_cola}


def main() -> int:
    print("=== APROVISIONAMIENTO IAC CREDICHECK ===")
    s3, sqs = crear_clientes()
    try:
        esperar_servicio(s3)
        aprovisionar(s3, sqs)
    except Exception as error:  # el contenedor debe terminar con código != 0 para frenar a la API
        print(f" -> [ERROR] {type(error).__name__}: {error}")
        return 1
    print("=== INFRAESTRUCTURA LISTA ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
