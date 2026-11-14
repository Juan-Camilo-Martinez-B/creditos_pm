"""Pruebas del esqueleto de la Fase 0. [JC] — se reemplazan por las suites reales (JC-2, JC-6)."""
from app.storage import get_storage
from app.storage.memoria import RepositorioMemoria


def test_health_responde_sano(client):
    # Arrange: API con la configuración por defecto
    # Act
    respuesta = client.get("/health")
    # Assert
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "healthy"


def test_health_simula_fallo(client, monkeypatch):
    # Arrange
    monkeypatch.setenv("FORZAR_FALLO_SALUD", "true")
    # Act
    respuesta = client.get("/health")
    # Assert
    assert respuesta.status_code == 500
    assert respuesta.json()["status"] == "unhealthy"


def test_fabrica_usa_memoria_por_defecto():
    get_storage.cache_clear()
    assert isinstance(get_storage(), RepositorioMemoria)
