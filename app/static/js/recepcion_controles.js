(() => {
  const page = document.querySelector(".controles-page");
  if (!page) return;

  const rows = document.getElementById("controles-rows");
  const detail = document.getElementById("controles-detail");
  const status = document.getElementById("controles-status");
  const queryInput = document.getElementById("controles-query");
  const providerSearch = document.getElementById("controles-provider-search");
  const providerSearchEntry = document.getElementById("controles-provider-entry");
  const providerSuggestions = document.getElementById("controles-provider-suggestions");
  const providerSelected = document.getElementById("controles-provider-selected");
  const providerSelectedCode = document.getElementById("controles-provider-code");
  const providerSelectedName = document.getElementById("controles-provider-name");
  const canWrite = page.dataset.canWrite === "true";
  let selectedProviderCode = "";
  let providerSearchTimer;
  let providerSearchController;
  let activeProviderOption = -1;
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

  function dateText(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleDateString("es-AR");
  }

  async function loadControls() {
    status.textContent = "";
    status.classList.remove("error");
    rows.innerHTML = '<tr><td colspan="7">Cargando...</td></tr>';
    const params = new URLSearchParams({ limit: "100" });
    const query = queryInput.value.trim();
    if (query) params.set("q", query);
    if (selectedProviderCode) params.set("proveedor_codigo", selectedProviderCode);
    const results = await Promise.allSettled([
      requestJson(`/api/recepcion/operativas?${params}`),
      requestJson(`/api/recepcion/access/controles?${params}`),
    ]);
    const operativas = results[0].status === "fulfilled"
      ? results[0].value.map((item) => ({
        origen: "COMPRAS",
        id: Number(item.id),
        numero: item.numero_recepcion,
        fecha: item.fecha_control || item.fecha_recepcion,
        codigo: item.proveedor_codigo,
        proveedor: item.proveedor_nombre,
        oc: item.orden_compra,
        remito: item.remito,
        estado: item.estado,
        cantidad: item.cantidad_articulos != null ? Number(item.cantidad_articulos) : null,
        soloLectura: item.recepcion_staging_id != null,
      }))
      : [];
    const access = results[1].status === "fulfilled"
      ? results[1].value.map((item) => ({
        origen: "Access",
        id: Number(item.ID_INT),
        numero: item.N_interno == null
          ? "Inspección sin número"
          : `Inspección ${Number.isInteger(Number(item.N_interno)) ? Number(item.N_interno) : item.N_interno}`,
        fecha: item["Fecha Control"],
        codigo: item["Codigo Proveedor"],
        proveedor: item.PROVEEDOR,
        oc: item["ORDEN DE COMPRA"],
        remito: item.Remito,
        estado: item.Estado,
        cantidad: item.Lote != null && item.Lote !== "" && Number.isFinite(Number(item.Lote))
          ? Number(item.Lote)
          : null,
        soloLectura: true,
      }))
      : [];
    const controls = [...operativas, ...access].sort((a, b) =>
      (Date.parse(b.fecha || "") || 0) - (Date.parse(a.fecha || "") || 0) || b.id - a.id,
    );
    const failures = results.filter((result) => result.status === "rejected");
    if (!controls.length && !failures.length) {
      rows.innerHTML = '<tr><td colspan="7">No se encontraron controles.</td></tr>';
      return;
    }
    rows.innerHTML = controls.map((item, index) => {
      const rowId = `control-${item.origen}-${item.id}-${index}`;
      const actions = item.origen === "COMPRAS"
        ? `<div class="controles-row-actions">${canWrite && !item.soloLectura ? `<button type="button" data-edit="${item.id}">Editar</button><button class="danger" type="button" data-delete="${item.id}">Borrar</button>` : ""}<button type="button" data-print-label="${item.id}">Imprimir etiqueta</button></div>`
        : '<span class="controles-source">Solo lectura</span>';
      return `<tr id="${rowId}">
        <td><button class="controles-open" type="button" data-open="${item.origen}" data-id="${item.id}">${escapeHtml(item.numero)}</button><br>${escapeHtml(dateText(item.fecha))}</td>
        <td>${escapeHtml(item.codigo)}<br>${escapeHtml(item.proveedor)}</td>
        <td>${escapeHtml(item.oc)}${item.remito ? `<br>Rto. ${escapeHtml(item.remito)}` : ""}</td>
        <td>${item.cantidad != null ? escapeHtml(String(item.cantidad)) : "—"}</td><td>${escapeHtml(item.estado || "Sin estado")}</td><td>${item.origen}</td><td>${actions}</td>
      </tr>`;
    }).join("");
    if (failures.length) {
      status.textContent = `No se pudo cargar ${failures.length === 2 ? "ninguno de los orígenes" : failures[0] === results[0] ? "COMPRAS" : "Access"}.`;
      status.classList.add("error");
    }
  }

  function closeProviderSuggestions() {
    providerSuggestions.hidden = true;
    providerSearch.setAttribute("aria-expanded", "false");
    providerSearch.removeAttribute("aria-activedescendant");
    activeProviderOption = -1;
  }

  function showProviderStatus(text) {
    providerSuggestions.innerHTML = `<p class="controles-provider-status" role="status">${escapeHtml(text)}</p>`;
    providerSuggestions.hidden = false;
    providerSearch.setAttribute("aria-expanded", "true");
  }

  function chooseProvider(provider) {
    clearTimeout(providerSearchTimer);
    providerSearchController?.abort();
    selectedProviderCode = String(provider.codigo);
    providerSearch.value = `${provider.codigo} · ${provider.nombre}`;
    providerSearch.setCustomValidity("");
    providerSelectedCode.textContent = provider.codigo;
    providerSelectedName.textContent = provider.nombre;
    providerSearchEntry.hidden = true;
    providerSelected.hidden = false;
    closeProviderSuggestions();
    loadControls();
  }

  function clearProviderSelection() {
    selectedProviderCode = "";
    providerSearch.value = "";
    providerSearch.setCustomValidity("");
    providerSearchEntry.hidden = false;
    providerSelected.hidden = true;
    closeProviderSuggestions();
    loadControls();
    providerSearch.focus();
  }

  function renderProviderSuggestions(providers) {
    activeProviderOption = -1;
    if (!providers.length) {
      showProviderStatus("No se encontraron proveedores activos.");
      return;
    }
    providerSuggestions.innerHTML = providers.map((provider, index) => `
      <button class="controles-provider-suggestion" type="button" role="option"
        id="controles-provider-option-${index}" aria-selected="false"
        data-provider-index="${index}"><strong>${escapeHtml(provider.codigo)}</strong>${escapeHtml(provider.nombre)}</button>
    `).join("");
    providerSuggestions.hidden = false;
    providerSearch.setAttribute("aria-expanded", "true");
    providerSuggestions.querySelectorAll("[data-provider-index]").forEach((option) => {
      option.addEventListener("pointerdown", (event) => event.preventDefault());
      option.addEventListener("click", () => chooseProvider(providers[Number(option.dataset.providerIndex)]));
    });
  }

  async function searchProviders(query) {
    providerSearchController?.abort();
    providerSearchController = new AbortController();
    showProviderStatus("Buscando proveedores...");
    try {
      const params = new URLSearchParams({ q: query });
      const data = await requestJson(`/api/recepcion/proveedores/buscar?${params}`, {
        signal: providerSearchController.signal,
      });
      renderProviderSuggestions(data);
    } catch (error) {
      if (error.name !== "AbortError") showProviderStatus(error.message);
    }
  }

  function setActiveProviderOption(nextIndex) {
    const options = [...providerSuggestions.querySelectorAll("[role='option']")];
    if (!options.length) return;
    activeProviderOption = (nextIndex + options.length) % options.length;
    options.forEach((option, index) => {
      const active = index === activeProviderOption;
      option.setAttribute("aria-selected", String(active));
      if (active) {
        providerSearch.setAttribute("aria-activedescendant", option.id);
        option.scrollIntoView({ block: "nearest" });
      }
    });
  }

  providerSearch.addEventListener("input", () => {
    selectedProviderCode = "";
    providerSearchController?.abort();
    clearTimeout(providerSearchTimer);
    const query = providerSearch.value.trim();
    if (query.length < 2) {
      closeProviderSuggestions();
      return;
    }
    providerSearchTimer = setTimeout(() => searchProviders(query), 250);
  });

  providerSearch.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && !providerSuggestions.hidden) {
      event.preventDefault();
      setActiveProviderOption(activeProviderOption + 1);
    } else if (event.key === "ArrowUp" && !providerSuggestions.hidden) {
      event.preventDefault();
      setActiveProviderOption(activeProviderOption - 1);
    } else if (event.key === "Enter" && !providerSuggestions.hidden) {
      const options = providerSuggestions.querySelectorAll("[data-provider-index]");
      if (options.length) {
        event.preventDefault();
        options[activeProviderOption < 0 ? 0 : activeProviderOption].click();
      }
    } else if (event.key === "Escape") {
      closeProviderSuggestions();
    }
  });

  providerSearch.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (!providerSuggestions.matches(":hover")) closeProviderSuggestions();
    }, 160);
  });

  async function showDetail(origin, id) {
    detail.innerHTML = '<p class="controles-empty">Cargando detalle...</p>';
    try {
      if (origin === "Access") {
        const data = await requestJson(`/api/recepcion/access/controles/${id}`);
        const checks = data.controles || [];
        const numeroInspeccion = data.N_interno == null
          ? "Sin N_interno"
          : Number.isInteger(Number(data.N_interno))
            ? Number(data.N_interno)
            : data.N_interno;
        detail.innerHTML = `<h3>Inspección ${escapeHtml(numeroInspeccion)} · ${escapeHtml(data.Estado || "Sin estado")}</h3>
          <div class="controles-detail-grid">
            <div><strong>Proveedor</strong>${escapeHtml(data["Codigo Proveedor"])} · ${escapeHtml(data.PROVEEDOR)}</div>
            <div><strong>Plano / material</strong>${escapeHtml(data.PLANO ?? "-")} · ${escapeHtml(data.Material || "-")}</div>
            <div><strong>OC / remito</strong>${escapeHtml(data["ORDEN DE COMPRA"] || "-")} · ${escapeHtml(data.Remito || "-")}</div>
            <div><strong>Fecha de control</strong>${escapeHtml(dateText(data["Fecha Control"]) || "-")}</div>
            <div><strong>Plan / muestra</strong>${escapeHtml(data["PLAN MUESTREO"] || "-")} · ${escapeHtml(data.MUESTREO ?? "-")}</div>
            <div><strong>Resultado de control</strong>Dimensional ${escapeHtml(data["CONTROL DIMENSIONAL"] ?? "-")}% · Terminación ${escapeHtml(data["TERMINACION SUPERFICIAL"] ?? "-")}% · Embalaje ${escapeHtml(data.EMBALAJE ?? "-")}%</div>
            <div><strong>Recepcionó / controló</strong>${escapeHtml(data.Recibio || "-")} · ${escapeHtml(data.Controlo || "-")}</div>
            <div><strong>Observaciones</strong>${escapeHtml(data.NOTA || "-")}</div>
          </div>
          <table class="controles-detail-table"><thead><tr><th>Control</th><th>Cota</th><th>Desviación</th><th>Aceptado</th></tr></thead>
          <tbody>${checks.length ? checks.map((check) => `<tr><td>${escapeHtml(check.CONTROL)}</td><td>${escapeHtml(check.COTA)}</td><td>${escapeHtml(check.DESVIACION)}</td><td>${escapeHtml(check.ACEPTADO)}</td></tr>`).join("") : '<tr><td colspan="4">Sin controles CRD vinculados.</td></tr>'}</tbody></table>`;
        return;
      }

      const data = await requestJson(`/api/recepcion/operativas/${id}`);
      const lineDetails = data.lineas.map((line) => `<div class="controles-detail-line">
        <h3>Línea ${Number(line.numero_linea)} · ${escapeHtml(line.producto_codigo)} · ${escapeHtml(line.designacion || line.producto_nombre)}</h3>
        <div class="controles-detail-grid">
          <div><strong>Plano / lote</strong>${escapeHtml(line.numero_plano || "-")} · ${escapeHtml(line.lote_numero || "-")}</div>
          <div><strong>Cantidades solicitada / recibida</strong>${escapeHtml(line.cantidad_solicitada)} / ${escapeHtml(line.cantidad_recibida)}</div>
          <div><strong>Plan / muestra</strong>${escapeHtml(line.nivel_inspeccion || "-")} · ${escapeHtml(line.tamano_muestra ?? "-")}</div>
        </div></div>`).join("");
      detail.innerHTML = `<h3>${escapeHtml(data.numero_recepcion)} · ${escapeHtml(data.estado)}</h3>
        <div class="controles-detail-grid">
          <div><strong>Proveedor</strong>${escapeHtml(data.proveedor_codigo)} · ${escapeHtml(data.proveedor_nombre)}</div>
          <div><strong>OC / remito</strong>${escapeHtml(data.orden_compra)} · ${escapeHtml(data.remito || "-")}</div>
          <div><strong>Recepción / control</strong>${escapeHtml(dateText(data.fecha_recepcion))} · ${escapeHtml(dateText(data.fecha_control) || "Pendiente")}</div>
          <div><strong>Recibió / calidad</strong>${escapeHtml(data.usuario_recepcion_nombre || "-")} · ${escapeHtml(data.usuario_calidad_nombre || "-")}</div>
          <div><strong>Observaciones</strong>${escapeHtml(data.notas || "-")}</div>
        </div>${lineDetails}`;
    } catch (error) {
      detail.innerHTML = `<p class="controles-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  rows.addEventListener("click", async (event) => {
    const openButton = event.target.closest("[data-open]");
    if (openButton) {
      await showDetail(openButton.dataset.open, Number(openButton.dataset.id));
      return;
    }
    const printButton = event.target.closest("[data-print-label]");
    if (printButton) {
      const printWindow = window.open("", "_blank");
      if (!printWindow) {
        status.textContent = "El navegador bloqueó la ventana de impresión. Permití las ventanas emergentes para este sitio.";
        status.classList.add("error");
        return;
      }
      try {
        const data = await requestJson(`/api/recepcion/operativas/${Number(printButton.dataset.printLabel)}`);
        if (!window.printReceptionYellowLabel(data, printWindow)) printWindow.close();
      } catch (error) {
        printWindow.close();
        status.textContent = error.message;
        status.classList.add("error");
      }
      return;
    }
    const editButton = event.target.closest("[data-edit]");
    if (editButton) {
      window.location.href = `/ui/recepcion?editar=${Number(editButton.dataset.edit)}`;
      return;
    }
    const deleteButton = event.target.closest("[data-delete]");
    if (!deleteButton || !window.confirm("¿Borrar este control de COMPRAS? Esta acción no se puede deshacer.")) return;
    try {
      await requestJson(`/api/recepcion/operativas/${Number(deleteButton.dataset.delete)}`, { method: "DELETE" });
      status.textContent = "Control eliminado.";
      status.classList.remove("error");
      detail.innerHTML = '<p class="controles-empty">Seleccioná un control para ver su detalle.</p>';
      await loadControls();
    } catch (error) {
      status.textContent = error.message;
      status.classList.add("error");
    }
  });

  document.getElementById("controles-search").addEventListener("click", loadControls);
  document.getElementById("controles-provider-change").addEventListener("click", clearProviderSelection);
  queryInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadControls();
    }
  });
  loadControls();
})();