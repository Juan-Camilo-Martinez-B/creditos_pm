"""Pruebas de carga de CrediCheck. [RA]

Hipótesis (S8): con STORAGE_BACKEND=s3, GET /evaluaciones es el cuello de botella
porque el adaptador lista objetos y luego pide cada uno (patrón N+1).
"""
import random

from locust import HttpUser, between, events, task

CASOS = [
    {"score": 599, "ingresos": 2500.0, "monto_solicitado": 1000.0},
    {"score": 600, "ingresos": 2500.0, "monto_solicitado": 1000.0},
    {"score": 700, "ingresos": 1999.99, "monto_solicitado": 1000.0},
    {"score": 700, "ingresos": 2000.0, "monto_solicitado": 10000.01},
    {"score": 850, "ingresos": 5000.0, "monto_solicitado": 30000.0},
]


class AnalistaCredito(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def evaluar_solicitud(self):
        cuerpo = {"solicitante": "Usuario de carga", **random.choice(CASOS)}
        with self.client.post(
            "/api/v1/evaluaciones",
            json=cuerpo,
            name="POST /evaluaciones",
            catch_response=True,
        ) as respuesta:
            if respuesta.status_code != 201:
                respuesta.failure(f"Se esperaba 201 y llegó {respuesta.status_code}")

    @task(2)
    def consultar_reglas(self):
        self.client.get("/api/v1/reglas", name="GET /reglas")

    @task(1)
    def consultar_historial(self):
        self.client.get("/api/v1/evaluaciones?limite=20", name="GET /evaluaciones (historial)")

    @task(1)
    def salud(self):
        self.client.get("/health", name="GET /health")


@events.quitting.add_listener
def umbral_de_rendimiento(environment, **kwargs):
    """Quality Gate de rendimiento: más de 1 % de fallos o p95 > 800 ms rompe el escenario."""
    total = environment.stats.total
    p95 = total.get_response_time_percentile(0.95) or 0
    if total.fail_ratio > 0.01 or p95 > 800:
        environment.process_exit_code = 1
