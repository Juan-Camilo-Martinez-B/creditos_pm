"""API de CrediCheck: implementa el contrato de la sección 7 del documento. [JC]"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.reglas_credito import evaluar_prestamo, reglas_publicas
from app.schemas import (
    ErrorRespuesta,
    EvaluacionRespuesta,
    ReglasRespuesta,
    SaludRespuesta,
    SolicitudEvaluacion,
)
from app.storage import get_storage
from app.storage.base import RepositorioEvaluaciones

app = FastAPI(
    title="CrediCheck API",
    version=settings.APP_VERSION,
    description=(
        "Evaluación automática de solicitudes de crédito. Proyecto final de "
        "Pruebas y Mantenimiento de Software (UCC)."
    ),
)


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@app.get(
    "/health",
    response_model=SaludRespuesta,
    responses={500: {"model": SaludRespuesta, "description": "Servicio no saludable"}},
    tags=["observabilidad"],
)
def health() -> JSONResponse:
    sano = not settings.forzar_fallo_salud()
    cuerpo = {
        "status": "healthy" if sano else "unhealthy",
        "version": settings.APP_VERSION,
        "entorno": settings.APP_ENV,
    }
    return JSONResponse(status_code=200 if sano else 500, content=cuerpo)


@app.get("/api/v1/reglas", response_model=ReglasRespuesta, tags=["reglas"])
def obtener_reglas() -> dict:
    return reglas_publicas()


@app.post(
    "/api/v1/evaluaciones",
    response_model=EvaluacionRespuesta,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorRespuesta, "description": "Valor fuera del dominio de negocio"}},
    tags=["evaluaciones"],
)
def crear_evaluacion(
    solicitud: SolicitudEvaluacion,
    repositorio: RepositorioEvaluaciones = Depends(get_storage),
) -> dict:
    try:
        resultado = evaluar_prestamo(solicitud.score, solicitud.ingresos, solicitud.monto_solicitado)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    evaluacion = {
        "id": str(uuid4()),
        "solicitante": solicitud.solicitante,
        "score": solicitud.score,
        "ingresos": float(solicitud.ingresos),
        "monto_solicitado": float(solicitud.monto_solicitado),
        **resultado.a_dict(),
        "fecha": _ahora_iso(),
        "version_api": settings.APP_VERSION,
    }
    evaluacion["comprobante"] = repositorio.guardar(evaluacion)
    repositorio.publicar_evento(evaluacion)
    return evaluacion


@app.get("/api/v1/evaluaciones", response_model=list[EvaluacionRespuesta], tags=["evaluaciones"])
def listar_evaluaciones(
    limite: int = Query(20, ge=1, le=100, description="Cantidad máxima de evaluaciones (1-100)"),
    repositorio: RepositorioEvaluaciones = Depends(get_storage),
) -> list[dict]:
    return repositorio.listar(limite)


@app.get(
    "/api/v1/evaluaciones/{evaluacion_id}",
    response_model=EvaluacionRespuesta,
    responses={404: {"model": ErrorRespuesta, "description": "Evaluación no encontrada"}},
    tags=["evaluaciones"],
)
def obtener_evaluacion(
    evaluacion_id: str,
    repositorio: RepositorioEvaluaciones = Depends(get_storage),
) -> dict:
    evaluacion = repositorio.obtener(evaluacion_id)
    if evaluacion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")
    return evaluacion
