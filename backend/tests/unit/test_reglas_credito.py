"""Pruebas de las reglas de negocio: valores límite (BVA), particiones (EP) y patrón AAA. [JC]

Las filas de la matriz BVA corresponden a la sección 4.5 del documento de propuesta.
"""
import pytest

from app.reglas_credito import (
    calcular_monto_maximo,
    evaluar_prestamo,
    multiplicador_para,
    reglas_publicas,
)

# (score, ingresos, monto, decision, motivo, monto_maximo, monto_aprobado)
MATRIZ_BVA = [
    pytest.param(300, 2500.0, 1000.0, "RECHAZADO", "SCORE_INSUFICIENTE", 0.0, 0.0, id="F02_score_300_on_point_inferior"),
    pytest.param(599, 2500.0, 1000.0, "RECHAZADO", "SCORE_INSUFICIENTE", 0.0, 0.0, id="F03_score_599_off_point_aprobacion"),
    pytest.param(600, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 7500.0, 1000.0, id="F04_score_600_on_point_aprobacion"),
    pytest.param(699, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 7500.0, 1000.0, id="F05_score_699_fin_banda_1"),
    pytest.param(700, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 12500.0, 1000.0, id="F06_score_700_inicio_banda_2"),
    pytest.param(799, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 12500.0, 1000.0, id="F07_score_799_fin_banda_2"),
    pytest.param(800, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 20000.0, 1000.0, id="F08_score_800_inicio_banda_3"),
    pytest.param(850, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 20000.0, 1000.0, id="F09_score_850_on_point_superior"),
    pytest.param(700, 1999.99, 1000.0, "RECHAZADO", "INGRESOS_INSUFICIENTES", 0.0, 0.0, id="F12_ingresos_1999.99_off_point"),
    pytest.param(700, 2000.00, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", 10000.0, 1000.0, id="F13_ingresos_2000_on_point"),
    pytest.param(700, 2000.00, 10000.00, "APROBADO", "CUMPLE_REQUISITOS", 10000.0, 10000.0, id="F14_monto_igual_al_maximo"),
    pytest.param(700, 2000.00, 10000.01, "APROBADO_PARCIAL", "MONTO_AJUSTADO", 10000.0, 10000.0, id="F15_monto_un_centavo_sobre_maximo"),
    pytest.param(700, 2500.0, 500.00, "APROBADO", "CUMPLE_REQUISITOS", 12500.0, 500.0, id="F17_monto_500_on_point_minimo"),
    pytest.param(850, 20000.0, 100000.00, "APROBADO", "CUMPLE_REQUISITOS", 160000.0, 100000.0, id="monto_100000_on_point_maximo"),
    pytest.param(700, 0.0, 1000.0, "RECHAZADO", "INGRESOS_INSUFICIENTES", 0.0, 0.0, id="ingresos_0_on_point_inferior"),
]


@pytest.mark.parametrize(
    "score, ingresos, monto, decision, motivo, monto_maximo, monto_aprobado", MATRIZ_BVA
)
def test_evaluar_prestamo_fronteras(score, ingresos, monto, decision, motivo, monto_maximo, monto_aprobado):
    resultado = evaluar_prestamo(score, ingresos, monto)

    obtenido = (resultado.decision, resultado.motivo, resultado.monto_maximo, resultado.monto_aprobado)
    assert obtenido == (decision, motivo, monto_maximo, monto_aprobado)


@pytest.mark.parametrize(
    "score, ingresos, monto, decision, motivo",
    [
        pytest.param(450, 2500.0, 1000.0, "RECHAZADO", "SCORE_INSUFICIENTE", id="score_valida_rechazo"),
        pytest.param(650, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", id="score_banda_1"),
        pytest.param(750, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", id="score_banda_2"),
        pytest.param(825, 2500.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", id="score_banda_3"),
        pytest.param(700, 1000.0, 1000.0, "RECHAZADO", "INGRESOS_INSUFICIENTES", id="ingresos_valida_rechazo"),
        pytest.param(700, 3000.0, 1000.0, "APROBADO", "CUMPLE_REQUISITOS", id="ingresos_valida_aprobacion"),
        pytest.param(700, 2500.0, 50000.0, "APROBADO_PARCIAL", "MONTO_AJUSTADO", id="monto_sobre_maximo"),
    ],
)
def test_evaluar_prestamo_particiones(score, ingresos, monto, decision, motivo):
    resultado = evaluar_prestamo(score, ingresos, monto)

    assert (resultado.decision, resultado.motivo) == (decision, motivo)


@pytest.mark.parametrize(
    "score, multiplicador",
    [(600, 3), (699, 3), (700, 5), (799, 5), (800, 8), (850, 8)],
)
def test_multiplicador_por_banda(score, multiplicador):
    assert multiplicador_para(score) == multiplicador


@pytest.mark.parametrize("score", [300, 599])
def test_multiplicador_no_existe_para_scores_rechazados(score):
    with pytest.raises(ValueError, match="banda de aprobación"):
        multiplicador_para(score)


def test_calcular_monto_maximo_redondea_a_dos_decimales():
    assert calcular_monto_maximo(650, 2000.001) == 6000.0


def test_score_en_frontera_inferior_es_aprobado():
    # Arrange
    score, ingresos, monto = 600, 2500.0, 1000.0
    # Act
    resultado = evaluar_prestamo(score, ingresos, monto)
    # Assert
    assert resultado.decision == "APROBADO"


def test_monto_sobre_el_maximo_se_aprueba_parcialmente():
    # Arrange: score 700 (x5) e ingresos 2000 -> monto máximo 10 000
    score, ingresos, monto = 700, 2000.0, 10000.01
    # Act
    resultado = evaluar_prestamo(score, ingresos, monto)
    # Assert
    assert resultado.decision == "APROBADO_PARCIAL"
    assert resultado.monto_aprobado == 10000.0


def test_ingresos_insuficientes_rechazan_aunque_el_score_sea_alto():
    # Arrange
    score, ingresos, monto = 850, 1999.99, 1000.0
    # Act
    resultado = evaluar_prestamo(score, ingresos, monto)
    # Assert
    assert resultado.motivo == "INGRESOS_INSUFICIENTES"
    assert resultado.monto_aprobado == 0.0


def test_acepta_enteros_en_ingresos_y_monto():
    resultado = evaluar_prestamo(700, 2000, 1000)

    assert resultado.decision == "APROBADO"


def test_resultado_se_convierte_a_dict():
    resultado = evaluar_prestamo(600, 2500.0, 1000.0)

    assert resultado.a_dict() == {
        "decision": "APROBADO",
        "motivo": "CUMPLE_REQUISITOS",
        "monto_maximo": 7500.0,
        "monto_aprobado": 1000.0,
    }


def test_reglas_publicas_exponen_los_umbrales():
    reglas = reglas_publicas()

    assert reglas["score"] == {"minimo": 300, "maximo": 850, "aprobacion_minima": 600}
    assert reglas["ingresos_minimos"] == 2000.0
    assert reglas["monto"] == {"minimo": 500.0, "maximo": 100000.0}
    assert [m["multiplicador"] for m in reglas["multiplicadores"]] == [3, 5, 8]
