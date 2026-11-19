"""Despliegue continuo de CrediCheck con smoke tests y rollback automático. [SA] (tareas SA-5 y SA-6)

Flujo (Blue/Green simplificado con dos contenedores):

    1. Infraestructura   LocalStack + IaC idempotente (docker compose)
    2. Construcción      imagen credicheck-api:<version>
    3. Staging           contenedor credicheck-staging en :8001 con la versión candidata
    4. Smoke tests       /health, /reglas, POST y GET de una evaluación real
         └─ si fallan →  ROLLBACK: se destruye staging, producción NO se toca, Telegram ⚠️, exit 1
    5. Producción        se reemplaza credicheck-produccion (:8002) por la candidata
    6. Verificación      /health en producción
         └─ si falla  →  ROLLBACK: se vuelve a levantar la imagen estable anterior, Telegram ⚠️, exit 1
    7. Éxito             tag credicheck-api:estable, Telegram ✅ con el lead time, exit 0

Uso (desde la raíz del repo):
    python deploy/deploy.py --version v1
    python deploy/deploy.py --version v2 --forzar-fallo     # demo del rollback (HTTP 500 en staging)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notificador  # noqa: E402  (contrato de Juan Camilo, JC-11)

RAIZ_REPO = Path(__file__).resolve().parents[1]
IMAGEN = "credicheck-api"
RED = "credicheck_red"
STAGING = {"nombre": "credicheck-staging", "puerto": int(os.getenv("PUERTO_STAGING", "8001")), "entorno": "staging"}
PRODUCCION = {"nombre": "credicheck-produccion", "puerto": int(os.getenv("PUERTO_PRODUCCION", "8002")),
              "entorno": "produccion"}
ENV_AWS = {
    "STORAGE_BACKEND": "s3",
    "AWS_ENDPOINT_URL": "http://localstack:4566",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
}
SOLICITUD_HUMO = {"solicitante": "Smoke test CD", "score": 700, "ingresos": 2000.0, "monto_solicitado": 10000.01}


class ServidorInaccesible(Exception):
    """El contenedor nunca respondió: no hay ni siquiera un código HTTP que evaluar."""


class FalloSmoke(Exception):
    """El servicio respondió, pero no como dice el contrato."""


# ---------------------------------------------------------------- Docker
class Docker:
    """Envoltorio mínimo de la CLI de Docker (se reemplaza por un doble en las pruebas)."""

    def ejecutar(self, *argumentos: str, verificar: bool = True) -> subprocess.CompletedProcess:
        print(f"   $ docker {' '.join(argumentos)}")
        return subprocess.run(["docker", *argumentos], cwd=RAIZ_REPO, capture_output=True, text=True,
                              check=verificar)

    def preparar_infraestructura(self) -> None:
        self.ejecutar("compose", "up", "-d", "--wait", "localstack")
        self.ejecutar("compose", "run", "--rm", "infra-init")

    def construir(self, etiqueta: str) -> None:
        self.ejecutar("build", "-t", etiqueta, "./backend")

    def levantar(self, entorno: dict, imagen: str, version: str, extra_env: dict = None) -> None:
        self.eliminar(entorno["nombre"])
        variables = {**ENV_AWS, "APP_ENV": entorno["entorno"], "APP_VERSION": version, **(extra_env or {})}
        argumentos = ["run", "-d", "--name", entorno["nombre"], "--network", RED,
                      "-p", f"{entorno['puerto']}:8000"]
        for clave, valor in variables.items():
            argumentos += ["-e", f"{clave}={valor}"]
        self.ejecutar(*argumentos, imagen)

    def eliminar(self, nombre: str) -> None:
        self.ejecutar("rm", "-f", nombre, verificar=False)

    def version_en_ejecucion(self, nombre: str):
        """Retorna (imagen, version) del contenedor si existe, o (None, None)."""
        resultado = self.ejecutar("inspect", nombre, verificar=False)
        if resultado.returncode != 0:
            return None, None
        datos = json.loads(resultado.stdout)[0]["Config"]
        variables = dict(v.split("=", 1) for v in datos.get("Env", []))
        return datos["Image"], variables.get("APP_VERSION")

    def etiquetar(self, origen: str, destino: str) -> None:
        self.ejecutar("tag", origen, destino)

    def guardar_logs(self, nombre: str, destino: Path) -> None:
        resultado = self.ejecutar("logs", nombre, verificar=False)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(resultado.stdout + resultado.stderr, encoding="utf-8")


# ---------------------------------------------------------------- Smoke tests
def esperar_salud(url_base: str, intentos: int = 30, pausa_s: float = 1.0, http=requests) -> requests.Response:
    """Espera a que el contenedor acepte conexiones. Un 500 SÍ es una respuesta (no se reintenta)."""
    ultimo_error = "sin respuesta"
    for _ in range(intentos):
        try:
            return http.get(f"{url_base}/health", timeout=3)
        except requests.RequestException as error:
            ultimo_error = type(error).__name__
            time.sleep(pausa_s)
    raise ServidorInaccesible(ultimo_error)


def smoke_tests(url_base: str, version: str, http=requests, **espera) -> list[str]:
    """Pruebas de humo del contrato mínimo. Retorna la lista de verificaciones superadas."""
    superadas = []

    salud = esperar_salud(url_base, http=http, **espera)
    if salud.status_code != 200:
        raise FalloSmoke(f"HTTP {salud.status_code} en /health")
    cuerpo = salud.json()
    if cuerpo.get("status") != "healthy" or cuerpo.get("version") != version:
        raise FalloSmoke(f"/health inesperado: {cuerpo}")
    superadas.append(f"GET /health 200 (versión {version})")

    reglas = http.get(f"{url_base}/api/v1/reglas", timeout=5)
    if reglas.status_code != 200:
        raise FalloSmoke(f"HTTP {reglas.status_code} en /api/v1/reglas")
    superadas.append("GET /api/v1/reglas 200")

    creada = http.post(f"{url_base}/api/v1/evaluaciones", json=SOLICITUD_HUMO, timeout=10)
    if creada.status_code != 201:
        raise FalloSmoke(f"HTTP {creada.status_code} al crear una evaluación")
    evaluacion = creada.json()
    if evaluacion.get("decision") != "APROBADO_PARCIAL" or not str(evaluacion.get("comprobante", "")).startswith("s3://"):
        raise FalloSmoke(f"Evaluación inesperada: {evaluacion.get('decision')} / {evaluacion.get('comprobante')}")
    superadas.append("POST /api/v1/evaluaciones 201 (comprobante en S3)")

    consultada = http.get(f"{url_base}/api/v1/evaluaciones/{evaluacion['id']}", timeout=5)
    if consultada.status_code != 200 or consultada.json().get("id") != evaluacion["id"]:
        raise FalloSmoke(f"HTTP {consultada.status_code} al consultar la evaluación creada")
    superadas.append("GET /api/v1/evaluaciones/{id} 200")
    return superadas


# ---------------------------------------------------------------- Pipeline
@dataclass
class Resultado:
    exito: bool
    etapa: str
    motivo: str = ""
    version_estable: str = ""
    lead_time_s: float = 0.0
    verificaciones: list = field(default_factory=list)


def _url(entorno: dict) -> str:
    return f"http://localhost:{entorno['puerto']}"


def desplegar(version: str, commit: str, inicio: float, docker: Docker, forzar_fallo: bool = False,
              construir: bool = True, preparar_infra: bool = True, smoke=smoke_tests,
              notificar=notificador.notificar, reloj=time.time, dir_logs: Path = RAIZ_REPO / "deploy" / "logs",
              http=requests, **espera) -> Resultado:
    imagen = f"{IMAGEN}:{version}"
    imagen_anterior, version_anterior = docker.version_en_ejecucion(PRODUCCION["nombre"])
    version_estable = version_anterior or "ninguna (primer despliegue)"
    print(f"== CD CrediCheck · candidata {version} · producción actual: {version_estable}")

    def abortar(etapa: str, motivo: str, inaccesible_url: str = None) -> Resultado:
        print(f"!! ROLLBACK en {etapa}: {motivo}")
        if inaccesible_url:
            notificar(notificador.mensaje_servidor_inaccesible(inaccesible_url, motivo))
        notificar(notificador.mensaje_rollback(version, motivo, version_estable))
        return Resultado(False, etapa, motivo, version_estable)

    if preparar_infra:
        print("[1/6] Infraestructura (IaC idempotente)")
        docker.preparar_infraestructura()
    if construir:
        print(f"[2/6] Construyendo {imagen}")
        docker.construir(imagen)

    # ---- Staging
    print(f"[3/6] Staging en {_url(STAGING)}")
    extra = {"FORZAR_FALLO_SALUD": "true"} if forzar_fallo else None
    docker.levantar(STAGING, imagen, version, extra)
    print("[4/6] Smoke tests en staging")
    try:
        verificaciones = smoke(_url(STAGING), version, http=http, **espera)
    except ServidorInaccesible as error:
        docker.guardar_logs(STAGING["nombre"], dir_logs / f"staging-{version}.log")
        docker.eliminar(STAGING["nombre"])
        return abortar("staging", f"staging no respondió ({error})", f"{_url(STAGING)}/health")
    except (FalloSmoke, requests.RequestException, ValueError) as error:
        docker.guardar_logs(STAGING["nombre"], dir_logs / f"staging-{version}.log")
        docker.eliminar(STAGING["nombre"])
        return abortar("staging", f"{error} en staging")
    for verificacion in verificaciones:
        print(f"   OK {verificacion}")
    docker.eliminar(STAGING["nombre"])

    # ---- Producción
    print(f"[5/6] Promoviendo {version} a producción en {_url(PRODUCCION)}")
    docker.levantar(PRODUCCION, imagen, version)
    print("[6/6] Verificación en producción")
    try:
        salud = esperar_salud(_url(PRODUCCION), http=http, **espera)
        if salud.status_code != 200:
            raise FalloSmoke(f"HTTP {salud.status_code} en /health de producción")
    except (ServidorInaccesible, FalloSmoke, requests.RequestException) as error:
        docker.guardar_logs(PRODUCCION["nombre"], dir_logs / f"produccion-{version}.log")
        if imagen_anterior:
            print(f"   Restaurando {imagen_anterior} ({version_anterior})")
            docker.levantar(PRODUCCION, imagen_anterior, version_anterior)
        else:
            docker.eliminar(PRODUCCION["nombre"])
        return abortar("produccion", str(error))

    docker.etiquetar(imagen, f"{IMAGEN}:estable")
    lead_time = reloj() - inicio
    notificar(notificador.mensaje_despliegue_exitoso(version, commit, lead_time))
    print(f"== DESPLIEGUE EXITOSO · {version} en producción · lead time {lead_time:.1f} s")
    return Resultado(True, "produccion", version_estable=version, lead_time_s=lead_time, verificaciones=verificaciones)


def _git(*argumentos: str, defecto: str) -> str:
    try:
        return subprocess.run(["git", *argumentos], cwd=RAIZ_REPO, capture_output=True, text=True,
                              check=True).stdout.strip() or defecto
    except (OSError, subprocess.CalledProcessError):
        return defecto


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CD de CrediCheck con rollback automático")
    parser.add_argument("--version", default=os.getenv("VERSION") or _git("rev-parse", "--short", "HEAD", defecto="dev"))
    parser.add_argument("--commit", default=os.getenv("GITHUB_SHA", "")[:7] or _git("rev-parse", "--short", "HEAD", defecto="local"))
    parser.add_argument("--forzar-fallo", action="store_true", help="Simula HTTP 500 en staging (demo de rollback)")
    parser.add_argument("--sin-construir", action="store_true", help="Usa una imagen ya construida")
    parser.add_argument("--sin-infra", action="store_true", help="No levanta LocalStack ni ejecuta la IaC")
    args = parser.parse_args(argv)

    # Lead time = desde el commit hasta producción (métrica DORA); si no hay git, desde el inicio del CD.
    inicio = float(_git("log", "-1", "--format=%ct", defecto=str(time.time())))
    try:
        resultado = desplegar(args.version, args.commit, inicio, Docker(), forzar_fallo=args.forzar_fallo,
                              construir=not args.sin_construir, preparar_infra=not args.sin_infra)
    except subprocess.CalledProcessError as error:
        print(f"!! Docker falló: {' '.join(error.cmd)}\n{error.stderr}")
        notificador.notificar(notificador.mensaje_rollback(args.version, "error de Docker en el pipeline", "sin cambios"))
        return 1
    return 0 if resultado.exito else 1


if __name__ == "__main__":
    sys.exit(main())
