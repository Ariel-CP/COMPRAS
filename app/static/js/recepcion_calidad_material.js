(() => {
  const page = document.querySelector(".calidad-page");
  if (!page) return;

  const lineaId = Number(page.dataset.lineId);
  const detail = document.getElementById("calidad-detail");
  const canWrite = page.dataset.canWrite === "true";
  const currentUser = page.dataset.currentUser || "Usuario actual";
  let selectedReception = null;
  let pendingItem = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const body = await response.text();
    let data = null;
    try {
      data = body ? JSON.parse(body) : null;
    } catch {
      throw new Error(`Respuesta no válida del servidor (HTTP ${response.status})`);
    }
    if (!response.ok) throw new Error(data?.detail || `Error HTTP ${response.status}`);
    return data;
  }

  function formatDate(value) {
    if (!value) return "-";
    const parsed = new Date(value);
    return Number.isNaN(parsed.valueOf()) ? String(value) : parsed.toLocaleDateString("es-AR");
  }

  function addCota(target, values = {}) {
    const row = document.createElement("div");
    row.className = "calidad-cota";
    row.innerHTML = `
      <label>Cota / criterio<input data-field="criterio_nombre" maxlength="255" value="${escapeHtml(values.criterio_nombre)}" required></label>
      <label>Especificación<input data-field="especificacion" maxlength="255" value="${escapeHtml(values.especificacion)}"></label>
      <label>Valor medido<input data-field="valor_medido" maxlength="255" value="${escapeHtml(values.valor_medido)}"></label>
      <label>Desviación<input data-field="desviacion" maxlength="500" value="${escapeHtml(values.desviacion)}"></label>
      <label>Resultado<select data-field="resultado"><option value="PENDIENTE">Pendiente</option><option value="OK">Conforme</option><option value="NO_CONFORME">No conforme</option><option value="NO_APLICA">No aplica</option></select></label>
      <button class="calidad-remove" type="button" aria-label="Quitar cota" title="Quitar cota">×</button>`;
    row.querySelector('[data-field="resultado"]').value = values.resultado || "PENDIENTE";
    row.querySelector(".calidad-remove").addEventListener("click", () => row.remove());
    target.append(row);
  }

  function cotasParaNuevoIntento(line, latest) {
    const cotasIniciales = (line.cotas || []).filter((cota) => cota.intento_id == null);
    const cotasPrevias = latest?.cotas || [];
    const cotas = cotasIniciales.length ? cotasIniciales : cotasPrevias;
    return cotas.map((cota) => ({
      criterio_nombre: cota.criterio_nombre || "",
      especificacion: cota.especificacion || "",
      valor_medido: "",
      desviacion: "",
      resultado: "PENDIENTE",
    }));
  }

  function renderAttemptHistory(attempts) {
    if (!attempts.length) return '<p class="calidad-muted">Sin intentos previos.</p>';
    return attempts.map((attempt) => {
      const cotas = (attempt.cotas || []).map((cota) => `
        <tr><td>${escapeHtml(cota.criterio_nombre)}</td><td>${escapeHtml(cota.especificacion || "-")}</td><td>${escapeHtml(cota.valor_medido || "-")}</td><td>${escapeHtml(cota.desviacion || "-")}</td><td>${escapeHtml(cota.resultado)}</td></tr>`).join("");
      return `<div class="calidad-attempt">
        <p><strong>Intento ${Number(attempt.numero_intento)} · ${escapeHtml(attempt.tipo_intento)}</strong> · ${escapeHtml(formatDate(attempt.fecha_inspeccion))} · ${escapeHtml(attempt.unidades_inspeccionadas)} inspeccionadas · ${escapeHtml(attempt.unidades_no_conformes)} no conformes · ${escapeHtml(attempt.decision)}</p>
        ${cotas ? `<table class="calidad-table"><thead><tr><th>Cota</th><th>Especificación</th><th>Medición</th><th>Desviación</th><th>Resultado</th></tr></thead><tbody>${cotas}</tbody></table>` : '<p class="calidad-muted">El intento no tiene cotas detalladas.</p>'}
      </div>`;
    }).join("");
  }

  async function loadMaterial() {
    if (!lineaId) {
      detail.innerHTML = '<p class="calidad-status error">Línea de recepción no válida.</p>';
      return;
    }
    detail.innerHTML = '<p class="calidad-muted">Cargando ficha e historial de inspección...</p>';
    try {
      // Localizar la línea dentro de las pendientes para obtener recepción y datos de muestreo
      const pendings = await requestJson("/api/recepcion/operativas/lineas-pendientes?limit=500");
      const item = pendings.find((material) => Number(material.linea_id) === lineaId);
      if (!item) {
        detail.innerHTML = '<p class="calidad-status error">El material ya no tiene controles pendientes o no existe.</p><p><a class="calidad-button secondary" href="/ui/recepcion/calidad">← Volver a pendientes</a></p>';
        return;
      }
      pendingItem = item;
      const reception = await requestJson(`/api/recepcion/operativas/${Number(item.recepcion_id)}`);
      const line = reception.lineas.find((entry) => Number(entry.id) === lineaId);
      if (!line) throw new Error("No se encontró la línea seleccionada en la recepción.");
      selectedReception = reception;
      renderDetail(item, reception, line);
    } catch (error) {
      detail.innerHTML = `<p class="calidad-status error">${escapeHtml(error.message)}</p>`;
    }
  }

  function renderDetail(item, reception, line) {
    const attempts = line.intentos_inspeccion || [];
    const latest = attempts.at(-1);
    const sample = item.tamano_muestra
      ? `${item.nivel_inspeccion} · letra ${item.letra_codigo_muestreo || "-"} · ${item.tamano_muestra} unidades (${item.porcentaje_muestreo ?? "-"} %)`
      : "Pendiente de asignación por falta de nivel o tamaño de lote tabulado";
    const plano = String(item.numero_plano || "").trim();
    const planoDisponible = /^\d{4}(?:-[A-Z])?$/i.test(plano);
    const planoLink = planoDisponible
      ? `<a class="calidad-button secondary" href="/api/recepcion/planos/${encodeURIComponent(plano)}/pdf" target="_blank" rel="noopener">Abrir plano PDF</a>`
      : '<span class="calidad-muted">Plano PDF no disponible</span>';
    const editReceptionLink = canWrite && reception.lineas.length === 1
      ? `<a class="calidad-button secondary" href="/ui/recepcion?editar=${Number(reception.id)}">Editar recepción</a>`
      : "";
    const nextAttempt = latest ? "REINSPECCION" : "INICIAL";
    detail.innerHTML = `
      <h2>${escapeHtml(item.producto_codigo)} · ${escapeHtml(item.designacion || item.producto_nombre)}</h2>
      ${editReceptionLink ? `<div class="calidad-toolbar">${editReceptionLink}</div>` : ""}
      <div class="calidad-summary">
        <div><strong>Recepción / fecha</strong>${escapeHtml(reception.numero_recepcion)} · ${escapeHtml(formatDate(reception.fecha_recepcion))}</div>
        <div><strong>Proveedor</strong>${escapeHtml(reception.proveedor_codigo)} · ${escapeHtml(reception.proveedor_nombre)}</div>
        <div><strong>OC / remito</strong>${escapeHtml(reception.orden_compra)} · ${escapeHtml(reception.remito || "-")}</div>
        <div><strong>Plano / identificador de lote</strong>${escapeHtml(plano || "-")} · ${escapeHtml(item.lote_numero || "-")}<br>${planoLink}</div>
        <div><strong>Solicitado / recibido</strong>${escapeHtml(item.cantidad_solicitada ?? "-")} / ${escapeHtml(item.cantidad_recibida ?? "-")} ${escapeHtml(item.unidad_medida || "")}</div>
        <div><strong>Embalaje / estado</strong>${escapeHtml(item.estado_embalaje || "-")} · ${escapeHtml(item.estado_inspeccion)}</div>
        <div><strong>Plan de muestra</strong>${escapeHtml(sample)}</div>
        <div><strong>Material utilizado</strong>${escapeHtml(item.material_utilizado || "-")}</div>
        <div><strong>Recepcionó</strong>${escapeHtml(reception.usuario_recepcion_nombre || "-")}</div>
      </div>
      <h3>Intentos anteriores</h3>
      ${renderAttemptHistory(attempts)}
      ${canWrite ? `
      <form class="calidad-form" id="control-linea-form" data-attempt-id="${latest ? Number(latest.id) : ""}" data-attempt-type="${nextAttempt}">
        <h3>${nextAttempt === "INICIAL" ? "Registrar inspección inicial" : "Registrar reinspección"}</h3>
        <div class="calidad-fields">
          <label>Inspector<input type="text" value="${escapeHtml(currentUser)}" readonly></label>
          <label>Tipo de intento<input type="text" value="${nextAttempt === "INICIAL" ? "Inicial" : "Reinspección"}" readonly></label>
          <label>Nivel aplicado<input type="text" value="${escapeHtml(item.nivel_inspeccion || "Pendiente")}" readonly></label>
          <label>Planificado (unidades)<input name="tamano_muestra_planificado" type="number" min="1" value="${item.tamano_muestra ? Number(item.tamano_muestra) : ""}" ${item.tamano_muestra ? "readonly" : ""}></label>
          <label>Unidades inspeccionadas<input name="unidades_inspeccionadas" type="number" min="1" ${item.tamano_muestra || item.cantidad_recibida ? `max="${escapeHtml(item.tamano_muestra || item.cantidad_recibida)}"` : ""} value="${item.tamano_muestra ? Number(item.tamano_muestra) : ""}" required></label>
          <label>Unidades no conformes<input name="unidades_no_conformes" type="number" min="0" value="${latest ? Number(latest.unidades_no_conformes) : 0}" required></label>
          <label>Decisión observada<select name="decision" required><option value="PENDIENTE">Pendiente</option><option value="ACEPTADO">Aceptado</option><option value="RECHAZADO">Rechazado</option></select></label>
          <label class="span-2">Referencia normativa<input name="referencia_normativa" maxlength="100" value="PG-4.10.01 v17"></label>
        </div>
        <p class="calidad-hint">La decisión se registra como observada. La aceptación Ac/Re automática requiere que Calidad defina el AQL aplicable.</p>
        <div class="calidad-cotas-head"><span>Cota / criterio</span><span>Especificación</span><span>Valor medido</span><span>Desviación</span><span>Resultado</span><span></span></div>
        <div id="calidad-cotas"></div>
        <div class="calidad-form-actions"><button class="calidad-button secondary" type="button" data-add-cota>Agregar cota</button><button class="calidad-button save" type="submit">Guardar inspección</button></div>
        <p class="calidad-status" data-form-status role="status" aria-live="polite"></p>
      </form>` : ""}`;
    const form = document.getElementById("control-linea-form");
    if (!form) return;
    form.querySelector('[name="decision"]').value = latest?.decision || "PENDIENTE";
    form.addEventListener("click", (event) => {
      if (event.target.closest("[data-add-cota]")) addCota(form.querySelector("#calidad-cotas"));
    });
    form.addEventListener("submit", submitInspection);
    cotasParaNuevoIntento(line, latest).forEach((cota) => {
      addCota(form.querySelector("#calidad-cotas"), cota);
    });
  }

  async function submitInspection(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const status = form.querySelector("[data-form-status]");
    const cotaRows = [...form.querySelectorAll(".calidad-cota")];
    if (!cotaRows.length) {
      status.textContent = "Agregá al menos una cota de control.";
      status.classList.add("error");
      return;
    }
    const formData = new FormData(form);
    const samplePlan = formData.get("tamano_muestra_planificado");
    const payload = {
      tipo_intento: form.dataset.attemptType,
      intento_anterior_id: form.dataset.attemptId ? Number(form.dataset.attemptId) : null,
      nivel_inspeccion: pendingItem?.nivel_inspeccion || null,
      tamano_muestra_planificado: samplePlan ? Number(samplePlan) : null,
      unidades_inspeccionadas: Number(formData.get("unidades_inspeccionadas")),
      unidades_no_conformes: Number(formData.get("unidades_no_conformes")),
      decision: formData.get("decision"),
      referencia_normativa: formData.get("referencia_normativa") || null,
      cotas: cotaRows.map((row) => Object.fromEntries(
        [...row.querySelectorAll("[data-field]")].map((control) => [control.dataset.field, control.value || null]),
      )),
    };
    const printWindow = payload.decision === "ACEPTADO" ? window.open("", "_blank") : null;
    status.textContent = "Guardando inspección...";
    status.classList.remove("error");
    try {
      const result = await requestJson(`/api/recepcion/operativas/lineas/${lineaId}/intentos-inspeccion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      status.textContent = `Intento ${result.numero_intento} guardado.`;
      if (payload.decision === "ACEPTADO" && printWindow) {
        if (!window.printReceptionAcceptedLabel(selectedReception, printWindow)) {
          printWindow.close();
          status.textContent += " No se pudo preparar la etiqueta verde.";
        }
      } else if (payload.decision === "ACEPTADO") {
        status.textContent += " El navegador bloqueó la ventana de impresión; habilitá las ventanas emergentes para este sitio.";
      }
      // Recargar la ficha: si sigue pendiente, se muestra el nuevo intento; si no, avisa.
      await loadMaterial();
    } catch (error) {
      printWindow?.close();
      status.textContent = error.message;
      status.classList.add("error");
    }
  }

  loadMaterial();
})();
