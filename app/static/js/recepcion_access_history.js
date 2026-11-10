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
  const table = rowsElement.closest("table");
  const headerRow = table.tHead.rows[0];
  const headers = Array.from(headerRow.cells);
  const defaults = [150, 125, 100, 190, 160, 300, 280, 150, 150, 130];
  const storageKey = "recepcion-access-columns-v1";
  let order = headers.map((_, index) => index);
  let widths = [...defaults];
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (saved && Array.isArray(saved.order) && saved.order.length === 9 &&
        new Set(saved.order).size === 9 &&
        saved.order.every((index) => Number.isInteger(index) && index >= 0 && index < 9)) {
      saved.order = saved.order.map((index) => index >= 6 ? index + 1 : index);
      saved.order.splice(saved.order.indexOf(5) + 1, 0, 6);
      if (Array.isArray(saved.widths) && saved.widths.length === 9) {
        saved.widths.splice(6, 0, defaults[6]);
      }
    }
    if (saved && Array.isArray(saved.order) && saved.order.length === headers.length &&
        new Set(saved.order).size === headers.length &&
        saved.order.every((index) => Number.isInteger(index) && index >= 0 && index < headers.length)) {
      order = saved.order;
    }
    if (saved && Array.isArray(saved.widths) && saved.widths.length === headers.length) {
      widths = saved.widths.map((width, index) => Number.isFinite(width) ? Math.max(80, Math.min(1200, width)) : defaults[index]);
    }
  } catch { /* La tabla funciona aunque el almacenamiento no este disponible. */ }
  const colgroup = document.createElement("colgroup");
  const columns = headers.map(() => document.createElement("col"));
  table.prepend(colgroup);
  function saveColumns() {
    try { localStorage.setItem(storageKey, JSON.stringify({ order, widths })); } catch { /* Preferencias opcionales. */ }
  }
  function applyColumns() {
    order.forEach((index) => {
      columns[index].style.width = `${widths[index]}px`;
      colgroup.append(columns[index]);
      headerRow.append(headers[index]);
    });
    table.style.width = `${widths.reduce((sum, width) => sum + width, 0)}px`;
    for (const row of rowsElement.rows) {
      if (row.cells.length !== headers.length) continue;
      const cells = Array.from(row.cells);
      cells.forEach((cell, index) => { cell.dataset.column ??= String(index); });
      const byColumn = new Map(cells.map((cell) => [Number(cell.dataset.column), cell]));
      order.forEach((index) => row.append(byColumn.get(index)));
    }
  }
  function moveColumn(source, target) {
    if (source === target) return;
    const targetPosition = order.indexOf(target);
    order.splice(order.indexOf(source), 1);
    order.splice(targetPosition, 0, source);
    applyColumns();
    saveColumns();
  }
  let draggedColumn = null;
  headers.forEach((header, index) => {
    header.draggable = true;
    header.tabIndex = 0;
    header.scope = "col";
    header.title = "Arrastrar para mover. Alt + flechas para mover con teclado.";
    header.addEventListener("dragstart", (event) => {
      draggedColumn = index;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", String(index));
    });
    header.addEventListener("dragover", (event) => {
      if (draggedColumn === null) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    });
    header.addEventListener("drop", (event) => {
      event.preventDefault();
      if (draggedColumn !== null) moveColumn(draggedColumn, index);
      draggedColumn = null;
    });
    header.addEventListener("dragend", () => { draggedColumn = null; });
    header.addEventListener("keydown", (event) => {
      if (event.target !== header || !event.altKey || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const target = order[order.indexOf(index) + (event.key === "ArrowLeft" ? -1 : 1)];
      if (target === undefined) return;
      event.preventDefault();
      moveColumn(index, target);
      header.focus();
    });
    const handle = document.createElement("span");
    handle.className = "access-history-resize";
    handle.tabIndex = 0;
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-orientation", "vertical");
    handle.setAttribute("aria-label", `Ancho de ${header.textContent.trim()}`);
    handle.title = "Arrastrar para ajustar ancho. Flechas para ajustar con teclado.";
    handle.addEventListener("dragstart", (event) => { event.preventDefault(); event.stopPropagation(); });
    handle.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      event.stopPropagation();
      widths[index] = Math.max(80, Math.min(1200, widths[index] + (event.key === "ArrowLeft" ? -10 : 10)));
      applyColumns();
      saveColumns();
    });
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      header.draggable = false;
      const startX = event.clientX;
      const startWidth = widths[index];
      handle.setPointerCapture(event.pointerId);
      const resize = (move) => {
        widths[index] = Math.max(80, Math.min(1200, startWidth + move.clientX - startX));
        applyColumns();
      };
      const finish = () => {
        handle.removeEventListener("pointermove", resize);
        handle.removeEventListener("pointerup", finish);
        handle.removeEventListener("pointercancel", finish);
        header.draggable = true;
        saveColumns();
      };
      handle.addEventListener("pointermove", resize);
      handle.addEventListener("pointerup", finish);
      handle.addEventListener("pointercancel", finish);
    });
    header.append(handle);
  });
  document.getElementById("access-history-reset-columns").addEventListener("click", () => {
    order = headers.map((_, index) => index);
    widths = [...defaults];
    applyColumns();
    saveColumns();
  });
  applyColumns();
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

  function displayPlano(value) {
    const numero = String(value ?? "").trim();
    return /^\d+$/.test(numero) ? numero.padStart(4, "0") : displayValue(value);
  }

  function displayDate(value) {
    const match = String(value ?? "").match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[T ])/);
    return match ? `${match[3]}/${match[2]}/${match[1]}` : displayValue(value);
  }

  function renderArticles(control) {
    const associations = control.articulo_asociaciones || [];
    if (!associations.length) return "Sin artículo asociado";
    return associations.map((item) => `<div><strong>${escapeHtml(displayValue(item.articulo_codigo))}</strong>${item.descripcion ? `<br><span class="hint">${escapeHtml(item.descripcion)}</span>` : ""}</div>`).join("");
  }

  function renderRow(control) {
    const id = Number(control.ID_INT);
    return `<tr>
      <td><button class="recepcion-open" type="button" data-access-id="${id}">${escapeHtml(displayValue(control.N_interno))}</button></td>
      <td>${escapeHtml(displayDate(control["Fecha Control"]))}</td>
      <td>${escapeHtml(displayPlano(control.PLANO))}</td>
      <td>${escapeHtml(displayValue(control.PROVEEDOR))}</td>
      <td>${escapeHtml(displayValue(control.Material))}</td>
      <td class="access-history-article-detail">${renderArticles(control)}</td>
      <td>${escapeHtml(control.articulo_nombre || "Sin nombre asociado")}</td>
      <td class="access-history-quantity">${escapeHtml(displayValue(control.Lote))}</td>
      <td><div class="access-history-order-remito"><span>OC: ${escapeHtml(displayValue(control["ORDEN DE COMPRA"]))}</span><span>Remito: ${escapeHtml(displayValue(control.Remito))}</span></div></td>
      <td><span class="state-pill">${escapeHtml(displayValue(control.Estado))}</span></td>
    </tr>`;
  }

  async function loadHistory(reset = true) {
    if (loading) return;
    loading = true;
    if (reset) {
      beforeId = null;
      rowsElement.innerHTML = '<tr><td colspan="10">Consultando Access...</td></tr>';
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
        rowsElement.innerHTML = '<tr><td colspan="10">No se encontraron controles.</td></tr>';
      } else {
        rowsElement.insertAdjacentHTML("beforeend", pageRows.map(renderRow).join(""));
      }
      applyColumns();
      if (pageRows.length) beforeId = pageRows[pageRows.length - 1].ID_INT;
      moreButton.hidden = !hasMore;
      countElement.textContent = `${rowsElement.querySelectorAll("[data-access-id]").length} controles cargados`;
      statusElement.textContent = "Historial Access · solo lectura";
    } catch (error) {
      statusElement.textContent = error.message;
      statusElement.classList.add("error");
      if (reset) rowsElement.innerHTML = `<tr><td colspan="10">${escapeHtml(error.message)}</td></tr>`;
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
        ["Plano", displayPlano(data.PLANO)], ["Código proveedor", data["Codigo Proveedor"]],
        ["Proveedor", data.PROVEEDOR], ["Material", data.Material],
        ["Código del artículo", data.articulo_codigo],
        ["Nombre del artículo", data.articulo_nombre],
        ["Descripción del artículo", (data.articulo_asociaciones || []).map((item) => item.descripcion).filter(Boolean).join("; ")],
        ["Orden de compra", data["ORDEN DE COMPRA"]], ["Remito", data.Remito],
        ["Fecha de entrega", data["Fecha de Entrega"]], ["Fecha de control", displayDate(data["Fecha Control"])],
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
