"""Fábrica del repositorio: el almacenamiento se elige con STORAGE_BACKEND. [BASE]"""
from functools import lru_cache

from app.config import settings
from app.storage.base import RepositorioEvaluaciones


@lru_cache
def get_storage() -> RepositorioEvaluaciones:
    if settings.STORAGE_BACKEND == "s3":
        from app.storage.s3_sqs import RepositorioS3Sqs

        return RepositorioS3Sqs()
    from app.storage.memoria import RepositorioMemoria

    return RepositorioMemoria()
