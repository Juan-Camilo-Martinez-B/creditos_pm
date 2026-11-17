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
