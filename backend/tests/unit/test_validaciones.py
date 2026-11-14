"""Pruebas negativas: entradas destructivas que el sistema debe rechazar (pytest.raises). [JC]"""
import math

import pytest

from app.reglas_credito import evaluar_prestamo


@pytest.mark.parametrize(
    "score, ingresos, monto",
    [
        pytest.param("700", 2500.0, 1000.0, id="score_texto"),
        pytest.param(True, 2500.0, 1000.0, id="score_booleano"),
        pytest.param(700.5, 2500.0, 1000.0, id="score_decimal"),
        pytest.param(None, 2500.0, 1000.0, id="score_nulo"),
        pytest.param(700, None, 1000.0, id="ingresos_nulos"),
        pytest.param(700, "2500", 1000.0, id="ingresos_texto"),
        pytest.param(700, True, 1000.0, id="ingresos_booleano"),
        pytest.param(700, 2500.0, None, id="monto_nulo"),
        pytest.param(700, 2500.0, "1000", id="monto_texto"),
        pytest.param(700, 2500.0, False, id="monto_booleano"),
    ],
)
def test_tipos_invalidos_lanzan_type_error(score, ingresos, monto):
    with pytest.raises(TypeError):
        evaluar_prestamo(score, ingresos, monto)


@pytest.mark.parametrize(
    "score, ingresos, monto, mensaje",
    [
        pytest.param(299, 2500.0, 1000.0, "Score fuera de rango", id="F01_score_299_off_point_inferior"),
        pytest.param(851, 2500.0, 1000.0, "Score fuera de rango", id="F10_score_851_off_point_superior"),
        pytest.param(700, -0.01, 1000.0, "ingresos no pueden ser negativos", id="F11_ingresos_negativos"),
        pytest.param(700, 2500.0, 499.99, "monto debe estar entre", id="F16_monto_499.99_off_point_minimo"),
        pytest.param(700, 2500.0, 100000.01, "monto debe estar entre", id="F18_monto_100000.01_off_point_maximo"),
        pytest.param(700, math.nan, 1000.0, "ingresos no pueden ser negativos", id="ingresos_nan"),
        pytest.param(700, 2500.0, math.inf, "monto debe estar entre", id="monto_infinito"),
    ],
)
def test_valores_fuera_de_dominio_lanzan_value_error(score, ingresos, monto, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        evaluar_prestamo(score, ingresos, monto)
