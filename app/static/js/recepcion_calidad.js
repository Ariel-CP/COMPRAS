(() => {
  const page = document.querySelector(".calidad-page");
  if (!page) return;

  const rows = document.getElementById("calidad-rows");
  const query = document.getElementById("calidad-query");
  const listStatus = document.getElementById("calidad-list-status");
  const canWrite = page.dataset.canWrite === "true";
  let pendingMaterials = [];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 204) return null;
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

  function renderRows() {
    if (!pendingMaterials.length) {
      rows.innerHTML = '<tr><td colspan="6">No hay materiales pendientes de control.</td></tr>';
      return;
    }
    rows.innerHTML = pendingMaterials.map((item) => {
      const muestra = item.tamano_muestra
        ? `${escapeHtml(item.nivel_inspeccion || "-")} · ${escapeHtml(item.letra_codigo_muestreo || "-")} · ${escapeHtml(item.tamano_muestra)}`
        : "Plan pendiente";
      const deleteButton = canWrite
        ? `<button class="calidad-delete" type="button" data-delete-reception="${Number(item.recepcion_id)}" data-reception-number="${escapeHtml(item.numero_recepcion)}">Eliminar</button>`
        : "";
      return `<tr>
        <td><a class="calidad-select" href="/ui/recepcion/calidad/linea/${Number(item.linea_id)}">${escapeHtml(item.numero_recepcion)}</a><br><span class="calidad-muted">${escapeHtml(formatDate(item.fecha_recepcion))}</span></td>
        <td>${escapeHtml(item.proveedor_codigo)}<br>${escapeHtml(item.proveedor_nombre)}</td>
        <td>${escapeHtml(item.producto_codigo)} · ${escapeHtml(item.designacion || item.producto_nombre)}<br><span class="calidad-muted">Plano ${escapeHtml(item.numero_plano || "-")} · Lote ${escapeHtml(item.lote_numero || "-")}</span></td>
        <td>${escapeHtml(item.orden_compra)}<br><span class="calidad-muted">${escapeHtml(item.remito || "Sin remito")}</span></td>
        <td>${muestra}<br><span class="calidad-muted">${escapeHtml(item.cantidad_recibida ?? item.cantidad_lote ?? "-")} ${escapeHtml(item.unidad_medida || "unid.")}</span></td>
        <td>${deleteButton}</td>
      </tr>`;
    }).join("");
  }

  async function loadPending() {
    listStatus.textContent = "Consultando ingresos pendientes...";
    listStatus.classList.remove("error");
    rows.innerHTML = '<tr><td colspan="6">Cargando...</td></tr>';
    const params = new URLSearchParams({ limit: "300" });
    if (query.value.trim()) params.set("q", query.value.trim());
    try {
      pendingMaterials = await requestJson(`/api/recepcion/operativas/lineas-pendientes?${params}`);
      renderRows();
      listStatus.textContent = `${pendingMaterials.length} material${pendingMaterials.length === 1 ? "" : "es"} pendiente${pendingMaterials.length === 1 ? "" : "s"}.`;
    } catch (error) {
      pendingMaterials = [];
      rows.innerHTML = `<tr><td colspan="6">${escapeHtml(error.message)}</td></tr>`;
      listStatus.textContent = error.message;
      listStatus.classList.add("error");
    }
  }

  async function deleteReception(button) {
    const receptionId = Number(button.dataset.deleteReception);
    const receptionNumber = button.dataset.receptionNumber || `#${receptionId}`;
    const confirmed = window.confirm(
      `¿Eliminar la recepción ${receptionNumber}?\n\nEsta acción no se puede deshacer. Solo se puede borrar si no tiene inspecciones ni no conformidades registradas.`,
    );
    if (!confirmed) return;
    button.disabled = true;
    listStatus.classList.remove("error");
    listStatus.textContent = `Eliminando recepción ${receptionNumber}...`;
    try {
      await requestJson(`/api/recepcion/operativas/${receptionId}`, { method: "DELETE" });
      listStatus.textContent = `Recepción ${receptionNumber} eliminada.`;
      await loadPending();
    } catch (error) {
      listStatus.textContent = error.message;
      listStatus.classList.add("error");
      button.disabled = false;
    }
  }

  rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-reception]");
    if (button) deleteReception(button);
  });
  document.getElementById("calidad-search-button").addEventListener("click", loadPending);
  query.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadPending();
    }
  });

  loadPending();
})();
