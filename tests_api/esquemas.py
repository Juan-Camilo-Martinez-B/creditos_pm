"""JSON Schemas (draft 7) del contrato de la API. [RA]"""

SALUD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "version", "entorno"],
    "properties": {
        "status": {"enum": ["healthy", "unhealthy"]},
        "version": {"type": "string", "minLength": 1},
        "entorno": {"enum": ["desarrollo", "staging", "produccion"]},
    },
}
