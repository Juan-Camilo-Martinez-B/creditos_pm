"""Pruebas de contrato de la API (corren en el contenedor test-runner). [RA] — Esqueleto: completar en RA-2."""
import os

import requests
from jsonschema import validate

from esquemas import SALUD_SCHEMA

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


def test_health_responde_200_y_cumple_esquema():
    respuesta = requests.get(f"{BASE_URL}/health", timeout=5)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    assert respuesta.elapsed.total_seconds() < 0.5
    validate(instance=respuesta.json(), schema=SALUD_SCHEMA)
