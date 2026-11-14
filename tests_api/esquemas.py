"""JSON Schemas del contrato de la API. [RA] — Esqueleto de la Fase 0: completar en RA-1."""

SALUD_SCHEMA = {
    "type": "object",
    "required": ["status", "version", "entorno"],
    "properties": {
        "status": {"enum": ["healthy", "unhealthy"]},
        "version": {"type": "string"},
        "entorno": {"type": "string"},
    },
}
