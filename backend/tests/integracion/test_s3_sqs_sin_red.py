"""Pruebas del adaptador S3/SQS con dobles de prueba (sin LocalStack ni red). [SA] (SA-4)

Complementan a test_storage_s3.py: validan la lógica del adaptador (índice, respaldo N+1, eventos)
y cuentan las lecturas a S3 para demostrar la optimización del historial (SA-7).
"""
import io
import json

import pytest
from botocore.exceptions import ClientError

from app.storage.base import RepositorioEvaluaciones
from app.storage.s3_sqs import CLAVE_INDICE, TAMANO_INDICE, RepositorioS3Sqs


class S3Falso:
    def __init__(self):
        self.objetos: dict[str, bytes] = {}
        self.lecturas = 0

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objetos[Key] = Body

    def get_object(self, Bucket, Key):
        self.lecturas += 1
        if Key not in self.objetos:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "no"}}, "GetObject")
        return {"Body": io.BytesIO(self.objetos[Key])}

    def get_paginator(self, nombre):
        objetos = self.objetos

        class Paginador:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k} for k in sorted(objetos) if k.startswith(Prefix)]}

        return Paginador()


class SqsFalso:
    def __init__(self):
        self.mensajes = []
        self.consultas_url = 0

    def get_queue_url(self, QueueName):
        self.consultas_url += 1
        return {"QueueUrl": f"http://sqs/{QueueName}"}

    def send_message(self, **kwargs):
        self.mensajes.append(kwargs)


def _evaluacion(n: int) -> dict:
    return {"id": f"id-{n}", "fecha": f"2026-11-18T10:00:{n:02d}.000000Z", "decision": "APROBADO"}


@pytest.fixture
def s3():
    return S3Falso()


@pytest.fixture
def sqs():
    return SqsFalso()


@pytest.fixture
def repositorio(s3, sqs):
    return RepositorioS3Sqs(s3, sqs, bucket="b", cola="c", usar_indice=True)


def test_cumple_el_contrato_base(repositorio):
    assert isinstance(repositorio, RepositorioEvaluaciones)


def test_guardar_incluye_el_comprobante_en_lo_persistido(repositorio, s3):
    referencia = repositorio.guardar(_evaluacion(1))

    assert referencia == "s3://b/evaluaciones/id-1.json"
    assert json.loads(s3.objetos["evaluaciones/id-1.json"])["comprobante"] == referencia


def test_obtener_inexistente_retorna_none(repositorio):
    assert repositorio.obtener("no-existe") is None


def test_obtener_rechaza_ids_con_barra(repositorio, s3):
    repositorio.guardar(_evaluacion(1))
    s3.lecturas = 0
    assert repositorio.obtener("../indices/recientes") is None
    assert s3.lecturas == 0  # ni siquiera se consulta S3


def test_otros_errores_de_s3_se_propagan(repositorio, s3):
    def falla(**_):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "GetObject")

    s3.get_object = falla
    with pytest.raises(ClientError):
        repositorio.obtener("id-1")


def test_listar_con_indice_hace_una_sola_lectura(repositorio, s3):
    for n in range(30):
        repositorio.guardar(_evaluacion(n))
    s3.lecturas = 0

    listado = repositorio.listar(limite=5)

    assert [e["id"] for e in listado] == ["id-29", "id-28", "id-27", "id-26", "id-25"]
    assert s3.lecturas == 1


def test_listar_por_escaneo_hace_n_mas_1_lecturas(s3, sqs):
    repositorio = RepositorioS3Sqs(s3, sqs, bucket="b", cola="c", usar_indice=False)
    for n in range(30):
        repositorio.guardar(_evaluacion(n))
    s3.lecturas = 0

    listado = repositorio.listar(limite=5)

    assert [e["id"] for e in listado][0] == "id-29"
    assert s3.lecturas == 30
    assert CLAVE_INDICE not in s3.objetos  # sin índice no se escribe el índice


def test_indice_se_limita_a_los_mas_recientes(repositorio, s3):
    for n in range(TAMANO_INDICE + 5):
        repositorio.guardar({"id": f"id-{n}", "fecha": f"2026-11-18T10:{n // 60:02d}:{n % 60:02d}Z"})

    indice = json.loads(s3.objetos[CLAVE_INDICE])
    assert len(indice) == TAMANO_INDICE
    assert indice[0]["id"] == f"id-{TAMANO_INDICE + 4}"


def test_guardar_dos_veces_el_mismo_id_no_duplica_en_el_indice(repositorio):
    repositorio.guardar(_evaluacion(1))
    repositorio.guardar(_evaluacion(1))

    assert [e["id"] for e in repositorio.listar()] == ["id-1"]


def test_indice_corrupto_usa_el_escaneo_como_respaldo(repositorio, s3):
    repositorio.guardar(_evaluacion(1))
    s3.objetos[CLAVE_INDICE] = b"{roto"

    assert [e["id"] for e in repositorio.listar()] == ["id-1"]


def test_variable_listado_s3_escaneo_desactiva_el_indice(monkeypatch, s3, sqs):
    monkeypatch.setenv("LISTADO_S3", "escaneo")
    assert RepositorioS3Sqs(s3, sqs)._usar_indice is False
    monkeypatch.delenv("LISTADO_S3")
    assert RepositorioS3Sqs(s3, sqs)._usar_indice is True


def test_publicar_evento_envia_el_tipo_y_la_evaluacion(repositorio, sqs):
    repositorio.publicar_evento(_evaluacion(1))
    repositorio.publicar_evento(_evaluacion(2))

    assert sqs.consultas_url == 1  # la URL de la cola se cachea
    primero = sqs.mensajes[0]
    assert primero["QueueUrl"] == "http://sqs/c"
    assert json.loads(primero["MessageBody"]) == {"tipo": "evaluacion.creada", "evaluacion": _evaluacion(1)}
    assert primero["MessageAttributes"]["tipo"]["StringValue"] == "evaluacion.creada"
