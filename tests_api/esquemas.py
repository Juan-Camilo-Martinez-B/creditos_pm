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

REGLAS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "ingresos_minimos", "monto", "multiplicadores"],
    "properties": {
        "score": {
            "type": "object",
            "additionalProperties": False,
            "required": ["minimo", "maximo", "aprobacion_minima"],
            "properties": {
                "minimo": {"const": 300},
                "maximo": {"const": 850},
                "aprobacion_minima": {"const": 600},
            },
        },
        "ingresos_minimos": {"const": 2000.0},
        "monto": {
            "type": "object",
            "additionalProperties": False,
            "required": ["minimo", "maximo"],
            "properties": {
                "minimo": {"const": 500.0},
                "maximo": {"const": 100000.0},
            },
        },
        "multiplicadores": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["desde", "hasta", "multiplicador"],
                "properties": {
                    "desde": {"type": "integer"},
                    "hasta": {"type": "integer"},
                    "multiplicador": {"type": "integer", "minimum": 1},
                },
            },
        },
    },
}
