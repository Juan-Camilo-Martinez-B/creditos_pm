"""Consumidor de la cola credicheck-eventos: avisa por Telegram cada evaluación creada. [SA] (tarea SA-8)

Semántica "al menos una vez":
- El mensaje se borra de la cola SOLO si se procesó bien (Telegram respondió).
- Si falla, no se borra: SQS lo vuelve a entregar al vencer el VisibilityTimeout y, tras
  3 recepciones (ver infra/init_infra.py), lo mueve a credicheck-eventos-dlq.
- Un mensaje mal formado nunca rompe el consumidor; también termina en la DLQ.

Uso (desde la raíz del repo, con LocalStack arriba):
    python deploy/consumidor_eventos.py            # escucha indefinidamente (Ctrl+C para salir)
    python deploy/consumidor_eventos.py --una-vez  # procesa lo que haya y termina (demo / CI)
"""
import argparse
import json
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notificador  # noqa: E402

TIPO_EVENTO = "evaluacion.creada"


def procesar_mensaje(cuerpo: str, notificar=notificador.notificar) -> bool:
    """Retorna True si el mensaje quedó atendido y puede borrarse de la cola."""
    try:
        evento = json.loads(cuerpo)
        evaluacion = evento["evaluacion"]
    except (ValueError, KeyError, TypeError):
        print("[CONSUMIDOR] Mensaje mal formado: se deja para que termine en la DLQ.")
        return False
    if evento.get("tipo") != TIPO_EVENTO:
        print(f"[CONSUMIDOR] Tipo desconocido '{evento.get('tipo')}': se ignora y se borra.")
        return True
    print(f"[CONSUMIDOR] {evaluacion.get('id')} -> {evaluacion.get('decision')}")
    return notificar(notificador.mensaje_evento_credito(evaluacion))


def consumir_lote(sqs, url_cola: str, espera_s: int = 10, notificar=notificador.notificar) -> tuple[int, int]:
    """Lee hasta 10 mensajes (long polling). Retorna (procesados, fallidos)."""
    respuesta = sqs.receive_message(QueueUrl=url_cola, MaxNumberOfMessages=10, WaitTimeSeconds=espera_s)
    procesados = fallidos = 0
    for mensaje in respuesta.get("Messages", []):
        if procesar_mensaje(mensaje["Body"], notificar):
            sqs.delete_message(QueueUrl=url_cola, ReceiptHandle=mensaje["ReceiptHandle"])
            procesados += 1
        else:
            fallidos += 1
    return procesados, fallidos


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Consumidor de eventos de CrediCheck")
    parser.add_argument("--una-vez", action="store_true", help="Procesa un lote y termina")
    args = parser.parse_args(argv)

    sqs = boto3.client(
        "sqs",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )
    url_cola = sqs.get_queue_url(QueueName=os.getenv("COLA_EVENTOS", "credicheck-eventos"))["QueueUrl"]
    print(f"[CONSUMIDOR] Escuchando {url_cola}")

    total_procesados = total_fallidos = 0
    try:
        while True:
            procesados, fallidos = consumir_lote(sqs, url_cola, espera_s=1 if args.una_vez else 10)
            total_procesados += procesados
            total_fallidos += fallidos
            if args.una_vez:
                break
    except KeyboardInterrupt:
        pass
    print(f"[CONSUMIDOR] Procesados: {total_procesados} · Fallidos: {total_fallidos}")
    return 0 if total_fallidos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
