"""Pruebas del CD (deploy.py) y del consumidor de eventos, sin Docker ni red. [SA] (SA-9)

Ejecutar desde la raíz del repo:
    python -m pytest deploy/test_deploy.py -p no:cacheprovider
"""
import json

import pytest
import requests

import consumidor_eventos
import deploy


# ---------------------------------------------------------------- Dobles de prueba
class DockerFalso:
    """Simula los contenedores: un dict nombre -> (imagen, version)."""

    def __init__(self, produccion=None):
        self.contenedores = {}
        if produccion:
            self.contenedores[deploy.PRODUCCION["nombre"]] = produccion
        self.eventos = []
        self.etiquetas = []

    def preparar_infraestructura(self):
        self.eventos.append("infra")

    def construir(self, etiqueta):
        self.eventos.append(f"build {etiqueta}")

    def levantar(self, entorno, imagen, version, extra_env=None):
        self.contenedores[entorno["nombre"]] = (imagen, version)
        self.eventos.append(f"run {entorno['nombre']} {imagen}" + (" FALLO" if extra_env else ""))

    def eliminar(self, nombre):
        self.contenedores.pop(nombre, None)

    def version_en_ejecucion(self, nombre):
        return self.contenedores.get(nombre, (None, None))

    def etiquetar(self, origen, destino):
        self.etiquetas.append((origen, destino))

    def guardar_logs(self, nombre, destino):
        self.eventos.append(f"logs {nombre}")


class Respuesta:
    def __init__(self, status_code, cuerpo=None):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}

    def json(self):
        return self._cuerpo


class HttpFalso:
    """API falsa que se comporta como CrediCheck sana (o con fallos configurables)."""

    def __init__(self, version="v2", salud=200, sin_conexion=False, post=201):
        self.version, self.salud, self.sin_conexion, self.post_status = version, salud, sin_conexion, post

    def get(self, url, timeout):
        if self.sin_conexion:
            raise requests.ConnectionError("rechazada")
        if url.endswith("/health"):
            estado = "healthy" if self.salud == 200 else "unhealthy"
            return Respuesta(self.salud, {"status": estado, "version": self.version, "entorno": "staging"})
        if url.endswith("/api/v1/reglas"):
            return Respuesta(200, {})
        return Respuesta(200, {"id": "abc"})

    def post(self, url, json, timeout):
        return Respuesta(self.post_status, {"id": "abc", "decision": "APROBADO_PARCIAL",
                                            "comprobante": "s3://credicheck-evaluaciones/evaluaciones/abc.json"})


@pytest.fixture
def mensajes():
    return []


def _desplegar(docker, mensajes, http, **kwargs):
    return deploy.desplegar("v2", "abc1234", inicio=100.0, docker=docker, http=http, intentos=2, pausa_s=0,
                            notificar=lambda m: mensajes.append(m) or True, reloj=lambda: 142.0, **kwargs)


# ---------------------------------------------------------------- Smoke tests
def test_smoke_tests_superan_las_cuatro_verificaciones():
    superadas = deploy.smoke_tests("http://x", "v2", http=HttpFalso(), intentos=1, pausa_s=0)
    assert len(superadas) == 4


@pytest.mark.parametrize("http, motivo", [
    (HttpFalso(salud=500), "HTTP 500 en /health"),
    (HttpFalso(version="otra"), "/health inesperado"),
    (HttpFalso(post=500), "HTTP 500 al crear"),
])
def test_smoke_tests_detectan_fallos(http, motivo):
    with pytest.raises(deploy.FalloSmoke, match=motivo):
        deploy.smoke_tests("http://x", "v2", http=http, intentos=1, pausa_s=0)


def test_esperar_salud_reintenta_y_declara_servidor_inaccesible():
    with pytest.raises(deploy.ServidorInaccesible, match="ConnectionError"):
        deploy.esperar_salud("http://x", intentos=3, pausa_s=0, http=HttpFalso(sin_conexion=True))


# ---------------------------------------------------------------- Pipeline
def test_despliegue_exitoso_promueve_etiqueta_y_notifica(mensajes):
    docker = DockerFalso(produccion=("credicheck-api:v1", "v1"))

    resultado = _desplegar(docker, mensajes, HttpFalso())

    assert resultado.exito and resultado.lead_time_s == 42.0
    assert docker.contenedores == {deploy.PRODUCCION["nombre"]: ("credicheck-api:v2", "v2")}  # staging destruido
    assert docker.etiquetas == [("credicheck-api:v2", "credicheck-api:estable")]
    assert docker.eventos[:2] == ["infra", "build credicheck-api:v2"]
    assert len(mensajes) == 1 and "DESPLIEGUE EXITOSO" in mensajes[0] and "42.0 s" in mensajes[0]


