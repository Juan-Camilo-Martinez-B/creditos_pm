# Infraestructura y despliegue continuo (Saray)

Rama: `feature/infra-cd`. Tareas SA-1 a SA-10 de la propuesta.

| Tarea | Entregable | Archivo |
|---|---|---|
| SA-1 | IaC declarativa e idempotente (bucket + cola + DLQ) | [infra/init_infra.py](../infra/init_infra.py) |
| SA-3 | Adaptador `RepositorioS3Sqs` (comprobante en S3, evento en SQS) | [backend/app/storage/s3_sqs.py](../backend/app/storage/s3_sqs.py) |
| SA-4 | Pruebas de integración contra LocalStack + pruebas sin red | [backend/tests/integracion/](../backend/tests/integracion/) |
| SA-5 / SA-6 | Pipeline de CD con smoke tests y rollback automático | [deploy/deploy.py](../deploy/deploy.py) |
| SA-7 | Optimización del historial (índice `indices/recientes.json`) | [s3_sqs.py](../backend/app/storage/s3_sqs.py) |
| SA-8 | Consumidor de eventos SQS → Telegram | [deploy/consumidor_eventos.py](../deploy/consumidor_eventos.py) |
| SA-9 | Pruebas del pipeline sin Docker ni red | [deploy/test_deploy.py](../deploy/test_deploy.py) |
| SA-10 | Workflow de GitHub Actions y secretos | [.github/workflows/cd.yml](../.github/workflows/cd.yml) |

## 1. Arquitectura

```
Analista ──► Frontend (nginx :8081) ──► API FastAPI (:8000)
                                          │  guardar()          ┌──────────────────────────────────────┐
                                          ├────────────────────►│ S3  credicheck-evaluaciones           │
                                          │                     │   evaluaciones/<id>.json  (comprobante)│
                                          │                     │   indices/recientes.json  (100 últimas)│
                                          │  publicar_evento()  └──────────────────────────────────────┘
                                          └────────────────────► SQS credicheck-eventos ──(3 fallos)──► credicheck-eventos-dlq
                                                                      │
                                                     consumidor_eventos.py ──► Telegram 📄
```

S3 y SQS se emulan con **LocalStack 3.8.1**; el mismo código funciona contra AWS real porque el endpoint
sale de `AWS_ENDPOINT_URL`.

## 2. IaC idempotente (SA-1)

`infra/init_infra.py` describe el **estado deseado** y solo crea lo que falta:

| Recurso | Configuración |
|---|---|
| Bucket `credicheck-evaluaciones` | versionado, cifrado AES256, bloqueo de acceso público |
| Cola `credicheck-eventos-dlq` | retención de 14 días |
| Cola `credicheck-eventos` | `RedrivePolicy` a la DLQ con `maxReceiveCount = 3`, visibilidad 30 s |

Lo ejecuta el servicio `infra-init` de `docker-compose.yml` antes de que arranque la API. Si falla, termina con
código 1 y la API no arranca (`service_completed_successfully`).

**Idempotencia demostrable:** ejecutarlo dos veces seguidas no falla ni duplica recursos.

```bash
docker compose up -d --wait localstack
docker compose run --rm infra-init   # 1.ª vez: CREADO / CREADA
docker compose run --rm infra-init   # 2.ª vez: YA EXISTE (mismo resultado final)
```

La prueba automática es `test_iac_es_idempotente` en las pruebas de integración.

## 3. Adaptador S3/SQS (SA-3)

Implementa el contrato `RepositorioEvaluaciones` (`backend/app/storage/base.py`), igual que el adaptador en memoria
de Juan Camilo, así que la API no cambia: se elige con `STORAGE_BACKEND=s3`.

| Método | S3 / SQS |
|---|---|
| `guardar(evaluacion)` | `PutObject evaluaciones/<id>.json` **con el campo `comprobante`** (acuerdo con Juan Camilo) y actualiza el índice. Retorna `s3://credicheck-evaluaciones/evaluaciones/<id>.json` |
| `obtener(id)` | `GetObject`; `None` si no existe. Un id con `/` se rechaza sin tocar S3 (no se puede salir del prefijo) |
| `listar(limite)` | Una sola lectura del índice; si falta o está corrupto, escaneo de respaldo |
| `publicar_evento(evaluacion)` | `SendMessage` con `{"tipo": "evaluacion.creada", "evaluacion": {...}}` y atributo `tipo` |

## 4. Optimización del historial (SA-7)

Hallazgo de las pruebas de carga de Rafael: `GET /api/v1/evaluaciones` era el cuello de botella porque listar hacía
un `ListObjects` **y una lectura por cada evaluación** (patrón N+1): el tiempo crecía con el volumen.

Solución: el índice `indices/recientes.json` guarda las 100 evaluaciones más recientes (el máximo de `?limite=`)
y se actualiza en cada `guardar()` (protegido con un `threading.Lock`, porque uvicorn atiende en varios hilos).
Ahora el historial cuesta **1 lectura** sin importar cuántas evaluaciones haya.

| Modo | Lecturas a S3 para listar 30 evaluaciones | Prueba |
|---|---|---|
| Escaneo (antes) | 30 | `test_listar_por_escaneo_hace_n_mas_1_lecturas` |
| Índice (después) | 1 | `test_listar_con_indice_hace_una_sola_lectura` |

Para medir el "antes" en Locust se puede forzar el modo anterior sin cambiar código:

```bash
# docker-compose.override.yml local (no se sube):  services: { api: { environment: [LISTADO_S3=escaneo] } }
```

