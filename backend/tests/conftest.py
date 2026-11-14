"""Fixtures compartidas de las pruebas unitarias. [JC]"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage
from app.storage.memoria import RepositorioMemoria


@pytest.fixture
def repositorio():
    """Un repositorio en memoria nuevo por prueba: cada prueba es independiente."""
    return RepositorioMemoria()


@pytest.fixture
def client(repositorio):
    app.dependency_overrides[get_storage] = lambda: repositorio
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest.fixture
def solicitud_valida():
    return {"solicitante": "Ana Gómez", "score": 700, "ingresos": 2000.0, "monto_solicitado": 10000.01}
