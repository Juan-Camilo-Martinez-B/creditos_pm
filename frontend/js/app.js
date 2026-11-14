// [JC] Lógica de la interfaz de CrediCheck.
// Los datos del usuario se pintan siempre con textContent (nunca innerHTML) para evitar XSS.

const $ = (id) => document.getElementById(id);

const moneda = new Intl.NumberFormat("es-CO", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
const fechaCorta = new Intl.DateTimeFormat("es-CO", { dateStyle: "short", timeStyle: "medium" });

const DECISIONES = {
  APROBADO: { clase: "aprobado", titulo: "Aprobado" },
  APROBADO_PARCIAL: { clase: "parcial", titulo: "Aprobado parcialmente" },
  RECHAZADO: { clase: "rechazado", titulo: "Rechazado" },
};

const CASOS_FRONTERA = [
  { etiqueta: "Score 599", datos: { score: 599, ingresos: 2500, monto_solicitado: 1000 } },
  { etiqueta: "Score 600", datos: { score: 600, ingresos: 2500, monto_solicitado: 1000 } },
  { etiqueta: "Ingresos 1999.99", datos: { score: 700, ingresos: 1999.99, monto_solicitado: 1000 } },
  { etiqueta: "Ingresos 2000", datos: { score: 700, ingresos: 2000, monto_solicitado: 1000 } },
  { etiqueta: "Monto 10000.00", datos: { score: 700, ingresos: 2000, monto_solicitado: 10000 } },
  { etiqueta: "Monto 10000.01", datos: { score: 700, ingresos: 2000, monto_solicitado: 10000.01 } },
  { etiqueta: "Score 851 (inválido)", datos: { score: 851, ingresos: 2500, monto_solicitado: 1000 } },
];

let reglas = null;
let historial = [];

// Crea un elemento con texto y atributos de forma segura.
function el(etiqueta, { clase, texto, atributos } = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  Object.entries(atributos || {}).forEach(([k, v]) => nodo.setAttribute(k, v));
  hijos.forEach((h) => nodo.append(h));
  return nodo;
}

function textoMotivo(motivo) {
  const r = reglas || { score: { aprobacion_minima: 600 }, ingresos_minimos: 2000 };
  return {
    CUMPLE_REQUISITOS: "Cumple todos los requisitos: se aprueba el monto solicitado.",
    MONTO_AJUSTADO: "El monto solicitado supera el máximo para este perfil: se aprueba hasta el monto máximo.",
    SCORE_INSUFICIENTE: `El score está por debajo de ${r.score.aprobacion_minima}.`,
    INGRESOS_INSUFICIENTES: `Los ingresos mensuales son menores a ${moneda.format(r.ingresos_minimos)}.`,
  }[motivo] || motivo;
}

// ---------------------------------------------------------------- Estado del servicio
async function refrescarEstado() {
  const { ok, datos } = await obtenerSalud();
  const contenedor = $("estado");
  if (datos) {
    $("estado-texto").textContent = `${ok ? "En línea" : "Con fallas"} · v${datos.version} · ${datos.entorno}`;
  } else {
    $("estado-texto").textContent = "API no disponible";
  }
  contenedor.className = `estado ${ok ? "ok" : "error"}`;
}

// ---------------------------------------------------------------- Reglas y bandas
function bandaDe(score) {
  if (!reglas) return null;
  if (score < reglas.score.aprobacion_minima) return { indice: 0, texto: "Banda de rechazo por score" };
  const i = reglas.multiplicadores.findIndex((m) => score >= m.desde && score <= m.hasta);
  if (i === -1) return null;
  const m = reglas.multiplicadores[i];
  return { indice: i + 1, texto: `Banda ${m.desde}–${m.hasta}: monto máximo = ${m.multiplicador} × ingresos` };
}

function pintarReglas() {
  const { score, multiplicadores, ingresos_minimos, monto } = reglas;
  const total = score.maximo - score.minimo + 1;
  const tramos = [
    { desde: score.minimo, hasta: score.aprobacion_minima - 1, clase: "rechazo", decision: "Rechazado", monto: "—" },
    ...multiplicadores.map((m, i) => ({
      desde: m.desde, hasta: m.hasta, clase: `banda-${i + 1}`, decision: "Aprobado", monto: `${m.multiplicador} × ingresos`,
    })),
  ];

  const barra = $("barra-bandas");
  barra.replaceChildren(
    ...tramos.map((t) => {
      const seg = el("div", { clase: `segmento ${t.clase}`, texto: `${t.desde}–${t.hasta}` });
      seg.style.flexBasis = `${((t.hasta - t.desde + 1) / total) * 100}%`;
      return seg;
    }),
    el("div", { clase: "marcador", atributos: { id: "marcador" } }),
  );

  $("tabla-reglas").replaceChildren(
    ...tramos.map((t, i) => {
      const fila = el("tr", { atributos: { "data-banda": String(i) } });
      fila.append(el("td", { texto: `${t.desde} – ${t.hasta}` }), el("td", { texto: t.decision }), el("td", { texto: t.monto }));
      return fila;
    }),
  );

  $("resumen-reglas").textContent =
    `Además: ingresos mínimos de ${moneda.format(ingresos_minimos)} y monto solicitado entre ` +
    `${moneda.format(monto.minimo)} y ${moneda.format(monto.maximo)}.`;

  ["score", "score-rango"].forEach((id) => {
    $(id).min = score.minimo;
    $(id).max = score.maximo;
  });
  $("monto").min = monto.minimo;
  $("monto").max = monto.maximo;
  resaltarBanda();
}

function resaltarBanda() {
  const score = Number($("score").value);
  const banda = bandaDe(score);
  $("banda-actual").textContent = banda ? banda.texto : "Score fuera del rango permitido.";
  document.querySelectorAll("#tabla-reglas tr").forEach((fila) => {
    fila.classList.toggle("activa", banda !== null && fila.dataset.banda === String(banda.indice));
  });
  const marcador = $("marcador");
  if (marcador && reglas) {
    const { minimo, maximo } = reglas.score;
    const limitado = Math.min(Math.max(score, minimo), maximo);
    marcador.style.left = `${((limitado - minimo + 0.5) / (maximo - minimo + 1)) * 100}%`;
  }
}

async function cargarReglas() {
  try {
    ({ datos: reglas } = await obtenerReglas());
    pintarReglas();
  } catch (error) {
    $("tabla-reglas").replaceChildren(el("tr", {}, el("td", { texto: error.message, atributos: { colspan: "3" } })));
  }
}

// ---------------------------------------------------------------- Resultado
function pintarResultado(e) {
  const info = DECISIONES[e.decision];
  const caja = $("resultado");
  caja.className = `resultado ${info.clase}`;
  const detalle = el("dl", { clase: "detalle" });
  const filas = [
    ["Solicitante", e.solicitante],
    ["Score", String(e.score)],
    ["Ingresos", moneda.format(e.ingresos)],
    ["Monto solicitado", moneda.format(e.monto_solicitado)],
    ["Monto máximo", moneda.format(e.monto_maximo)],
    ["Monto aprobado", moneda.format(e.monto_aprobado)],
    ["Fecha", fechaCorta.format(new Date(e.fecha))],
    ["Id", e.id, "mono"],
    ["Comprobante", e.comprobante, "mono"],
  ];
  filas.forEach(([dt, dd, clase]) => detalle.append(el("dt", { texto: dt }), el("dd", { texto: dd, clase })));
  caja.replaceChildren(
    el("p", { clase: "decision", texto: info.titulo }),
    el("p", { texto: textoMotivo(e.motivo) }),
    detalle,
  );
}

function pintarError(mensaje) {
  const caja = $("resultado");
  caja.className = "resultado error";
  caja.replaceChildren(el("p", { clase: "decision", texto: "No se pudo evaluar" }), el("p", { texto: mensaje }));
}

// ---------------------------------------------------------------- Formulario
function leerFormulario() {
  return {
    solicitante: $("solicitante").value.trim(),
    score: Number.parseInt($("score").value, 10),
    ingresos: Number.parseFloat($("ingresos").value),
    monto_solicitado: Number.parseFloat($("monto").value),
  };
}

async function enviarSolicitud(evento) {
  evento.preventDefault();
  const solicitud = leerFormulario();
  if ($("solicitante").value.trim().length < 3) {
    pintarError("El nombre del solicitante debe tener al menos 3 caracteres.");
    $("solicitante").focus();
    return;
  }
  const boton = $("boton-evaluar");
  boton.disabled = true;
  boton.textContent = "Evaluando…";
  try {
    const { datos } = await evaluar(solicitud);
    pintarResultado(datos);
    await cargarHistorial();
  } catch (error) {
    pintarError(error.message);
  } finally {
    boton.disabled = false;
    boton.textContent = "Evaluar solicitud";
  }
}

function sincronizarScore(origen) {
  const valor = origen.value;
  if (origen.id === "score-rango") $("score").value = valor;
  else if (valor !== "") $("score-rango").value = valor;
  resaltarBanda();
}

function pintarCasosFrontera() {
  $("casos-frontera").replaceChildren(
    ...CASOS_FRONTERA.map((caso) => {
      const chip = el("button", { clase: "chip", texto: caso.etiqueta, atributos: { type: "button" } });
      chip.addEventListener("click", () => {
        if ($("solicitante").value.trim().length < 3) $("solicitante").value = "Cliente de prueba";
        $("score").value = caso.datos.score;
        $("score-rango").value = caso.datos.score;
        $("ingresos").value = caso.datos.ingresos;
        $("monto").value = caso.datos.monto_solicitado;
        resaltarBanda();
        $("formulario").requestSubmit();
      });
      return chip;
    }),
  );
}

// ---------------------------------------------------------------- Historial
function pintarHistorial() {
  const filtro = $("filtro").value;
  const visibles = historial.filter((e) => !filtro || e.decision === filtro);
  const cuerpo = $("tabla-historial");
  if (visibles.length === 0) {
    cuerpo.replaceChildren(el("tr", {}, el("td", { texto: "Sin evaluaciones para mostrar.", atributos: { colspan: "5" } })));
    return;
  }
  cuerpo.replaceChildren(
    ...visibles.map((e) => {
      const fila = el("tr", { atributos: { "data-id": e.id, tabindex: "0", title: "Ver detalle" } });
      fila.append(
        el("td", { texto: fechaCorta.format(new Date(e.fecha)) }),
        el("td", { texto: e.solicitante }),
        el("td", { texto: String(e.score) }),
        el("td", {}, el("span", { clase: `etiqueta ${e.decision}`, texto: DECISIONES[e.decision].titulo })),
        el("td", { texto: moneda.format(e.monto_aprobado) }),
      );
      const abrir = () => verDetalle(e.id);
      fila.addEventListener("click", abrir);
      fila.addEventListener("keydown", (ev) => ev.key === "Enter" && abrir());
      return fila;
    }),
  );
}

async function cargarHistorial() {
  try {
    const { datos, milisegundos } = await listarEvaluaciones(20);
    historial = datos;
    $("tiempo-historial").textContent =
      `Últimas ${datos.length} evaluaciones · tiempo de respuesta: ${milisegundos.toFixed(0)} ms`;
    pintarHistorial();
  } catch (error) {
    $("tiempo-historial").textContent = error.message;
  }
}

async function verDetalle(id) {
  try {
    const { datos } = await obtenerEvaluacion(id);
    pintarResultado(datos);
    $("resultado").scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    pintarError(error.message);
  }
}

// ---------------------------------------------------------------- Inicio
function iniciar() {
  $("formulario").addEventListener("submit", enviarSolicitud);
  $("score").addEventListener("input", (e) => sincronizarScore(e.target));
  $("score-rango").addEventListener("input", (e) => sincronizarScore(e.target));
  $("filtro").addEventListener("change", pintarHistorial);
  $("boton-actualizar").addEventListener("click", cargarHistorial);
  pintarCasosFrontera();
  refrescarEstado();
  setInterval(refrescarEstado, 15000);
  cargarReglas();
  cargarHistorial();
}

iniciar();
