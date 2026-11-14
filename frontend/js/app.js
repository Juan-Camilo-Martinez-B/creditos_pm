// [JC] Lógica de la interfaz. Esqueleto de la Fase 0: completar en JC-9.
async function refrescarEstado() {
  const etiqueta = document.getElementById("estado");
  try {
    const { ok, datos } = await obtenerSalud();
    etiqueta.textContent = `${ok ? "En línea" : "Con fallas"} · v${datos.version} · ${datos.entorno}`;
    etiqueta.className = `estado ${ok ? "ok" : "error"}`;
  } catch {
    etiqueta.textContent = "API no disponible";
    etiqueta.className = "estado error";
  }
}

refrescarEstado();
setInterval(refrescarEstado, 15000);
