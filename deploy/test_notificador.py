"""Pruebas del notificador de Telegram, sin red real. [JC] (JC-11)

Ejecutar desde la raíz del repo:  python -m pytest deploy/test_notificador.py -p no:cacheprovider
"""
import pytest
import requests

import notificador

TOKEN_FALSO = "123456:TOKEN-DE-PRUEBA-NO-REAL"


class RespuestaFalsa:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture
def llamadas(monkeypatch):
    """Reemplaza requests.post por un doble de prueba que registra las llamadas."""
    registro = []

    def post_falso(url, json, timeout):
        registro.append({"url": url, "json": json, "timeout": timeout})
        return RespuestaFalsa(200)

    monkeypatch.setattr(notificador.requests, "post", post_falso)
    return registro


@pytest.fixture
def con_credenciales(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN_FALSO)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")


@pytest.mark.parametrize("variable_faltante", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
def test_sin_credenciales_no_llama_a_la_red(monkeypatch, llamadas, con_credenciales, variable_faltante, capsys):
    # Arrange
    monkeypatch.delenv(variable_faltante)
    # Act
    enviado = notificador.notificar("hola")
    # Assert
    assert enviado is False
    assert llamadas == []
    assert "[TELEGRAM DESACTIVADO]" in capsys.readouterr().out


def test_con_credenciales_envia_al_chat_correcto(llamadas, con_credenciales):
    enviado = notificador.notificar("*hola*")

    assert enviado is True
    assert llamadas == [{
        "url": f"https://api.telegram.org/bot{TOKEN_FALSO}/sendMessage",
        "json": {"chat_id": "-100123", "text": "*hola*", "parse_mode": "Markdown"},
        "timeout": 5,
    }]


def test_respuesta_distinta_de_200_retorna_false(monkeypatch, con_credenciales):
    monkeypatch.setattr(notificador.requests, "post", lambda url, json, timeout: RespuestaFalsa(401))

    assert notificador.notificar("hola") is False


@pytest.mark.parametrize("excepcion", [requests.ConnectionError, requests.Timeout])
def test_error_de_red_no_rompe_el_pipeline(monkeypatch, con_credenciales, excepcion, capsys):
    def post_que_falla(url, json, timeout):
        raise excepcion(f"fallo al conectar con {url}")

    monkeypatch.setattr(notificador.requests, "post", post_que_falla)

    assert notificador.notificar("hola") is False
    assert TOKEN_FALSO not in capsys.readouterr().out


def test_ninguna_salida_expone_el_token(llamadas, con_credenciales, capsys):
    notificador.notificar("hola")

    assert TOKEN_FALSO not in capsys.readouterr().out


def test_mensaje_despliegue_exitoso():
    mensaje = notificador.mensaje_despliegue_exitoso("a1b2c3d", "a1b2c3d4e5", 42.31)

    assert "DESPLIEGUE EXITOSO" in mensaje
    assert "a1b2c3d" in mensaje
    assert "42.3 s" in mensaje


def test_mensaje_rollback():
    mensaje = notificador.mensaje_rollback("v2", "HTTP 500 en staging", "v1")

    assert "ROLLBACK AUTOMÁTICO" in mensaje
    assert "HTTP 500 en staging" in mensaje
    assert "`v1`" in mensaje and "`v2`" in mensaje


def test_mensaje_servidor_inaccesible():
    mensaje = notificador.mensaje_servidor_inaccesible("http://localhost:8001/health", "ConnectionError")

    assert "SERVIDOR INACCESIBLE" in mensaje
    assert "http://localhost:8001/health" in mensaje


def test_mensaje_evento_credito():
    evaluacion = {
        "id": "abc", "solicitante": "Ana Gómez", "decision": "APROBADO_PARCIAL",
        "motivo": "MONTO_AJUSTADO", "monto_solicitado": 10000.01, "monto_aprobado": 10000.0,
    }

    mensaje = notificador.mensaje_evento_credito(evaluacion)

    assert "Ana Gómez" in mensaje
    assert "APROBADO_PARCIAL (MONTO_AJUSTADO)" in mensaje
    assert "10,000.00" in mensaje


def test_mensaje_evento_credito_tolera_campos_faltantes():
    assert "—" in notificador.mensaje_evento_credito({})
