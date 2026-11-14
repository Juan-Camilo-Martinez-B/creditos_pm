// [JC] Cliente HTTP de CrediCheck. Esqueleto de la Fase 0: completar en JC-9.
async function obtenerSalud() {
  const respuesta = await fetch("/health");
  return { ok: respuesta.ok, datos: await respuesta.json() };
}
