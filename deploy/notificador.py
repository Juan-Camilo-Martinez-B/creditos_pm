"""Notificaciones de Telegram para el pipeline de CrediCheck. [JC] (tarea JC-11)

Contrato que usan deploy.py y consumidor_eventos.py (Saray):
    notificar(mensaje) -> bool
    mensaje_despliegue_exitoso(version, commit, lead_time_s) -> str
    mensaje_rollback(version, motivo, version_estable) -> str
    mensaje_servidor_inaccesible(url, error) -> str
    mensaje_evento_credito(evaluacion) -> str

Reglas de seguridad (lección de la semana 9):
- El token y el chat id se leen SOLO de variables de entorno (GitHub Secrets en el CD).
- Nunca se imprime el token.
- Una falla de Telegram nunca rompe el pipeline: notificar() no lanza excepciones.
"""
import os
import sys

import requests

URL_API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SEGUNDOS = 5


def notificar(mensaje: str) -> bool:
    """Envía el mensaje (Markdown) al chat configurado. Retorna True si Telegram respondió 200."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[TELEGRAM DESACTIVADO] Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID; mensaje no enviado.")
        return False

    try:
        respuesta = requests.post(
            URL_API.format(token=token),
            json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"},
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException as error:
        # No se imprime el error completo: la URL contiene el token.
        print(f"[TELEGRAM] No se pudo enviar la notificación ({type(error).__name__}).")
        return False

    if respuesta.status_code != 200:
        print(f"[TELEGRAM] Telegram respondió con el estado {respuesta.status_code}.")
        return False
    print("[TELEGRAM] Notificación enviada.")
    return True


def mensaje_despliegue_exitoso(version: str, commit: str, lead_time_s: float) -> str:
    return (
        "✅ *DESPLIEGUE EXITOSO EN PRODUCCIÓN*\n\n"
        "• *Servicio:* CrediCheck API\n"
        f"• *Versión:* `{version}`\n"
        f"• *Commit:* `{commit}`\n"
        "• *Smoke tests en staging:* OK\n"
        f"• *Lead time:* {lead_time_s:.1f} s\n"
        "• *Estado:* operativa"
    )


def mensaje_rollback(version: str, motivo: str, version_estable: str) -> str:
    return (
        "⚠️ *ALERTA: ROLLBACK AUTOMÁTICO ACTIVADO*\n\n"
        "• *Servicio:* CrediCheck API\n"
        f"• *Versión rechazada:* `{version}`\n"
        f"• *Motivo:* {motivo}\n"
        "• *Acción:* despliegue abortado\n"
        f"• *Estado actual:* se mantiene `{version_estable}` estable"
    )


def mensaje_servidor_inaccesible(url: str, error: str) -> str:
    return (
        "🚨 *ALERTA CRÍTICA: SERVIDOR INACCESIBLE*\n\n"
        f"• *URL:* {url}\n"
        f"• *Error:* {error}\n"
        "• *Acción:* rollback por falta de conexión"
    )


def mensaje_evento_credito(evaluacion: dict) -> str:
    return (
        "📄 *Nueva evaluación de crédito*\n\n"
        f"• *Solicitante:* {evaluacion.get('solicitante', '—')}\n"
        f"• *Decisión:* {evaluacion.get('decision', '—')} ({evaluacion.get('motivo', '—')})\n"
        f"• *Monto solicitado:* {evaluacion.get('monto_solicitado', 0):,.2f}\n"
        f"• *Monto aprobado:* {evaluacion.get('monto_aprobado', 0):,.2f}\n"
        f"• *Id:* `{evaluacion.get('id', '—')}`"
    )


if __name__ == "__main__":
    # Prueba manual: python deploy/notificador.py  (con las variables de entorno configuradas)
    ejemplos = [
        mensaje_despliegue_exitoso("v-prueba", "abc1234", 42.0),
        mensaje_rollback("v-prueba", "HTTP 500 en staging", "v-estable"),
        mensaje_servidor_inaccesible("http://localhost:8001/health", "ConnectionError"),
    ]
    enviados = sum(notificar(m) for m in ejemplos)
    print(f"Mensajes enviados: {enviados}/{len(ejemplos)}")
    sys.exit(0 if enviados == len(ejemplos) else 1)