> Limitación conocida: el candado protege un solo proceso. Con varios workers o réplicas habría que pasar el
> índice a una tabla (DynamoDB) o usar escrituras condicionales; para el alcance del proyecto basta.

## 5. Pruebas (SA-4 y SA-9)

| Suite | Qué valida | Cómo se ejecuta |
|---|---|---|
| `backend/tests/integracion/test_storage_s3.py` (marcador `integracion`) | Adaptador contra LocalStack real: comprobante en S3, orden y límite, índice corrupto, evento en SQS, API extremo a extremo e idempotencia de la IaC | Job `pruebas-integracion` de la CI |
| `backend/tests/integracion/test_s3_sqs_sin_red.py` | Lógica del adaptador con dobles de S3/SQS (cuenta lecturas) | Con `python -m pytest` normal |
| `deploy/test_deploy.py` | Pipeline de CD (éxito, rollback en staging, servidor inaccesible, fallo en producción) y consumidor | Primer paso del CD |

Las pruebas de integración crean un **bucket y una cola temporales** con sufijo aleatorio y los borran al
final: no dependen de datos previos ni ensucian `credicheck-evaluaciones`.

```bash
# Integración (requiere LocalStack)
docker compose up -d --wait localstack
cd backend && python -m pytest -m integracion --no-cov

# Pipeline y consumidor (sin Docker ni red), desde la raíz
python -m pip install -r deploy/requirements.txt
python -m pytest deploy/ -p no:cacheprovider
```

## 6. Despliegue continuo con rollback (SA-5, SA-6, SA-10)

`deploy/deploy.py` implementa un Blue/Green simplificado con dos contenedores:

| Paso | Qué hace | Si falla |
|---|---|---|
| 1. Infraestructura | `docker compose up localstack` + IaC idempotente | Exit 1 |
| 2. Construcción | `docker build -t credicheck-api:<sha>` | Exit 1 |
| 3. Staging | `credicheck-staging` en **:8001** con la versión candidata | — |
| 4. Smoke tests | `GET /health` (200, `healthy` y versión correcta), `GET /reglas`, `POST` de una evaluación real con comprobante `s3://` y `GET` por id | **Rollback:** se guardan los logs, se destruye staging, producción **no se toca**, Telegram ⚠️ |
| 5. Producción | Reemplaza `credicheck-produccion` en **:8002** | — |
| 6. Verificación | `GET /health` en producción | **Rollback:** se vuelve a levantar la imagen estable anterior, Telegram ⚠️ |
| 7. Éxito | Tag `credicheck-api:estable`, Telegram ✅ con el **lead time** (commit → producción) | — |

Si staging nunca responde, además se envía la alerta 🚨 *Servidor inaccesible*. Los mensajes usan el contrato
`deploy/notificador.py` de Juan Camilo (JC-11).

### Workflow `.github/workflows/cd.yml`

- Se dispara con `workflow_run` **solo si la CI terminó en verde sobre `main`** (el Quality Gate bloquea el CD) y
  despliega exactamente el commit que pasó la CI (`head_sha`).
- `workflow_dispatch` con la opción **"Simular HTTP 500 en staging"** para demostrar el rollback en la sustentación.
- Como el runner es efímero, primero reconstruye la versión anterior (`HEAD~1`) y la deja corriendo como
  producción: así el rollback siempre tiene una versión estable real a la que volver.
- `concurrency: cd-produccion` evita dos despliegues simultáneos; `permissions: contents: read` (mínimo privilegio);
  acciones fijadas por SHA.
- Sube el artefacto **`evidencias-cd`** con los logs de staging/producción, `docker ps` y el `/health` final.

### Demo local

```bash
python -m pip install -r deploy/requirements.txt
python deploy/deploy.py --version v1                  # ✅ v1 en producción (http://localhost:8002/health)
python deploy/deploy.py --version v2 --forzar-fallo   # ⚠️ rollback: staging da HTTP 500
curl http://localhost:8002/health                     # sigue respondiendo "version": "v1"
```

### Consumidor de eventos (SA-8)

```bash
python deploy/consumidor_eventos.py --una-vez   # procesa lo pendiente en la cola y termina
```

Semántica **al menos una vez**: el mensaje se borra solo si Telegram respondió; si no, SQS lo reintenta y tras
3 recepciones lo mueve a la DLQ. Un mensaje mal formado nunca tumba al consumidor.

## 7. Secretos (solo nombres)

Los valores reales viven en **GitHub → Settings → Secrets and variables → Actions**. Nunca en el repositorio
(`.env` está en `.gitignore`; `.env.example` solo trae los nombres).

| Secreto | Lo usa |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `cd.yml` → `deploy.py` / `consumidor_eventos.py` |
| `TELEGRAM_CHAT_ID` | `cd.yml` → `deploy.py` / `consumidor_eventos.py` |
| `SONAR_TOKEN` | `ci.yml` (Rafael) |

Las credenciales `test/test` de LocalStack no son secretos: LocalStack las acepta por diseño y no dan acceso a
ninguna cuenta real.

## 8. Evidencias

Guardar en [evidencias/saray/](evidencias/saray/):

- [ ] Salida de `infra-init` ejecutado dos veces (CREADO → YA EXISTE)
- [ ] Job `pruebas-integracion` en verde en GitHub Actions
- [ ] Run del CD exitoso + mensaje ✅ de Telegram con el lead time
- [ ] Run del CD con "Simular HTTP 500" + mensaje ⚠️ de rollback y `/health` de producción con la versión anterior
- [ ] Mensaje 📄 del consumidor de eventos
- [ ] Comparación de Locust antes/después del índice (junto con Rafael)
