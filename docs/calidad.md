# Calidad (Rafael Calzada González)

Rama: `feature/calidad-ci`.
Semanas que demuestra: S5 (pruebas de API y JSON Schema en contenedores), S6 (CI con GitHub Actions), S7 (SonarCloud y Quality Gates), S8 (Locust) y la validación con el analista (UAT).

## 1. Plan de pruebas

### Alcance

Entra todo lo que el contrato de la sección 7 promete al analista: salud del servicio, reglas públicas, crear una evaluación, consultarla, listar el historial y rechazar datos imposibles. Queda fuera el adaptador S3/SQS y el despliegue continuo: son de Saray. Las reglas de negocio puras las prueba Juan Camilo con Pytest; aquí se comprueba que la API no se desvía de ese contrato.

### Pirámide

| Nivel | Qué responde | Dónde vive | Dueño |
|---|---|---|---|
| Unitarias | ¿La decisión de 599 y de 600 es la correcta? | `backend/tests/unit` | Juan Camilo |
| Contrato | ¿La respuesta HTTP cumple código, cabecera, tiempo y JSON Schema? | `tests_api/` | Rafael |
| Integración | ¿El comprobante queda en S3 y el evento en SQS? | `backend/tests/integracion` | Saray, job en la CI de Rafael |
| Carga | ¿Aguanta el escenario sin pasar de 1 % de fallos ni de 800 ms en el p95? | `carga/locustfile.py` | Rafael |
| Aceptación | ¿El analista entiende la decisión en la pantalla? | Lista UAT de este documento | Rafael |

### Herramientas

| Herramienta | Versión | Uso |
|---|---|---|
| pytest | 8.3.3 | Contrato |
| requests | 2.32.3 | Peticiones HTTP del contrato |
| jsonschema | 4.23.0 | Draft 7 de los esquemas |
| GitHub Actions | SHA fijo, no tags flotantes | CI y carga |
| SonarCloud | Quality Gate «Sonar way» | Cobertura, duplicación y calificaciones del código nuevo |
| Locust | 2.31.8 | Humo, carga y estrés |

## 2. Criterios de entrada y de salida

### Entrada

- El contrato de la sección 7 no cambió (mismos campos, mismos códigos 200, 201, 400, 404 y 422).
- `python -m pytest` en `backend/` está en verde con cobertura de al menos 80 %.
- Para el contrato dentro de Docker, el servicio `api` responde `GET /health`. Hoy `docker-compose.yml` fija `STORAGE_BACKEND=s3` y el adaptador de Saray todavía lanza `NotImplementedError`, así que el POST solo puede persistir cuando ese adaptador exista. Mientras tanto el contrato se ejecuta en local con `STORAGE_BACKEND=memoria`.

### Salida

- `docker compose --profile pruebas run --rm --build test-runner` devuelve 0 y hay al menos 12 pruebas de contrato.
- Los cuatro jobs de `.github/workflows/ci.yml` están en verde: `pruebas-unitarias`, `analisis-sonarcloud`, `pruebas-integracion` y `pruebas-contrato`.
- El Quality Gate de SonarCloud queda en Passed sobre el código nuevo.
- El informe de Locust identifica el cuello de botella y, después de la optimización de Saray, compara mediana, p95 y RPS del historial.
- La lista UAT está ejecutada sobre el frontend, con el resultado anotado.

## 3. Matriz de trazabilidad

Cada fila sale de la sección 4 de la propuesta. La prueba unitaria la escribe Juan Camilo; el contrato y el caso UAT son de esta rama.

| Regla | Unitaria (JC) | Contrato (RA) | UAT |
|---|---|---|---|
| Score 599 rechaza; 600 aprueba | `test_evaluar_prestamo_fronteras` | `score_599_off_point`, `score_600_on_point` | UAT-01, UAT-02 |
| Score 851 está fuera de dominio (400) | `test_validaciones` | `score_851_fuera_de_rango` | UAT-07 |
| Ingresos 1999.99 rechazan; 2000 aprueban | frontera de ingresos | `ingresos_1999_99`, `ingresos_2000` | UAT-03, UAT-04 |
| Monto 10000.01 con score 700 ajusta a 10000 | frontera de monto | `monto_10000_01` | UAT-05 |
| Score texto, null o ausente → 422 | `test_endpoints` | `test_tipo_invalido_retorna_422` | UAT-08 |
| La evaluación creada se puede volver a leer | `test_endpoints` | `test_consultar_evaluacion_creada` | UAT-09 |
| Un id desconocido responde 404 | `test_endpoints` | `test_evaluacion_inexistente_retorna_404` | — |
| El historial va de la más reciente a la más antigua y `limite` está entre 1 y 100 | `test_endpoints` | `test_historial_cumple_esquema_y_orden`, `test_historial_limite_invalido_retorna_422` | UAT-09 |
| `GET /reglas` publica 600 y 2000 | `test_endpoints` | `test_reglas_cumplen_esquema_y_umbrales` | UAT-06 |
| `GET /health` en menos de 500 ms | `test_endpoints` | `test_health_responde_200_y_cumple_esquema` | UAT-10 |
| El POST de una evaluación válida responde en menos de 1 s | — | `test_crear_evaluacion_tiempo_respuesta` | UAT-02 |
