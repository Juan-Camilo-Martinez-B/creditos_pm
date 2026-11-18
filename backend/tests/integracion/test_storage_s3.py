"""Pruebas de integración contra LocalStack. [SA] (tarea SA-4)

Requieren LocalStack en ejecución:
    docker compose up -d --wait localstack
    cd backend && python -m pytest -m integracion --no-cov

Cada sesión crea un bucket y una cola TEMPORALES (sufijo aleatorio) y los borra al final:
las pruebas no dependen de datos previos ni ensucian credicheck-evaluaciones.
"""
import importlib.util
import json
import os
import uuid
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage
from app.storage.s3_sqs import CLAVE_INDICE, RepositorioS3Sqs

pytestmark = pytest.mark.integracion

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
RAIZ_REPO = Path(__file__).resolve().parents[3]


def _evaluacion(fecha: str, **cambios) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "solicitante": "Prueba Integración",
        "score": 700,
        "ingresos": 2000.0,
        "monto_solicitado": 10000.01,
        "decision": "APROBADO_PARCIAL",
        "motivo": "MONTO_SUPERA_CAPACIDAD",
        "monto_aprobado": 10000.0,
        "fecha": fecha,
        "version_api": "1.0.0",
    }
    return {**base, **cambios}


@pytest.fixture(scope="session")
def clientes():
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    s3 = boto3.client("s3", endpoint_url=ENDPOINT, region_name=REGION)
    sqs = boto3.client("sqs", endpoint_url=ENDPOINT, region_name=REGION)
    return s3, sqs


@pytest.fixture(scope="session")
def recursos_temporales(clientes):
    s3, sqs = clientes
    sufijo = uuid.uuid4().hex[:8]
    bucket, cola = f"credicheck-test-{sufijo}", f"credicheck-eventos-test-{sufijo}"
    s3.create_bucket(Bucket=bucket)
    url_cola = sqs.create_queue(QueueName=cola)["QueueUrl"]
    yield {"bucket": bucket, "cola": cola, "url_cola": url_cola}
    for objeto in s3.list_objects_v2(Bucket=bucket).get("Contents", []):
        s3.delete_object(Bucket=bucket, Key=objeto["Key"])
    s3.delete_bucket(Bucket=bucket)
    sqs.delete_queue(QueueUrl=url_cola)


@pytest.fixture
def repositorio(clientes, recursos_temporales):
    """Repositorio limpio por prueba: se vacían el bucket y la cola temporales."""
    s3, sqs = clientes
    for objeto in s3.list_objects_v2(Bucket=recursos_temporales["bucket"]).get("Contents", []):
        s3.delete_object(Bucket=recursos_temporales["bucket"], Key=objeto["Key"])
    sqs.purge_queue(QueueUrl=recursos_temporales["url_cola"])
    return RepositorioS3Sqs(s3, sqs, bucket=recursos_temporales["bucket"], cola=recursos_temporales["cola"])


# ---------- S3 ----------
def test_guardar_crea_el_comprobante_en_s3_con_su_referencia(repositorio, clientes, recursos_temporales):
    s3, _ = clientes
    evaluacion = _evaluacion("2026-11-18T10:00:00.000000Z")

    referencia = repositorio.guardar(evaluacion)

    clave = f"evaluaciones/{evaluacion['id']}.json"
    assert referencia == f"s3://{recursos_temporales['bucket']}/{clave}"
    objeto = s3.get_object(Bucket=recursos_temporales["bucket"], Key=clave)
    assert objeto["ContentType"] == "application/json"
    assert json.loads(objeto["Body"].read()) == {**evaluacion, "comprobante": referencia}


def test_obtener_retorna_lo_guardado_incluyendo_el_comprobante(repositorio):
    evaluacion = _evaluacion("2026-11-18T10:00:00.000000Z")
    referencia = repositorio.guardar(evaluacion)

    assert repositorio.obtener(evaluacion["id"]) == {**evaluacion, "comprobante": referencia}


@pytest.mark.parametrize("evaluacion_id", ["no-existe", "../indices/recientes", ""])
def test_obtener_inexistente_o_invalido_retorna_none(repositorio, evaluacion_id):
    assert repositorio.obtener(evaluacion_id) is None


@pytest.mark.parametrize("usar_indice", [True, False], ids=["con-indice", "escaneo-n+1"])
def test_listar_ordena_por_fecha_desc_y_respeta_el_limite(repositorio, usar_indice):
    repositorio._usar_indice = usar_indice
    fechas = ["2026-11-18T10:00:01.000000Z", "2026-11-18T10:00:03.000000Z", "2026-11-18T10:00:02.000000Z"]
    for fecha in fechas:
        repositorio.guardar(_evaluacion(fecha))

    listado = repositorio.listar(limite=2)

    assert [e["fecha"] for e in listado] == ["2026-11-18T10:00:03.000000Z", "2026-11-18T10:00:02.000000Z"]


