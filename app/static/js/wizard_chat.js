(function (root) {
  "use strict";
  root.iniciarWizardChat = function (api) {
    const el = (id) => document.getElementById(`wizard-chat-${id}`);
    const endpoint = "/api/plan-produccion-mensual/asistente-oc/ia/conversacion";
    const acciones = {
      excel_integral: "Ir a la plantilla Excel para cargar todos los listados juntos",
      periodo: "Cambiar el período del Wizard", cargar_plan: "Cargar el plan y sus ajustes",
      stock_mp: "Ir al stock de materias primas", laf: "Ir a los pedidos LAF",
      stock_pt: "Ir al stock de productos terminados", deuda: "Ir a la deuda de clientes",
      importar_mp: "Importar y guardar el archivo seleccionado de stock MP",
      importar_laf: "Importar y guardar el archivo seleccionado de pedidos LAF",
      importar_pt: "Importar y guardar el archivo seleccionado de stock PT",
      importar_deuda: "Importar y guardar el archivo seleccionado de deuda a clientes",
      simular: "Calcular los materiales sin guardar sugerencias", revisar: "Revisar el requerimiento de materiales",
    };
    let historial = [];
    let envio = null;
    let propuesta = null;
    let contextoPropuesta = "";
    let ocupado = false;
    let disponible = false;
    let revision = 0;
    let ultimaAccion = "ninguna";
    let ultimoResultado = "sin_accion";
    const datosContexto = () => ({ ...api.contexto(), accion_anterior: ultimaAccion, resultado_accion_anterior: ultimoResultado });
    const contexto = () => JSON.stringify(datosContexto());
    function invalidar() {
      envio = null;
      propuesta = null;
      el("preview").hidden = true;
      el("propuesta").hidden = true;
    }
    function mensaje(rol, texto) {
      const p = document.createElement("p");
      const b = document.createElement("strong");
      b.textContent = rol === "user" ? "Vos: " : "IA: ";
      p.appendChild(b);
      p.appendChild(document.createTextNode(texto));
      el("mensajes").appendChild(p);
      historial.push({ rol, texto });
    }
    function bloquear(valor) {
      ocupado = valor;
      ["enviar", "limpiar", "aplicar"].forEach((id) => { el(id).disabled = valor; });
      el("preparar").disabled = valor || !disponible;
    }
    document.querySelectorAll(".wizard-body").forEach((pane) => {
      const changed = () => { revision += 1; invalidar(); };
      pane.addEventListener("input", changed);
      pane.addEventListener("change", changed);
    });
    document.addEventListener("wizard:datos-modificados", () => { revision += 1; invalidar(); });
    el("pregunta").addEventListener("input", () => { envio = null; el("preview").hidden = true; });
    el("form").addEventListener("submit", (event) => {
      event.preventDefault();
      if (ocupado || !disponible) return;
      if (!el("pregunta").value.trim()) return;
      if (historial.length >= 30) {
        el("estado").textContent = "Iniciá una nueva conversación para continuar; los datos cargados en el Wizard se conservan.";
        return;
      }
      envio = { confirmar_envio: true, mensaje: el("pregunta").value.trim(), historial: historial.slice(), contexto: datosContexto() };
      el("envio").textContent = JSON.stringify({ mensaje: envio.mensaje, historial: envio.historial, contexto: envio.contexto }, null, 2);
      el("preview").hidden = false;
      el("propuesta").hidden = true;
    });
    el("cancelar").addEventListener("click", () => { envio = null; el("preview").hidden = true; });
    el("limpiar").addEventListener("click", () => {
      if (ocupado) return;
      historial = [];
      invalidar();
      el("mensajes").replaceChildren();
      el("pregunta").value = "";
      el("estado").textContent = "Nueva conversación. Los datos del Wizard se conservan.";
    });
    el("enviar").addEventListener("click", async () => {
      if (ocupado || !envio) return;
      if (JSON.stringify(envio.contexto) !== contexto()) {
        invalidar();
        el("estado").textContent = "Cambió el Wizard. Revisá nuevamente el mensaje antes de enviarlo.";
        return;
      }
      const payload = envio;
      const version = revision;
      invalidar();
      bloquear(true);
      el("estado").textContent = "Consultando al asistente…";
      try {
        const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo consultar al asistente.");
        mensaje("user", payload.mensaje);
        mensaje("assistant", data.mensaje);
        el("pregunta").value = "";
        if (version !== revision || JSON.stringify(payload.contexto) !== contexto()) {
          el("estado").textContent = "La respuesta corresponde al estado anterior del Wizard. Enviá una nueva consulta antes de aplicar acciones.";
          return;
        }
        if (acciones[data.accion]) {
          propuesta = data;
          contextoPropuesta = contexto();
          el("accion-texto").textContent = acciones[data.accion] + (data.accion === "periodo" ? `: ${data.anio}-${String(data.mes).padStart(2, "0")}` : "");
          el("propuesta").hidden = false;
        }
        el("estado").textContent = "Respuesta recibida. Las acciones todavía no se ejecutaron.";
      } catch (error) {
        el("estado").textContent = error.message || "No se pudo completar la consulta. No se reintentó.";
      } finally { bloquear(false); }
    });
    el("aplicar").addEventListener("click", async () => {
      if (ocupado || !propuesta) return;
      if (contextoPropuesta !== contexto()) {
        invalidar();
        el("estado").textContent = "Cambió el Wizard. Pedí una nueva propuesta.";
        return;
      }
      const accion = propuesta;
      invalidar();
      bloquear(true);
      try {
        const ok = await api.aplicar(accion);
        ultimaAccion = accion.accion;
        ultimoResultado = ok === false ? "fallida" : "completada";
        el("estado").textContent = ok === false ? "No se completó la acción. Revisá los mensajes del paso." : "Acción aplicada al Wizard. Revisá el resultado en el paso correspondiente antes de continuar.";
      } catch (_error) {
        ultimaAccion = accion.accion;
        ultimoResultado = "fallida";
        el("estado").textContent = "No se completó la acción. Revisá los mensajes del Wizard.";
      } finally { bloquear(false); }
    });
    fetch(`${endpoint}/estado`, { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error();
      const data = await response.json();
      disponible = data.disponible;
      el("disponibilidad").textContent = disponible ? `OpenAI · ${data.modelo}` : "Falta habilitar o configurar el asistente en Administración → IA y controles";
      bloquear(false);
    }).catch(() => { el("disponibilidad").textContent = "No se pudo comprobar la configuración del asistente."; });
  };
})(window);