def test_fallo_en_staging_hace_rollback_sin_tocar_produccion(mensajes):
    docker = DockerFalso(produccion=("credicheck-api:v1", "v1"))

    resultado = _desplegar(docker, mensajes, HttpFalso(salud=500), forzar_fallo=True)

    assert not resultado.exito and resultado.etapa == "staging"
    assert docker.contenedores == {deploy.PRODUCCION["nombre"]: ("credicheck-api:v1", "v1")}
    assert "run credicheck-staging credicheck-api:v2 FALLO" in docker.eventos
    assert "logs credicheck-staging" in docker.eventos
    assert docker.etiquetas == []
    assert len(mensajes) == 1 and "ROLLBACK" in mensajes[0] and "`v1`" in mensajes[0]
    assert "HTTP 500" in mensajes[0]


def test_staging_inaccesible_avisa_servidor_caido_y_rollback(mensajes):
    docker = DockerFalso()

    resultado = _desplegar(docker, mensajes, HttpFalso(sin_conexion=True))

    assert not resultado.exito and docker.contenedores == {}
    assert "SERVIDOR INACCESIBLE" in mensajes[0] and "localhost:8001" in mensajes[0]
    assert "ROLLBACK" in mensajes[1] and "primer despliegue" in mensajes[1]


def test_fallo_en_produccion_restaura_la_version_estable(mensajes):
    docker = DockerFalso(produccion=("credicheck-api:v1", "v1"))
    smoke_ok = lambda url, version, **_: ["ok"]  # noqa: E731  staging pasa...

    resultado = _desplegar(docker, mensajes, HttpFalso(salud=500), smoke=smoke_ok)  # ...producción no

    assert not resultado.exito and resultado.etapa == "produccion"
    assert docker.contenedores[deploy.PRODUCCION["nombre"]] == ("credicheck-api:v1", "v1")
    assert docker.etiquetas == [] and "ROLLBACK" in mensajes[0]


# ---------------------------------------------------------------- Consumidor de eventos
EVENTO = json.dumps({"tipo": "evaluacion.creada", "evaluacion": {
    "id": "abc", "solicitante": "Ana", "decision": "APROBADO", "motivo": "OK",
    "monto_solicitado": 1000.0, "monto_aprobado": 1000.0}})


class SqsFalso:
    def __init__(self, cuerpos):
        self.mensajes = [{"Body": c, "ReceiptHandle": f"r{i}"} for i, c in enumerate(cuerpos)]
        self.borrados = []

    def receive_message(self, **_):
        return {"Messages": self.mensajes}

    def delete_message(self, QueueUrl, ReceiptHandle):
        self.borrados.append(ReceiptHandle)


def test_consumidor_notifica_y_borra_el_mensaje():
    enviados = []
    sqs = SqsFalso([EVENTO])

    resultado = consumidor_eventos.consumir_lote(sqs, "url", notificar=lambda m: enviados.append(m) or True)

    assert resultado == (1, 0) and sqs.borrados == ["r0"]
    assert "Ana" in enviados[0] and "APROBADO" in enviados[0]


def test_consumidor_no_borra_si_telegram_falla():
    sqs = SqsFalso([EVENTO])
    assert consumidor_eventos.consumir_lote(sqs, "url", notificar=lambda m: False) == (0, 1)
    assert sqs.borrados == []  # SQS lo reintentará y luego irá a la DLQ


@pytest.mark.parametrize("cuerpo", ["{roto", "[]", json.dumps({"tipo": "evaluacion.creada"})])
def test_mensaje_mal_formado_no_rompe_el_consumidor(cuerpo):
    sqs = SqsFalso([cuerpo, EVENTO])
    assert consumidor_eventos.consumir_lote(sqs, "url", notificar=lambda m: True) == (1, 1)
    assert sqs.borrados == ["r1"]


def test_tipo_desconocido_se_descarta():
    assert consumidor_eventos.procesar_mensaje(json.dumps({"tipo": "otro", "evaluacion": {}})) is True
