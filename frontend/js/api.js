// [JC] Cliente HTTP de CrediCheck. Usa rutas relativas: nginx reenvía /api y /health a la API.

class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje);
    this.estado = estado;
  }
}

function mensajeDeError(estado, datos) {
  if (estado === 422 && datos && Array.isArray(datos.detail)) {
    // Errores de validación de tipos (Pydantic): "campo: mensaje"
    return datos.detail
      .map((e) => `${(e.loc || []).filter((p) => p !== "body").join(".")}: ${e.msg}`)
      .join(" · ");
  }
  if (datos && typeof datos.detail === "string") return datos.detail;
  return `La API respondió con el estado ${estado}.`;
}

async function pedir(url, opciones = {}) {
  const inicio = performance.now();
  let respuesta;
  try {
    respuesta = await fetch(url, { headers: { Accept: "application/json" }, ...opciones });
  } catch {
    throw new ErrorApi("API no disponible. Verifique que el servicio esté en ejecución.", 0);
  }
  const milisegundos = performance.now() - inicio;
  let datos = null;
  try {
    datos = await respuesta.json();
  } catch {
    datos = null;
  }
  if (!respuesta.ok) throw new ErrorApi(mensajeDeError(respuesta.status, datos), respuesta.status);
  return { datos, milisegundos };
}

// /health responde 500 con cuerpo JSON cuando el servicio no está sano: no es una excepción.
async function obtenerSalud() {
  try {
    const respuesta = await fetch("/health", { cache: "no-store" });
    return { ok: respuesta.ok, datos: await respuesta.json() };
  } catch {
    return { ok: false, datos: null };
  }
}

const obtenerReglas = () => pedir("/api/v1/reglas");

const evaluar = (solicitud) =>
  pedir("/api/v1/evaluaciones", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(solicitud),
  });

const listarEvaluaciones = (limite = 20) =>
  pedir(`/api/v1/evaluaciones?limite=${encodeURIComponent(limite)}`);

const obtenerEvaluacion = (id) => pedir(`/api/v1/evaluaciones/${encodeURIComponent(id)}`);