def test_listar_con_bucket_vacio_retorna_lista_vacia(repositorio):
    assert repositorio.listar() == []


def test_indice_corrupto_se_ignora_y_se_reconstruye(repositorio, clientes, recursos_temporales):
    s3, _ = clientes
    vieja = _evaluacion("2026-11-18T09:00:00.000000Z")
    repositorio.guardar(vieja)
    s3.put_object(Bucket=recursos_temporales["bucket"], Key=CLAVE_INDICE, Body=b"{no es json")

    assert [e["id"] for e in repositorio.listar()] == [vieja["id"]]  # respaldo: escaneo

    nueva = _evaluacion("2026-11-18T11:00:00.000000Z")
    repositorio.guardar(nueva)  # reconstruye el índice
    indice = json.loads(s3.get_object(Bucket=recursos_temporales["bucket"], Key=CLAVE_INDICE)["Body"].read())
    assert [e["id"] for e in indice] == [nueva["id"], vieja["id"]]


# ---------- SQS ----------
def test_publicar_evento_deja_el_mensaje_en_la_cola(repositorio, clientes, recursos_temporales):
    _, sqs = clientes
    evaluacion = _evaluacion("2026-11-18T10:00:00.000000Z", comprobante="s3://x/y.json")

    repositorio.publicar_evento(evaluacion)

    mensajes = sqs.receive_message(
        QueueUrl=recursos_temporales["url_cola"], MaxNumberOfMessages=1, WaitTimeSeconds=2,
        MessageAttributeNames=["All"],
    ).get("Messages", [])
    assert len(mensajes) == 1
    assert json.loads(mensajes[0]["Body"]) == {"tipo": "evaluacion.creada", "evaluacion": evaluacion}
    assert mensajes[0]["MessageAttributes"]["tipo"]["StringValue"] == "evaluacion.creada"


# ---------- Extremo a extremo: API + S3 + SQS ----------
def test_api_post_y_get_persisten_en_s3_y_publican_en_sqs(repositorio, clientes, recursos_temporales):
    _, sqs = clientes
    app.dependency_overrides[get_storage] = lambda: repositorio
    try:
        with TestClient(app) as cliente:
            creada = cliente.post("/api/v1/evaluaciones", json={
                "solicitante": "Ana Gómez", "score": 700, "ingresos": 2000.0, "monto_solicitado": 10000.01,
            })
            consultada = cliente.get(f"/api/v1/evaluaciones/{creada.json()['id']}")
            historial = cliente.get("/api/v1/evaluaciones?limite=5")
    finally:
        app.dependency_overrides.clear()

    assert creada.status_code == 201
    assert creada.json()["comprobante"].startswith(f"s3://{recursos_temporales['bucket']}/evaluaciones/")
    assert consultada.status_code == 200 and consultada.json() == creada.json()
    assert [e["id"] for e in historial.json()] == [creada.json()["id"]]
    mensajes = sqs.receive_message(QueueUrl=recursos_temporales["url_cola"], WaitTimeSeconds=2).get("Messages", [])
    assert json.loads(mensajes[0]["Body"])["evaluacion"]["id"] == creada.json()["id"]


# ---------- IaC (SA-1) ----------
def _cargar_init_infra():
    spec = importlib.util.spec_from_file_location("init_infra", RAIZ_REPO / "infra" / "init_infra.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_iac_es_idempotente(clientes):
    """Ejecutar el aprovisionamiento dos veces seguidas no falla ni duplica recursos."""
    s3, sqs = clientes
    init_infra = _cargar_init_infra()

    init_infra.aprovisionar(s3, sqs)
    segunda = init_infra.aprovisionar(s3, sqs)

    assert segunda["bucket"] == "YA EXISTE"
    assert segunda["dlq"] == "YA EXISTE"
    assert segunda["cola"] == "YA EXISTE"
    assert s3.get_bucket_versioning(Bucket=init_infra.BUCKET)["Status"] == "Enabled"
    atributos = sqs.get_queue_attributes(QueueUrl=segunda["url_cola"], AttributeNames=["RedrivePolicy"])
    redrive = json.loads(atributos["Attributes"]["RedrivePolicy"])
    assert redrive["deadLetterTargetArn"].endswith(init_infra.COLA_DLQ)
    assert int(redrive["maxReceiveCount"]) == init_infra.MAX_RECEPCIONES
