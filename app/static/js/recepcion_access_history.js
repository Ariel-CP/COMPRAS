(() => {
  const form = document.getElementById("access-history-form");
  if (!form) return;

  const queryInput = document.getElementById("access-history-query");
  const fromInput = document.getElementById("access-history-from");
  const toInput = document.getElementById("access-history-to");
  const rowsElement = document.getElementById("access-history-rows");
  const statusElement = document.getElementById("access-history-status");
  const countElement = document.getElementById("access-history-count");
  const moreButton = document.getElementById("access-history-more");
  const detailElement = document.getElementById("access-history-detail");
  let beforeId = null;
  let loading = false;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  function displayValue(value) {
    if (value === null || value === undefined || value === "") return "-";
    if (value === true) return "Sí";
    if (value === false) return "No";
    return String(value);
  }

  function renderRow(control) {
    const id = Number(control.ID_INT);
    return `<tr>
      <td><button class="recepcion-open" type="button" data-access-id="${id}">${escapeHtml(displayValue(control.ID_INT))} / ${escapeHtml(displayValue(control.N_interno))}</button></td>
      <td>${escapeHtml(displayValue(control["Fecha Control"]))}</td>
      <td>${escapeHtml(displayValue(control.PLANO))}</td>
      <td>${escapeHtml(displayValue(control.PROVEEDOR))}</td>
      <td>${escapeHtml(displayValue(control.Material))}</td>
      <td>${escapeHtml(displayValue(control["ORDEN DE COMPRA"]))}${control.Remito ? `<br>Rto. ${escapeHtml(control.Remito)}` : ""}</td>
      <td><span class="state-pill">${escapeHtml(displayValue(control.Estado))}</span></td>
    </tr>`;
  }

  async function loadHistory(reset = true) {
    if (loading) return;
    loading = true;
    if (reset) {
      beforeId = null;
      rowsElement.innerHTML = '<tr><td colspan="7">Consultando Access...</td></tr>';
      detailElement.hidden = true;
      countElement.textContent = "";
    }
    statusElement.className = "access-history-status";
    statusElement.textContent = "Consultando Access en modo solo lectura...";
    moreButton.disabled = true;

    try {
      const pageSize = 50;
      const params = new URLSearchParams({ limit: String(pageSize + 1) });
      const query = queryInput.value.trim();
      if (query) params.set("q", query);
      if (fromInput.value) params.set("desde", fromInput.value);
      if (toInput.value) params.set("hasta", toInput.value);
      if (!reset && beforeId !== null) params.set("before_id", String(beforeId));
      const response = await fetch(`/api/recepcion/access/controles?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo consultar Access");

      const pageRows = data.slice(0, pageSize);
      const hasMore = data.length > pageSize;
      if (reset) rowsElement.replaceChildren();
      if (!pageRows.length && reset) {
        rowsElement.innerHTML = '<tr><td colspan="7">No se encontraron controles.</td></tr>';
      } else {
        rowsElement.insertAdjacentHTML("beforeend", pageRows.map(renderRow).join(""));
      }
      if (pageRows.length) beforeId = pageRows[pageRows.length - 1].ID_INT;
      moreButton.hidden = !hasMore;
      countElement.textContent = `${rowsElement.querySelectorAll("[data-access-id]").length} controles cargados`;
      statusElement.textContent = "Historial Access · solo lectura";
    } catch (error) {
      statusElement.textContent = error.message;
      statusElement.classList.add("error");
      if (reset) rowsElement.innerHTML = `<tr><td colspan="7">${escapeHtml(error.message)}</td></tr>`;
    } finally {
      loading = false;
      moreButton.disabled = false;
    }
  }

  async function loadDetail(accessId) {
    detailElement.hidden = false;
    detailElement.innerHTML = '<p class="access-history-empty">Cargando datos y cotas desde Access...</p>';
    try {
      const response = await fetch(`/api/recepcion/access/controles/${Number(accessId)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el control");

      const fields = [
        ["ID Access", data.ID_INT], ["Número interno", data.N_interno],
        ["Plano", data.PLANO], ["Código proveedor", data["Codigo Proveedor"]],
        ["Proveedor", data.PROVEEDOR], ["Material", data.Material],
        ["Orden de compra", data["ORDEN DE COMPRA"]], ["Remito", data.Remito],
        ["Fecha de entrega", data["Fecha de Entrega"]], ["Fecha de control", data["Fecha Control"]],
        ["Lote", data.Lote], ["Recepcionó", data.Recibio], ["Controló", data.Controlo],
        ["Muestreo", data.MUESTREO], ["Porcentaje total", data["PORCENTAJE TOTAL"]],
        ["Control dimensional", data["CONTROL DIMENSIONAL"]],
        ["Terminación superficial", data["TERMINACION SUPERFICIAL"]],
        ["Embalaje", data.EMBALAJE], ["Plan de muestreo", data["PLAN MUESTREO"]],
        ["Estado histórico", data.Estado], ["Observaciones", data.NOTA],
      ];
      const cotas = data.controles || [];
      detailElement.innerHTML = `
        <h2>Control ${escapeHtml(data.ID_INT)} · ${escapeHtml(displayValue(data.Estado))}</h2>
        <div class="access-history-detail-grid">
          ${fields.map(([label, value]) => `<div><strong>${escapeHtml(label)}</strong>${escapeHtml(displayValue(value))}</div>`).join("")}
        </div>
        <h2 style="margin-top:18px">Cotas y mediciones (${cotas.length})</h2>
        <table class="access-history-cotas">
          <thead><tr><th>Control / criterio</th><th>Cota</th><th>Desviación</th><th>Aceptado</th></tr></thead>
          <tbody>${cotas.length ? cotas.map((item) => `<tr>
            <td>${escapeHtml(displayValue(item.CONTROL))}</td>
            <td>${escapeHtml(displayValue(item.COTA))}</td>
            <td>${escapeHtml(displayValue(item.DESVIACION))}</td>
            <td>${escapeHtml(displayValue(item.ACEPTADO))}</td>
          </tr>`).join("") : '<tr><td colspan="4">No hay cotas CRD vinculadas a este control.</td></tr>'}</tbody>
        </table>`;
    } catch (error) {
      detailElement.innerHTML = `<p class="access-history-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadHistory(true);
  });
  moreButton.addEventListener("click", () => loadHistory(false));
  rowsElement.addEventListener("click", (event) => {
    const button = event.target.closest("[data-access-id]");
    if (button) loadDetail(Number(button.dataset.accessId));
  });
  loadHistory();
})();
