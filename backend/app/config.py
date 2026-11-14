"""Configuración leída de variables de entorno. [BASE] — no modificar sin acuerdo del equipo."""
import os


def _bool(nombre: str) -> bool:
    return os.getenv(nombre, "false").strip().lower() in ("1", "true", "si", "yes")


class Settings:
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    APP_ENV = os.getenv("APP_ENV", "desarrollo")  # desarrollo | staging | produccion
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "memoria")  # memoria | s3
    AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    BUCKET_EVALUACIONES = os.getenv("BUCKET_EVALUACIONES", "credicheck-evaluaciones")
    COLA_EVENTOS = os.getenv("COLA_EVENTOS", "credicheck-eventos")

    def forzar_fallo_salud(self) -> bool:
        """Se lee en cada petición para poder simular un fallo (CD y pruebas con monkeypatch)."""
        return _bool("FORZAR_FALLO_SALUD")


settings = Settings()
