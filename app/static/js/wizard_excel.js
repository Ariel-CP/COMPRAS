(function (root) {
  "use strict";
  root.iniciarWizardExcel = function (api) {
    const el = (name) => document.getElementById(`excel-${name}`);
    const endpoint = "/api/plan-produccion-mensual/asistente-oc/archivo-integral";
    const labels = { Plan_PT: "Plan PT", Stock_MP: "Stock MP", Stock_PT: "Stock PT", Deuda_Clientes: "Deuda de clientes", LAF_Solicitado: "Pedidos LAF" };
    let preview = null;
    let busy = false;
    let revision = 0;
    el("periodo").value = api.periodo();
    function invalidate() {
      revision++;
      preview = null;
      el("importar").disabled = true;
      el("resumen").hidden = true;
      el("errores").hidden = true;
    }
    function lock(value) {
      busy = value;
      ["descargar", "validar", "archivo"].forEach((name) => { el(name).disabled = value; });
      el("importar").disabled = value || !preview || !api.puedeGuardar;
    }
    function line(target, message) {
      const p = document.createElement("p");
      p.textContent = message;
      target.appendChild(p);
    }
    el("archivo").addEventListener("change", () => { invalidate(); el("estado").textContent = "Archivo cambiado. Validalo antes de guardar."; });
    document.querySelectorAll(".wizard-body").forEach((pane) => {
      pane.addEventListener("input", invalidate);
      pane.addEventListener("change", invalidate);
    });
    document.addEventListener("wizard:datos-modificados", invalidate);
    el("descargar").addEventListener("click", async () => {
      if (busy) return;
      if (!el("periodo").value || !el("periodo").reportValidity()) return;
      const [year, month] = el("periodo").value.split("-").map(Number);
      lock(true);
      el("estado").textContent = "Preparando la plantilla con el catálogo y los datos guardados…";
      try {
        const response = await fetch(`${endpoint}/plantilla.xlsx?anio=${year}&mes=${month}`, { cache: "no-store" });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo descargar la plantilla.");
        }
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = `requerimiento_materiales_${year}_${String(month).padStart(2, "0")}.xlsx`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        el("estado").textContent = "Plantilla descargada. Completá todas las hojas y luego validá el archivo.";
      } catch (error) { el("estado").textContent = error.message; }
      finally { lock(false); }
    });
    el("validar").addEventListener("click", async () => {
      if (busy) return;
      invalidate();
      const file = el("archivo").files[0];
      if (!file) { el("estado").textContent = "Seleccioná la plantilla completada."; return; }
      if (file.size > 20 * 1024 * 1024) { el("estado").textContent = "El archivo supera 20 MB."; return; }
      const version = revision;
      lock(true);
      el("estado").textContent = "Validando todas las hojas, sin guardar datos…";
      try {
        const body = new FormData(); body.append("archivo", file);
        const response = await fetch(`${endpoint}/validar`, { method: "POST", body });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo validar el archivo.");
        if (version !== revision) { el("estado").textContent = "Cambiaron los datos. Volvé a validar."; return; }
        if (!data.valido) {
          el("errores").replaceChildren();
          data.errores.forEach((issue) => line(el("errores"), `${issue.hoja}, fila ${issue.fila}, ${issue.campo}: ${issue.mensaje}`));
          el("errores").hidden = false;
          el("estado").textContent = `${data.total_errores} error(es). Se muestran hasta 100. No se guardó ningún dato.`;
          return;
        }
        preview = { data, file };
        el("resumen").replaceChildren();
        line(el("resumen"), `Plan: ${data.mes}/${data.anio}. Stock MP: ${data.mes_stock}/${data.anio_stock}.`);
        Object.entries(data.filas).forEach(([name, count]) => line(el("resumen"), `${labels[name] || name}: ${count} fila(s) del archivo; ${data.existentes[name] || 0} registro(s) existentes.`));
        line(el("resumen"), "Se reemplaza la lista LAF completa del período, incluso si la confirmaste vacía. Las otras hojas actualizan los códigos listados. La confirmación vence en 30 minutos o si cambian los datos guardados.");
        el("resumen").hidden = false;
        el("estado").textContent = api.puedeGuardar ? "Archivo válido. Revisá el resumen y confirmá la carga." : "Archivo válido. Tu usuario no tiene los permisos necesarios para guardar.";
      } catch (error) { el("estado").textContent = error.message || "No se pudo validar el archivo."; }
      finally { lock(false); }
    });
    el("importar").addEventListener("click", async () => {
      if (busy || !preview || !api.puedeGuardar) return;
      const { data, file } = preview;
      if (!window.confirm(`¿Guardar los datos del plan ${data.mes}/${data.anio}, el stock MP ${data.mes_stock}/${data.anio_stock} y reemplazar la lista LAF de ese plan? Después se calcularán los materiales sin guardar sugerencias.`)) return;
      invalidate();
      lock(true);
      el("estado").textContent = "Guardando todas las hojas y calculando materiales…";
      let saved = false;
      try {
        const body = new FormData(); body.append("archivo", file); body.append("token", data.token); body.append("confirmar", "true");
        const response = await fetch(`${endpoint}/importar`, { method: "POST", body });
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "El servidor rechazó la carga. Validá nuevamente.");
        saved = true;
        await api.mostrar(result);
        el("estado").textContent = "Datos guardados y cálculo completo. Revisá los materiales y alertas en el paso 5.";
      } catch (error) {
        el("estado").textContent = saved ? "Los datos se guardaron y calcularon, pero no se pudo actualizar toda la pantalla. Recargá el Wizard para consultarlos." : `${error.message || "No se recibió la confirmación del servidor."} Revisá el período antes de reintentar.`;
      } finally { lock(false); }
    });
  };
})(window);
