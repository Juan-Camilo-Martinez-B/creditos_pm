"""API de CrediCheck. [JC] — Esqueleto de la Fase 0: solo /health. Los demás endpoints van en JC-4."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings

app = FastAPI(
    title="CrediCheck API",
    version=settings.APP_VERSION,
    description="Evaluación de solicitudes de crédito (proyecto final de Pruebas y Mantenimiento).",
)


@app.get("/health")
def health() -> JSONResponse:
    sano = not settings.forzar_fallo_salud()
    cuerpo = {
        "status": "healthy" if sano else "unhealthy",
        "version": settings.APP_VERSION,
        "entorno": settings.APP_ENV,
    }
    return JSONResponse(status_code=200 if sano else 500, content=cuerpo)
