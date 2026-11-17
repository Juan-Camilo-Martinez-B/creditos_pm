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

EVALUACION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "id",
        "solicitante",
        "score",
        "ingresos",
        "monto_solicitado",
        "decision",
        "motivo",
        "monto_maximo",
        "monto_aprobado",
        "comprobante",
        "fecha",
        "version_api",
    ],
    "properties": {
        "id": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
        "solicitante": {"type": "string", "minLength": 3, "maxLength": 80},
        "score": {"type": "integer", "minimum": 300, "maximum": 850},
        "ingresos": {"type": "number", "minimum": 0},
        "monto_solicitado": {"type": "number", "minimum": 500, "maximum": 100000},
        "decision": {"enum": ["APROBADO", "APROBADO_PARCIAL", "RECHAZADO"]},
        "motivo": {
            "enum": [
                "CUMPLE_REQUISITOS",
                "MONTO_AJUSTADO",
                "SCORE_INSUFICIENTE",
                "INGRESOS_INSUFICIENTES",
            ]
        },
        "monto_maximo": {"type": "number", "minimum": 0},
        "monto_aprobado": {"type": "number", "minimum": 0},
        "comprobante": {"type": "string", "minLength": 1},
        "fecha": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T"},
        "version_api": {"type": "string", "minLength": 1},
    },
}
