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

## 4. Lista de aceptación (UAT)

Se ejecuta en el frontend (`http://localhost:8081`) como si quien opera fuera el analista de crédito. Validación: ¿construimos lo correcto? El nombre del solicitante puede ser cualquier texto de 3 a 80 caracteres.

| Id | Pasos | Resultado esperado |
|---|---|---|
| UAT-01 | Pulsar el chip «Score 599» y luego «Evaluar solicitud». | La tarjeta dice «Rechazado» y explica que el score está por debajo de 600. Monto aprobado US$ 0,00. |
| UAT-02 | Pulsar «Score 600» y evaluar. | Dice «Aprobado» y «Cumple todos los requisitos». Monto máximo US$ 7.500,00 y monto aprobado US$ 1.000,00. |
| UAT-03 | Pulsar «Ingresos 1999.99» y evaluar. | «Rechazado» porque los ingresos son menores a US$ 2.000,00. |
| UAT-04 | Pulsar «Ingresos 2000» y evaluar. | «Aprobado». Con score 700 el máximo es US$ 10.000,00 y se aprueba el US$ 1.000,00 pedido. |
| UAT-05 | Pulsar «Monto 10000.01» y evaluar. | «Aprobado parcialmente». El texto dice que se aprueba hasta el monto máximo. Monto aprobado US$ 10.000,00, no los 10.000,01 pedidos. |
| UAT-06 | Leer la tabla «Reglas y fronteras» sin evaluar nada. | Se ve la aprobación mínima en 600, los ingresos mínimos en 2.000 y las bandas ×3, ×5 y ×8. Esos números vienen de `GET /api/v1/reglas`. |
| UAT-07 | Pulsar «Score 851 (inválido)» y evaluar. | «No se pudo evaluar» y el mensaje de score fuera de rango (300-850). No aparece una fila nueva de decisión Aprobado. |
| UAT-08 | Borrar el score y pulsar evaluar; después escribir un solicitante de dos letras. | El formulario no envía la solicitud (campos requeridos y longitud mínima). No hay decisión a medias. |
| UAT-09 | Evaluar UAT-01 y enseguida UAT-02. Pulsar «Actualizar» en Historial. | La fila de score 600 queda por encima de la de score 599. El filtro «Aprobado» deja solo la segunda. |
| UAT-10 | Mirar el indicador del encabezado. Apagar la API y esperar hasta 15 s. | En línea se lee versión y entorno. Al caer la API el indicador pasa a «API no disponible». |

Estas diez filas se marcan en la sustentación, con la pantalla abierta, no solo con el JSON de la API.

## 5. Plantilla de reporte de defecto

Copiar este bloque al abrir un issue. El título nombra el síntoma, no la causa supuesta.

```
Título: [pantalla o endpoint] qué se ve

Pasos para reproducir:
1.
2.
3.

Resultado esperado:
Resultado obtenido:

Clasificación (semana 1):
- Error (equivocación humana):
- Defecto (lo incorrecto en el código o la configuración):
- Fallo (lo que ve el usuario o la prueba):

Datos: score / ingresos / monto / id
Entorno: desarrollo | staging | produccion
Versión de la API:
Prueba que lo detecta: (unitaria, contrato, UAT o Locust)
Severidad: bloqueante | mayor | menor
Dueño del archivo (CODEOWNERS):
```

Ejemplo ya resuelto en el diseño, para explicar la cadena en la sustentación: alguien entiende «score mayor a 600» y escribe `score > 600`. El defecto está en la comparación. El fallo es que una persona con score 600 sale rechazada. La fila `score_600_on_point` lo detiene antes de llegar al analista.

## 6. Carga con Locust

Tres escenarios. El de humo y el de carga buscan 0 % de fallos y p95 del POST por debajo de 800 ms (OE6). El de estrés busca el punto de quiebre.

| Escenario | Usuarios | Spawn | Duración | Comando |
|---|---|---|---|---|
| Humo | 10 | 2/s | 1 min | `locust -f carga/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 1m` |
| Carga | 100 | 10/s | 5 min | `-u 100 -r 10 -t 5m` |
| Estrés | 500 y subir hacia 2000 | 50/s | hasta que el p95 o los fallos se disparen | `-u 500 -r 50 -t 3m`, luego repetir con más usuarios |

En GitHub: Actions → «Pruebas de carga» → Run workflow. El resultado queda en el artefacto `reporte-carga` (`carga/resultados/reporte.html` y los CSV). El job usa el mismo umbral que el listener `umbral_de_rendimiento`: si los fallos superan 1 % o el p95 global supera 800 ms, Locust termina con código 1.

### Cuello de botella (hipótesis para Saray)

`GET /api/v1/evaluaciones` será el más lento cuando el almacenamiento sea S3. `listar()` hace un `list_objects` y después una lectura por cada objeto (N+1). En memoria ese listado es un ordenamiento local, así que no sirve para declarar el cuello de botella: hay que medirlo con `STORAGE_BACKEND=s3` y el adaptador real. La comparación antes/después (mediana, p95 y RPS solo del historial) se llena cuando Saray entregue el índice `indices/recientes.json`.

| Métrica del historial | Antes (N+1) | Después (índice) |
|---|---|---|
| Mediana | pendiente de la medición sobre S3 | pendiente |
| p95 | pendiente | pendiente |
| RPS | pendiente | pendiente |

## 7. SonarCloud

1. Entrar a sonarcloud.io con GitHub e importar `Juan-Camilo-Martinez-B/creditos_pm`.
2. Desactivar Automatic Analysis. Si queda activo, choca con el análisis del CI.
3. Copiar la organización y el project key reales a `sonar-project.properties` si difieren de `juan-camilo-martinez-b` y `juan-camilo-martinez-b_creditos_pm`.
4. Crear el secreto `SONAR_TOKEN` en el repositorio (Settings → Secrets → Actions). No se escribe en el código ni en `.env` versionado.
5. `sonar.qualitygate.wait=true` hace fallar el job `analisis-sonarcloud` si el gate no pasa, y ese job es un status check obligatorio.

Gate «Sonar way» sobre código nuevo: cobertura ≥ 80 %, duplicación ≤ 3 %, fiabilidad, seguridad y mantenibilidad en A, y 100 % de hotspots revisados. Los hallazgos se abren como issues asignados al dueño del archivo (CODEOWNERS); cada quien los corrige en su rama.

## 8. Protección de `main` (RA-4)

Lo hace un administrador del repositorio (Juan Camilo), en Settings → Branches → regla de `main`:

- Exigir Pull Request antes de mergear.
- Una aprobación.
- Revisión de CODEOWNERS.
- Status checks obligatorios: `pruebas-unitarias`, `analisis-sonarcloud`, `pruebas-integracion`, `pruebas-contrato`.
- Prohibir force push.

Evidencia para la sustentación: un PR con el botón de merge bloqueado mientras uno de esos checks está en rojo. Los PR se cierran con «Create a merge commit» y la rama no se borra. El orden del hito es Juan Camilo, luego Saray, luego esta rama.

## 9. Cómo ejecutar la parte de Rafael

```bash
# Contrato contra la API en memoria (no toca archivos de otros)
cd backend
set STORAGE_BACKEND=memoria
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# En otra terminal, desde tests_api/
python -m pip install -r requirements.txt
python -m pytest -v --tb=short test_contrato_api.py

# Igual que la CI, cuando el adaptador S3 ya persista
docker compose --profile pruebas run --rm --build test-runner

# Carga con interfaz en http://localhost:8089
docker compose --profile carga up -d --build
```
