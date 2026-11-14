"""Aprovisionamiento IaC de CrediCheck en LocalStack. [SA] — Esqueleto de la Fase 0: implementar en SA-1.

Debe ser declarativo e idempotente: crear el bucket credicheck-evaluaciones y las colas
credicheck-eventos / credicheck-eventos-dlq solo si no existen.
"""
import sys


def main() -> int:
    print("=== APROVISIONAMIENTO IAC CREDICHECK ===")
    print(" -> [PENDIENTE] SA-1: crear bucket y colas de forma idempotente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
