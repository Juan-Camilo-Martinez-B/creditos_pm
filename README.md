# CrediCheck

Plataforma de evaluación de crédito con pruebas automatizadas, integración continua y despliegue continuo.
Proyecto final de **Pruebas y Mantenimiento de Software** (Universidad Cooperativa de Colombia, 7.º semestre).

Un analista registra una solicitud (score, ingresos y monto) y obtiene una decisión automática:
`APROBADO`, `APROBADO_PARCIAL` o `RECHAZADO`. Cada evaluación se guarda como comprobante en S3 y
publica un evento en SQS (emulados con LocalStack).

## Equipo y ramas

| Integrante | Rama | Responsabilidad | Documentación |
|---|---|---|---|
| Juan Camilo | `feature/backend-frontend` | Reglas de negocio, API, pruebas unitarias, frontend, notificaciones de Telegram | [docs/backend-frontend.md](docs/backend-frontend.md) |
| Rafael | `feature/calidad-ci` | Pruebas de contrato, CI, SonarCloud, Locust | [docs/calidad.md](docs/calidad.md) |
| Saray | `feature/infra-cd` | LocalStack (IaC), S3/SQS, CD con rollback | [docs/infra-cd.md](docs/infra-cd.md) |

**Regla de oro:** cada archivo tiene un único dueño (ver [.github/CODEOWNERS](.github/CODEOWNERS)).
Los archivos compartidos (`docker-compose.yml`, `backend/requirements.txt`, `backend/pytest.ini`,
`backend/.coveragerc`, `backend/app/config.py`, `backend/app/storage/base.py`, `backend/app/storage/__init__.py`)
están congelados: solo se cambian con una rama `chore/...` aprobada por los tres.

## Cómo ejecutar

Requisitos: Docker Desktop (con WSL 2 en Windows) y Python 3.11+.

```bash
# Todo el sistema: frontend http://localhost:8081 · API http://localhost:8000/docs
docker compose up -d --build

# Pruebas unitarias con Quality Gate de cobertura (>= 80 %)
cd backend
python -m pip install -r requirements.txt
python -m pytest

# Pruebas de contrato de la API dentro de contenedores (igual que en la CI).
# Se usa "run" y no "up --exit-code-from": este último apaga todo cuando infra-init termina.
docker compose --profile pruebas run --rm --build test-runner

# Pruebas de carga: interfaz de Locust en http://localhost:8089
docker compose --profile carga up -d --build

# Apagar y destruir todo (incluida la "nube" local)
docker compose down -v
```

## Flujo de trabajo con Git

```bash
git checkout -b feature/<tu-rama>          # una sola vez
git fetch origin && git merge origin/main  # todos los días y antes de cada PR
git add <solo tus archivos>
git commit -m "feat(api): ..."             # Conventional Commits
git push
```

Los Pull Requests a `main` se cierran con **"Create a merge commit"** (no squash) y sin borrar la rama.
Orden de merge en cada hito: Juan Camilo → Saray → Rafael.
