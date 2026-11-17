"""Pruebas de carga de CrediCheck. [RA]

Hipótesis (S8): con STORAGE_BACKEND=s3, GET /evaluaciones es el cuello de botella
porque el adaptador lista objetos y luego pide cada uno (patrón N+1).
"""
import random

from locust import HttpUser, between, task

CASOS = [
    {"score": 599, "ingresos": 2500.0, "monto_solicitado": 1000.0},
    {"score": 600, "ingresos": 2500.0, "monto_solicitado": 1000.0},
    {"score": 700, "ingresos": 1999.99, "monto_solicitado": 1000.0},
    {"score": 700, "ingresos": 2000.0, "monto_solicitado": 10000.01},
    {"score": 850, "ingresos": 5000.0, "monto_solicitado": 30000.0},
]
