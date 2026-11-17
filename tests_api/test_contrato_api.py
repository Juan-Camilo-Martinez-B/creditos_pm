"""Pruebas de contrato de la API (corren en el contenedor test-runner). [RA]

Cada prueba cubre los cuatro niveles de la semana 5:
petición, código de estado, cabeceras/tiempo y esquema JSON.
"""
import os

import pytest
import requests
from jsonschema import validate

from esquemas import ERROR_SCHEMA, EVALUACION_SCHEMA, REGLAS_SCHEMA, SALUD_SCHEMA

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


def _afirmar_niveles(respuesta: requests.Response, codigo: int, schema: dict, max_segundos: float) -> dict:
    """Niveles 2, 3 y 4. El nivel 1 es la petición que produjo la respuesta."""
    assert respuesta.status_code == codigo
    tipo = respuesta.headers.get("content-type", "")
    assert tipo.startswith("application/json")
    assert respuesta.elapsed.total_seconds() < max_segundos
    cuerpo = respuesta.json()
    validate(instance=cuerpo, schema=schema)
    return cuerpo


def test_health_responde_200_y_cumple_esquema():
    respuesta = requests.get(f"{BASE_URL}/health", timeout=5)
    cuerpo = _afirmar_niveles(respuesta, 200, SALUD_SCHEMA, 0.5)
    assert cuerpo["status"] == "healthy"


def test_reglas_cumplen_esquema_y_umbrales():
    respuesta = requests.get(f"{BASE_URL}/api/v1/reglas", timeout=5)
    reglas = _afirmar_niveles(respuesta, 200, REGLAS_SCHEMA, 0.5)
    assert reglas["score"]["aprobacion_minima"] == 600
    assert reglas["ingresos_minimos"] == 2000.0
    assert reglas["multiplicadores"][0]["multiplicador"] == 3
    assert reglas["multiplicadores"][1]["multiplicador"] == 5
    assert reglas["multiplicadores"][2]["multiplicador"] == 8

SOLICITANTE = "Ana Gómez"

# Filas ★ de la matriz BVA (sección 4.5). 201 si la decisión es de negocio; 400 si el dominio es inválido.
FILAS_ESTRELLA = [
    pytest.param(599, 2500.0, 1000.0, 201, "RECHAZADO", "SCORE_INSUFICIENTE", 0.0, 0.0, id="score_599_off_point"),
    pytest.param(600, 2500.0, 1000.0, 201, "APROBADO", "CUMPLE_REQUISITOS", 7500.0, 1000.0, id="score_600_on_point"),
    pytest.param(851, 2500.0, 1000.0, 400, None, None, None, None, id="score_851_fuera_de_rango"),
    pytest.param(700, 1999.99, 1000.0, 201, "RECHAZADO", "INGRESOS_INSUFICIENTES", 0.0, 0.0, id="ingresos_1999_99"),
    pytest.param(700, 2000.0, 1000.0, 201, "APROBADO", "CUMPLE_REQUISITOS", 10000.0, 1000.0, id="ingresos_2000"),
    pytest.param(
        700, 2000.0, 10000.01, 201, "APROBADO_PARCIAL", "MONTO_AJUSTADO", 10000.0, 10000.0, id="monto_10000_01"
    ),
]


def _evaluar(score, ingresos, monto) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/api/v1/evaluaciones",
        json={
            "solicitante": SOLICITANTE,
            "score": score,
            "ingresos": ingresos,
            "monto_solicitado": monto,
        },
        timeout=5,
    )


@pytest.mark.parametrize(
    "score, ingresos, monto, codigo, decision, motivo, monto_maximo, monto_aprobado",
    FILAS_ESTRELLA,
)
def test_crear_evaluacion_fronteras(score, ingresos, monto, codigo, decision, motivo, monto_maximo, monto_aprobado):
    respuesta = _evaluar(score, ingresos, monto)
    if codigo == 400:
        _afirmar_niveles(respuesta, 400, ERROR_SCHEMA, 1)
        return
    cuerpo = _afirmar_niveles(respuesta, 201, EVALUACION_SCHEMA, 1)
    assert cuerpo["decision"] == decision
    assert cuerpo["motivo"] == motivo
    assert cuerpo["monto_maximo"] == pytest.approx(monto_maximo)
    assert cuerpo["monto_aprobado"] == pytest.approx(monto_aprobado)
