"""Pruebas del adaptador en memoria. [JC]"""
from app.storage.memoria import RepositorioMemoria


def evaluacion(evaluacion_id, fecha, decision="APROBADO"):
    return {"id": evaluacion_id, "fecha": fecha, "decision": decision}


def test_guardar_agrega_el_comprobante_y_retorna_la_referencia():
    repo = RepositorioMemoria()

    referencia = repo.guardar(evaluacion("a", "2026-11-20T10:00:00.000000Z"))

    assert referencia == "memoria://evaluaciones/a.json"
    assert repo.obtener("a")["comprobante"] == referencia


def test_guardar_dos_veces_el_mismo_id_no_duplica_el_historial():
    # Arrange
    repo = RepositorioMemoria()
    repo.guardar(evaluacion("a", "2026-11-20T10:00:00.000000Z"))
    # Act
    repo.guardar(evaluacion("a", "2026-11-20T10:00:00.000000Z", decision="RECHAZADO"))
    # Assert
    assert len(repo.listar()) == 1
    assert repo.obtener("a")["decision"] == "RECHAZADO"


def test_listar_ordena_por_fecha_y_desempata_por_llegada():
    repo = RepositorioMemoria()
    repo.guardar(evaluacion("vieja", "2026-11-19T10:00:00.000000Z"))
    repo.guardar(evaluacion("empate-1", "2026-11-20T10:00:00.000000Z"))
    repo.guardar(evaluacion("empate-2", "2026-11-20T10:00:00.000000Z"))

    assert [e["id"] for e in repo.listar()] == ["empate-2", "empate-1", "vieja"]


def test_obtener_retorna_una_copia():
    repo = RepositorioMemoria()
    repo.guardar(evaluacion("a", "2026-11-20T10:00:00.000000Z"))

    copia = repo.obtener("a")
    copia["decision"] = "MODIFICADA"

    assert repo.obtener("a")["decision"] == "APROBADO"
