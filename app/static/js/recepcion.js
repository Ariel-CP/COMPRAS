(() => {
  const form = document.getElementById("recepcion-form");
  if (!form) return;

  const page = document.querySelector(".recepcion-page");
  const cotasList = document.getElementById("cotas-list");
  const message = document.getElementById("recepcion-message");
  const rows = document.getElementById("recepcion-rows");
  const providerSearch = document.getElementById("proveedor-search");
  const providerSearchEntry = document.getElementById("proveedor-search-entry");
  const providerId = document.getElementById("proveedor-id");
  const providerSelected = document.getElementById("proveedor-selected");
  const providerSelectedCode = document.getElementById("proveedor-selected-code");
  const providerSelectedName = document.getElementById("proveedor-selected-name");
  const providerSuggestions = document.getElementById("proveedor-suggestions");
  const articleSearch = document.getElementById("articulo-search");
  const articleSearchEntry = document.getElementById("articulo-search-entry");
  const articleId = document.getElementById("articulo-id");
  const articleSelected = document.getElementById("articulo-selected");
  const articleSelectedCode = document.getElementById("articulo-selected-code");
  const articleSelectedName = document.getElementById("articulo-selected-name");
  const articleSuggestions = document.getElementById("articulo-suggestions");
  const writeEnabled = page?.dataset.canWrite === "true";
  let providerSearchTimer;
  let providerSearchController;
  let activeProviderOption = -1;
  let articleSearchTimer;
  let articleSearchController;
  let activeArticleOption = -1;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  function closeProviderSuggestions() {
    providerSuggestions.hidden = true;
    providerSearch.setAttribute("aria-expanded", "false");
    providerSearch.removeAttribute("aria-activedescendant");
    activeProviderOption = -1;
  }

  function showProviderStatus(text) {
    providerSuggestions.innerHTML = `<p class="proveedor-suggestion-status" role="status">${escapeHtml(text)}</p>`;
    providerSuggestions.hidden = false;
    providerSearch.setAttribute("aria-expanded", "true");
  }

  function chooseProvider(provider) {
    clearTimeout(providerSearchTimer);
    providerSearchController?.abort();
    providerId.value = String(provider.id);
    providerSearch.value = `${provider.codigo} · ${provider.nombre}`;
    providerSearch.setCustomValidity("");
    closeProviderSuggestions();
    providerSelectedCode.textContent = provider.codigo;
    providerSelectedName.textContent = provider.nombre;
    providerSelected.hidden = false;
    providerSearchEntry.hidden = true;
    document.getElementById("orden_compra").focus();
  }

  function clearProviderSelection() {
    providerId.value = "";
    providerSearch.value = "";
    providerSearch.disabled = false;
    providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
    providerSelected.hidden = true;
    providerSearchEntry.hidden = false;
    closeProviderSuggestions();
    providerSearch.focus();
  }

  function renderProviderSuggestions(providers) {
    activeProviderOption = -1;
    if (!providers.length) {
      showProviderStatus("No se encontraron proveedores activos.");
      return;
    }

    providerSuggestions.innerHTML = providers.map((provider, index) => `
      <button
        class="proveedor-suggestion"
        type="button"
        role="option"
        id="proveedor-option-${index}"
        aria-selected="false"
        data-provider-index="${index}"
      ><strong>${escapeHtml(provider.codigo)}</strong>${escapeHtml(provider.nombre)}</button>
    `).join("");
    providerSuggestions.hidden = false;
    providerSearch.setAttribute("aria-expanded", "true");
    providerSuggestions.querySelectorAll("[data-provider-index]").forEach((option) => {
      option.addEventListener("pointerdown", (event) => event.preventDefault());
      option.addEventListener("click", () => {
        chooseProvider(providers[Number(option.dataset.providerIndex)]);
      });
    });
  }

  async function searchProviders(query) {
    providerSearchController?.abort();
    providerSearchController = new AbortController();
    showProviderStatus("Buscando proveedores...");
    try {
      const params = new URLSearchParams({ q: query });
      const response = await fetch(`/api/recepcion/proveedores/buscar?${params}`, {
        signal: providerSearchController.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo buscar proveedores");
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
      const isActive = index === activeProviderOption;
      option.setAttribute("aria-selected", String(isActive));
      if (isActive) {
        providerSearch.setAttribute("aria-activedescendant", option.id);
        option.scrollIntoView({ block: "nearest" });
      }
    });
  }

  providerSearch.addEventListener("input", () => {
    providerId.value = "";
    providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
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
        const optionIndex = activeProviderOption < 0 ? 0 : activeProviderOption;
        options[optionIndex].click();
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

  document.getElementById("proveedor-change").addEventListener("click", clearProviderSelection);

  function closeArticleSuggestions() {
    articleSuggestions.hidden = true;
    articleSearch.setAttribute("aria-expanded", "false");
    articleSearch.removeAttribute("aria-activedescendant");
    activeArticleOption = -1;
  }

  function showArticleStatus(text) {
    articleSuggestions.innerHTML = `<p class="articulo-suggestion-status" role="status">${escapeHtml(text)}</p>`;
    articleSuggestions.hidden = false;
    articleSearch.setAttribute("aria-expanded", "true");
  }

  function chooseArticle(article) {
    clearTimeout(articleSearchTimer);
    articleSearchController?.abort();
    articleId.value = String(article.id);
    articleSearch.value = `${article.codigo} · ${article.nombre}`;
    articleSearch.setCustomValidity("");
    closeArticleSuggestions();
    articleSelectedCode.textContent = article.codigo;
    articleSelectedName.textContent = article.nombre;
    articleSelected.hidden = false;
    articleSearchEntry.hidden = true;
    const planoSuffix = String(article.codigo).match(/(\d{4})$/);
    if (planoSuffix) {
      document.getElementById("numero_plano").value = planoSuffix[1];
    }
    document.getElementById("numero_plano").focus();
  }

  function clearArticleSelection() {
    articleId.value = "";
    articleSearch.value = "";
    articleSearch.disabled = false;
    articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
    articleSelected.hidden = true;
    articleSearchEntry.hidden = false;
    closeArticleSuggestions();
    articleSearch.focus();
  }

  function renderArticleSuggestions(articles) {
    activeArticleOption = -1;
    if (!articles.length) {
      showArticleStatus("No se encontraron artículos activos.");
      return;
    }

    articleSuggestions.innerHTML = articles.map((article, index) => `
      <button
        class="articulo-suggestion"
        type="button"
        role="option"
        id="articulo-option-${index}"
        aria-selected="false"
        data-article-index="${index}"
      ><strong>${escapeHtml(article.codigo)}</strong>${escapeHtml(article.nombre)}</button>
    `).join("");
    articleSuggestions.hidden = false;
    articleSearch.setAttribute("aria-expanded", "true");
    articleSuggestions.querySelectorAll("[data-article-index]").forEach((option) => {
      option.addEventListener("pointerdown", (event) => event.preventDefault());
      option.addEventListener("click", () => {
        chooseArticle(articles[Number(option.dataset.articleIndex)]);
      });
    });
  }

  async function searchArticles(query) {
    articleSearchController?.abort();
    articleSearchController = new AbortController();
    showArticleStatus("Buscando artículos...");
    try {
      const params = new URLSearchParams({ q: query });
      const response = await fetch(`/api/recepcion/articulos/buscar?${params}`, {
        signal: articleSearchController.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo buscar artículos");
      renderArticleSuggestions(data);
    } catch (error) {
      if (error.name !== "AbortError") showArticleStatus(error.message);
    }
  }

  function setActiveArticleOption(nextIndex) {
    const options = [...articleSuggestions.querySelectorAll("[role='option']")];
    if (!options.length) return;
    activeArticleOption = (nextIndex + options.length) % options.length;
    options.forEach((option, index) => {
      const isActive = index === activeArticleOption;
      option.setAttribute("aria-selected", String(isActive));
      if (isActive) {
        articleSearch.setAttribute("aria-activedescendant", option.id);
        option.scrollIntoView({ block: "nearest" });
      }
    });
  }

  articleSearch.addEventListener("input", () => {
    articleId.value = "";
    articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
    articleSearchController?.abort();
    clearTimeout(articleSearchTimer);
    const query = articleSearch.value.trim();
    if (query.length < 2) {
      closeArticleSuggestions();
      return;
    }
    articleSearchTimer = setTimeout(() => searchArticles(query), 250);
  });

  articleSearch.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && !articleSuggestions.hidden) {
      event.preventDefault();
      setActiveArticleOption(activeArticleOption + 1);
    } else if (event.key === "ArrowUp" && !articleSuggestions.hidden) {
      event.preventDefault();
      setActiveArticleOption(activeArticleOption - 1);
    } else if (event.key === "Enter" && !articleSuggestions.hidden) {
      const options = articleSuggestions.querySelectorAll("[data-article-index]");
      if (options.length) {
        event.preventDefault();
        const optionIndex = activeArticleOption < 0 ? 0 : activeArticleOption;
        options[optionIndex].click();
      }
    } else if (event.key === "Escape") {
      closeArticleSuggestions();
    }
  });

  articleSearch.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (!articleSuggestions.matches(":hover")) closeArticleSuggestions();
    }, 160);
  });

  document.getElementById("articulo-change").addEventListener("click", clearArticleSelection);

  function addCota(values = {}) {
    const row = document.createElement("div");
    row.className = "cota-row";
    row.innerHTML = `
      <label>Cota / criterio<input data-field="criterio_nombre" maxlength="255" value="${escapeHtml(values.criterio_nombre)}" required></label>
      <label>Especificación<input data-field="especificacion" maxlength="255" value="${escapeHtml(values.especificacion)}"></label>
      <label>Control<input data-field="valor_medido" maxlength="255" value="${escapeHtml(values.valor_medido)}"></label>
      <label>Desviación<input data-field="desviacion" value="${escapeHtml(values.desviacion)}"></label>
      <label>Resultado<select data-field="resultado"><option value="PENDIENTE">Pendiente</option><option value="OK">Aceptado</option><option value="NO_CONFORME">No conforme</option><option value="NO_APLICA">No aplica</option></select></label>
      <button class="cota-remove" type="button" aria-label="Quitar cota" title="Quitar cota">×</button>`;
    row.querySelector('[data-field="resultado"]').value = values.resultado || "PENDIENTE";
    row.querySelector(".cota-remove").addEventListener("click", () => row.remove());
    cotasList.append(row);
  }

  async function loadRecepciones() {
    const query = document.getElementById("recepcion-query").value.trim();
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    rows.innerHTML = '<tr><td colspan="4">Cargando...</td></tr>';
    try {
      const response = await fetch(`/api/recepcion/operativas?${params}`);
      if (!response.ok) throw new Error((await response.json()).detail || "No se pudo cargar el listado");
      const recepciones = await response.json();
      rows.innerHTML = recepciones.length ? recepciones.map((item) => `
        <tr><td><button class="recepcion-open" type="button" data-recepcion-id="${Number(item.id)}">${escapeHtml(item.numero_recepcion)}</button><br>${escapeHtml(item.fecha_recepcion || "")}</td>
        <td>${escapeHtml(item.proveedor_nombre)}</td>
        <td>${escapeHtml(item.orden_compra || "")}${item.remito ? `<br>Rto. ${escapeHtml(item.remito)}` : ""}</td>
        <td><span class="state-pill">${escapeHtml(item.estado)}</span></td></tr>`).join("") : '<tr><td colspan="4">Sin recepciones registradas</td></tr>';
    } catch (error) {
      rows.innerHTML = `<tr><td colspan="4">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  async function loadDetail(recepcionId) {
    const detail = document.getElementById("recepcion-detail");
    detail.innerHTML = '<p class="recepcion-detail-empty">Cargando detalle...</p>';
    try {
      const response = await fetch(`/api/recepcion/operativas/${recepcionId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el detalle");
      const header = `
        <h3>${escapeHtml(data.numero_recepcion)} · ${escapeHtml(data.estado)}</h3>
        <div class="recepcion-detail-grid">
          <div><strong>Proveedor</strong>${escapeHtml(data.proveedor_codigo)} · ${escapeHtml(data.proveedor_nombre)}</div>
          <div><strong>OC / Remito</strong>${escapeHtml(data.orden_compra)} · ${escapeHtml(data.remito || "Sin remito")}</div>
          <div><strong>Recepción / Control</strong>${escapeHtml(data.fecha_recepcion)} · ${escapeHtml(data.fecha_control)}</div>
          <div><strong>Checklist</strong>Terminación ${escapeHtml(data.terminacion_superficial ?? "-")}% · Dimensional ${escapeHtml(data.control_dimensional ?? "-")}% · Embalaje ${escapeHtml(data.embalaje ?? "-")}%</div>
          <div><strong>Observaciones</strong>${escapeHtml(data.notas || "Sin observaciones")}</div>
        </div>`;
      const lines = data.lineas.map((line) => `
        <div class="recepcion-detail-line">
          <h3>Línea ${Number(line.numero_linea)} · ${escapeHtml(line.producto_codigo)} · ${escapeHtml(line.designacion || line.producto_nombre)}</h3>
          <div class="recepcion-detail-grid">
            <div><strong>Plano / lote</strong>${escapeHtml(line.numero_plano || "-")} · ${escapeHtml(line.lote_numero || "-")}</div>
            <div><strong>Cantidades solicitada / recibida</strong>${escapeHtml(line.cantidad_solicitada)} / ${escapeHtml(line.cantidad_recibida)}</div>
            <div><strong>Inspección / muestra</strong>${escapeHtml(line.nivel_inspeccion || "-")} · ${escapeHtml(line.tamano_muestra ?? "-")} unidades (${escapeHtml(line.porcentaje_muestreo ?? "-")}%)</div>
            <div><strong>Material utilizado</strong>${escapeHtml(line.material_utilizado || "-")}</div>
          </div>
          <div class="recepcion-table-wrap"><table class="recepcion-detail-table"><thead><tr><th>Cota</th><th>Especificación</th><th>Control</th><th>Desviación</th><th>Resultado</th></tr></thead><tbody>
            ${line.cotas.length ? line.cotas.map((cota) => `<tr><td>${escapeHtml(cota.criterio_nombre)}</td><td>${escapeHtml(cota.especificacion || "-")}</td><td>${escapeHtml(cota.valor_medido || "-")}</td><td>${escapeHtml(cota.desviacion || "-")}</td><td>${escapeHtml(cota.resultado)}</td></tr>`).join("") : '<tr><td colspan="5">Sin cotas registradas</td></tr>'}
          </tbody></table></div>
        </div>`).join("");
      detail.innerHTML = header + (lines || '<p class="recepcion-detail-empty">La recepción no tiene líneas.</p>');
    } catch (error) {
      detail.innerHTML = `<p class="recepcion-detail-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  document.getElementById("cota-add").addEventListener("click", () => addCota());
  document.getElementById("recepcion-search").addEventListener("click", loadRecepciones);
  rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-recepcion-id]");
    if (button) loadDetail(Number(button.dataset.recepcionId));
  });
  document.getElementById("recepcion-query").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadRecepciones();
    }
  });
  document.getElementById("recepcion-reset").addEventListener("click", () => {
    form.reset();
    providerId.value = "";
    providerSelected.hidden = true;
    providerSearchEntry.hidden = false;
    providerSearch.disabled = false;
    providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
    closeProviderSuggestions();
    articleId.value = "";
    articleSelected.hidden = true;
    articleSearchEntry.hidden = false;
    articleSearch.disabled = false;
    articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
    closeArticleSuggestions();
    cotasList.replaceChildren();
    message.textContent = "";
    message.className = "recepcion-message";
  });

  if (!writeEnabled) {
    form.querySelectorAll("input, select, textarea, button").forEach((control) => {
      control.disabled = true;
    });
    document.getElementById("recepcion-reset").disabled = true;
  }

  providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
  articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!writeEnabled) return;
    message.textContent = "";
    message.className = "recepcion-message";
    const data = Object.fromEntries(new FormData(form).entries());
    for (const key of ["fecha_entrega_esperada", "nivel_inspeccion", "tamano_muestra", "porcentaje_muestreo", "material_utilizado", "numero_plano", "designacion", "lote_numero", "notas", "remito", "terminacion_superficial", "control_dimensional", "embalaje"]) {
      if (data[key] === "") data[key] = null;
    }
    for (const key of ["cantidad_solicitada", "cantidad_recibida", "cantidad_lote", "porcentaje_muestreo", "terminacion_superficial", "control_dimensional", "embalaje"]) {
      if (data[key] !== null && data[key] !== undefined) data[key] = Number(data[key]);
    }
    data.tamano_muestra = data.tamano_muestra ? Number(data.tamano_muestra) : null;
    data.cotas = [...cotasList.querySelectorAll(".cota-row")].map((row) => Object.fromEntries(
      [...row.querySelectorAll("[data-field]")].map((control) => [control.dataset.field, control.value || null]),
    ));
    try {
      const response = await fetch("/api/recepcion/operativas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "No se pudo guardar la recepción");
      message.textContent = `Recepción ${result.numero_recepcion} guardada (${result.estado}).`;
      message.classList.add("success");
      form.reset();
      providerId.value = "";
      providerSelected.hidden = true;
      providerSearchEntry.hidden = false;
      providerSearch.disabled = false;
      providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
      closeProviderSuggestions();
      articleId.value = "";
      articleSelected.hidden = true;
      articleSearchEntry.hidden = false;
      articleSearch.disabled = false;
      articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
      closeArticleSuggestions();
      cotasList.replaceChildren();
      loadRecepciones();
    } catch (error) {
      message.textContent = error.message;
      message.classList.add("error");
    }
  });

  loadRecepciones();
})();