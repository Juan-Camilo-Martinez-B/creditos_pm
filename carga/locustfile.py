"""Pruebas de carga de CrediCheck. [RA] — Esqueleto de la Fase 0: completar en RA-6."""
from locust import HttpUser, between, task


class AnalistaCredito(HttpUser):
    wait_time = between(1, 3)

    @task
    def salud(self):
        self.client.get("/health", name="GET /health")
