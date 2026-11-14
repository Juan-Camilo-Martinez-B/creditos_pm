"""Pruebas de los endpoints con TestClient y el repositorio en memoria. [JC]"""
import re

import pytest

from app.config import settings
from app.reglas_credito import reglas_publicas
from app.storage import get_storage
from app.storage.memoria import RepositorioMemoria
from app.storage.s3_sqs import RepositorioS3Sqs

CAMPOS_EVALUACION = {
    "id", "solicitante", "score", "ingresos", "monto_solicitado", "decision", "motivo",
    "monto_maximo", "monto_aprobado", "comprobante", "fecha", "version_api",
}


def crear(client, **cambios):
    cuerpo = {"solicitante": "Ana Gómez", "score": 700, "ingresos": 2500.0, "monto_solicitado": 1000.0}
    cuerpo.update(cambios)
    return client.post("/api/v1/evaluaciones", json=cuerpo)


# ---------------------------------------------------------------- /health
def test_health_responde_sano_con_version_y_entorno(client):
    # Arrange: configuración por defecto
    # Act
    respuesta = client.get("/health")
    # Assert
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "healthy", "version": settings.APP_VERSION, "entorno": settings.APP_ENV}


def test_health_simula_fallo_con_variable_de_entorno(client, monkeypatch):
    # Arrange
    monkeypatch.setenv("FORZAR_FALLO_SALUD", "true")
    # Act
    respuesta = client.get("/health")
    # Assert
    assert respuesta.status_code == 500
    assert respuesta.json()["status"] == "unhealthy"


# ---------------------------------------------------------------- /api/v1/reglas
def test_reglas_coinciden_con_las_constantes_del_negocio(client):
    respuesta = client.get("/api/v1/reglas")

    assert respuesta.status_code == 200
    assert respuesta.json() == reglas_publicas()


# ---------------------------------------------------------------- POST /api/v1/evaluaciones
def test_crear_evaluacion_retorna_201_con_el_contrato_completo(client, solicitud_valida):
    respuesta = client.post("/api/v1/evaluaciones", json=solicitud_valida)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == CAMPOS_EVALUACION
    assert cuerpo["decision"] == "APROBADO_PARCIAL"
    assert cuerpo["motivo"] == "MONTO_AJUSTADO"
    assert cuerpo["monto_maximo"] == 10000.0
    assert cuerpo["monto_aprobado"] == 10000.0
    assert re.fullmatch(r"[0-9a-f-]{36}", cuerpo["id"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", cuerpo["fecha"])
    assert cuerpo["comprobante"] == f"memoria://evaluaciones/{cuerpo['id']}.json"
    assert cuerpo["version_api"] == settings.APP_VERSION


@pytest.mark.parametrize(
    "score, ingresos, monto, decision",
    [(599, 2500.0, 1000.0, "RECHAZADO"), (600, 2500.0, 1000.0, "APROBADO"), (700, 1999.99, 1000.0, "RECHAZADO")],
)
def test_crear_evaluacion_respeta_las_fronteras(client, score, ingresos, monto, decision):
    respuesta = crear(client, score=score, ingresos=ingresos, monto_solicitado=monto)

    assert respuesta.status_code == 201
    assert respuesta.json()["decision"] == decision


def test_crear_evaluacion_acepta_enteros_y_los_devuelve_como_decimales(client):
    respuesta = crear(client, ingresos=2000, monto_solicitado=1000)

    assert respuesta.status_code == 201
    assert respuesta.json()["ingresos"] == 2000.0


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"score": 851}, "Score fuera de rango"),
        ({"score": 299}, "Score fuera de rango"),
        ({"ingresos": -0.01}, "ingresos no pueden ser negativos"),
        ({"monto_solicitado": 499.99}, "monto debe estar entre"),
        ({"monto_solicitado": 100000.01}, "monto debe estar entre"),
    ],
)
def test_valor_fuera_de_dominio_retorna_400(client, cambios, mensaje):
    respuesta = crear(client, **cambios)

    assert respuesta.status_code == 400
    assert mensaje in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "cambios",
    [
        {"score": "700"},
        {"score": 700.5},
        {"score": True},
        {"ingresos": "2500"},
        {"monto_solicitado": None},
        {"solicitante": "Al"},
        {"solicitante": "x" * 81},
        {"campo_extra": 1},
    ],
)
def test_tipo_invalido_retorna_422(client, cambios):
    respuesta = crear(client, **cambios)

    assert respuesta.status_code == 422


def test_campo_faltante_retorna_422(client):
    respuesta = client.post("/api/v1/evaluaciones", json={"solicitante": "Ana Gómez", "score": 700})

    assert respuesta.status_code == 422


def test_crear_evaluacion_guarda_y_publica_un_evento(client, repositorio):
    respuesta = crear(client)

    evaluacion = respuesta.json()
    assert repositorio.obtener(evaluacion["id"]) == evaluacion
    assert repositorio.eventos_publicados == [{"tipo": "evaluacion.creada", "evaluacion": evaluacion}]


def test_evaluacion_rechazada_por_dominio_no_se_guarda(client, repositorio):
    crear(client, score=851)

    assert repositorio.listar() == []
    assert repositorio.eventos_publicados == []


# ---------------------------------------------------------------- GET /api/v1/evaluaciones/{id}
def test_consultar_evaluacion_existente(client):
    creada = crear(client).json()

    respuesta = client.get(f"/api/v1/evaluaciones/{creada['id']}")

    assert respuesta.status_code == 200
    assert respuesta.json() == creada


def test_consultar_evaluacion_inexistente_retorna_404(client):
    respuesta = client.get("/api/v1/evaluaciones/00000000-0000-0000-0000-000000000000")

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Evaluación no encontrada"}


# ---------------------------------------------------------------- GET /api/v1/evaluaciones
def test_historial_vacio(client):
    respuesta = client.get("/api/v1/evaluaciones")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_historial_respeta_el_limite_y_el_orden_descendente(client):
    ids = [crear(client, solicitante=f"Cliente {n}").json()["id"] for n in range(3)]

    respuesta = client.get("/api/v1/evaluaciones", params={"limite": 2})

    assert respuesta.status_code == 200
    assert [e["id"] for e in respuesta.json()] == [ids[2], ids[1]]


@pytest.mark.parametrize("limite", [0, 101, "abc"])
def test_historial_con_limite_invalido_retorna_422(client, limite):
    respuesta = client.get("/api/v1/evaluaciones", params={"limite": limite})

    assert respuesta.status_code == 422


# ---------------------------------------------------------------- fábrica de almacenamiento
def test_fabrica_usa_memoria_por_defecto(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "memoria")
    get_storage.cache_clear()
    try:
        assert isinstance(get_storage(), RepositorioMemoria)
    finally:
        get_storage.cache_clear()


def test_fabrica_usa_s3_cuando_se_configura(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    get_storage.cache_clear()
    try:
        assert isinstance(get_storage(), RepositorioS3Sqs)
    finally:
        get_storage.cache_clear()
