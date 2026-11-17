"""Pruebas de contrato de la API (corren en el contenedor test-runner). [RA]

Cada prueba cubre los cuatro niveles de la semana 5:
petición, código de estado, cabeceras/tiempo y esquema JSON.
"""
import os

import requests
from jsonschema import validate

from esquemas import REGLAS_SCHEMA, SALUD_SCHEMA

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
