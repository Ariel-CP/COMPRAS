(() => {
  const form = document.getElementById("recepcion-form");
  if (!form) return;

  const page = document.querySelector(".recepcion-page");
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
  const articlePlanActions = document.getElementById("articulo-plan-actions");
  const articlePlanLink = document.getElementById("articulo-open-plan");
  const articlePlanNumber = document.getElementById("numero_plano");
  const articleSuggestions = document.getElementById("articulo-suggestions");
  const writeEnabled = page?.dataset.canWrite === "true";
  const currentUserName = page?.dataset.currentUserName || "Usuario actual";
  let providerSearchTimer;
  let providerSearchController;
  let activeProviderOption = -1;
  let articleSearchTimer;
  let articleSearchController;
  let activeArticleOption = -1;
  let planLookupGeneration = 0;
  let planLookupPending = false;
  let selectedProviderCode = "";
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
    selectedProviderCode = String(provider.codigo);
    loadRecepciones();
    document.getElementById("orden_compra").focus();
  }

  function clearProviderSelection() {
    selectedProviderCode = "";
    providerId.value = "";
    providerSearch.value = "";
    providerSearch.disabled = false;
    providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
    providerSelected.hidden = true;
    providerSearchEntry.hidden = false;
    closeProviderSuggestions();
    loadRecepciones();
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

  function updateArticlePlanLink() {
    const numeroPlano = articlePlanNumber.value.trim();
    const validNumber = /^\d{4}(?:-[A-Z])?$/i.test(numeroPlano);
    articlePlanActions.hidden = articleSelected.hidden;
    articlePlanLink.setAttribute("aria-disabled", String(!validNumber));
    if (validNumber) {
      articlePlanLink.textContent = "Abrir plano PDF";
      articlePlanLink.href = `/api/recepcion/planos/${encodeURIComponent(numeroPlano)}/pdf`;
    } else {
      articlePlanLink.removeAttribute("href");
    }
  }

  function clearArticlePlanLink() {
    planLookupGeneration += 1;
    planLookupPending = false;
    articlePlanActions.hidden = true;
    articlePlanLink.removeAttribute("href");
    articlePlanLink.setAttribute("aria-disabled", "true");
    articlePlanLink.textContent = "Abrir plano PDF";
  }

  async function loadLatestArticlePlan(article) {
    const match = String(article.codigo).match(/(?:^|\D)(\d{4})(?:-([A-Z]))?(?!\d)/i);
    articlePlanNumber.value = match?.[1] || "";
    planLookupPending = Boolean(match);
    articlePlanActions.hidden = false;
    articlePlanLink.removeAttribute("href");
    articlePlanLink.setAttribute("aria-disabled", "true");
    articlePlanLink.textContent = match ? "Buscando última revisión..." : "Número de plano no identificado";

    if (!match) return;

    const generation = ++planLookupGeneration;
    const numeroBase = match[1];
    try {
      const response = await fetch(
        `/api/recepcion/planos/${numeroBase}/ultima-version`,
        { cache: "no-store" },
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "No se encontró el plano");
      if (generation !== planLookupGeneration || articleId.value !== String(article.id)) return;
      planLookupPending = false;
      articlePlanNumber.value = result.numero_plano;
      updateArticlePlanLink();
    } catch {
      if (generation !== planLookupGeneration || articleId.value !== String(article.id)) return;
      planLookupPending = false;
      articlePlanNumber.value = numeroBase;
      articlePlanLink.textContent = "Plano PDF no encontrado";
    }
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
    loadLatestArticlePlan(article);
    articlePlanNumber.focus();
  }

  function clearArticleSelection() {
    articleId.value = "";
    articleSearch.value = "";
    articleSearch.disabled = false;
    articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
    articleSelected.hidden = true;
    clearArticlePlanLink();
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
  articlePlanNumber.addEventListener("input", () => {
    if (!articleSelected.hidden) {
      planLookupGeneration += 1;
      planLookupPending = false;
      updateArticlePlanLink();
    }
  });
  articlePlanLink.addEventListener("click", (event) => {
    if (articlePlanLink.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
    }
  });

  function addCota(targetList, values = {}) {
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
    targetList.append(row);
  }

  async function loadRecepciones() {
    const query = document.getElementById("recepcion-query").value.trim();
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    if (selectedProviderCode) params.set("proveedor_codigo", selectedProviderCode);
    rows.innerHTML = '<tr><td colspan="4">Cargando...</td></tr>';
    try {
      const response = await fetch(`/api/recepcion/operativas?${params}`);
      if (!response.ok) throw new Error((await response.json()).detail || "No se pudo cargar el listado");
      const recepciones = await response.json();
      rows.innerHTML = recepciones.length ? recepciones.map((item) => `
        <tr><td><button class="recepcion-open" type="button" data-access-id="${Number(item.ID_INT)}">${escapeHtml(item.ID_INT)}</button><br>${escapeHtml(item["Fecha Control"] || "")}</td>
        <td>${escapeHtml(item["Codigo Proveedor"] || "")}<br>${escapeHtml(item.PROVEEDOR || "")}</td>
        <td>${escapeHtml(item["ORDEN DE COMPRA"] || "")}${item.Remito ? `<br>Rto. ${escapeHtml(item.Remito)}` : ""}</td>
        <td><span class="state-pill">${escapeHtml(item.Estado || "Sin estado")}</span></td></tr>`).join("") : '<tr><td colspan="4">Sin recepciones encontradas en Access</td></tr>';
    } catch (error) {
      rows.innerHTML = `<tr><td colspan="4">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  async function loadAccessReceiptDetail(accessId) {
    const detail = document.getElementById("recepcion-detail");
    detail.innerHTML = '<p class="recepcion-detail-empty">Cargando detalle desde Access...</p>';
    try {
      const response = await fetch(`/api/recepcion/access/controles/${Number(accessId)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el control de Access");
      const checks = data.controles || [];
      detail.innerHTML = `
        <h3>Control Access ${escapeHtml(data.ID_INT)} · ${escapeHtml(data.Estado || "Sin estado")}</h3>
        <div class="recepcion-detail-grid">
          <div><strong>Proveedor</strong>${escapeHtml(data["Codigo Proveedor"] || "")} · ${escapeHtml(data.PROVEEDOR || "")}</div>
          <div><strong>Artículo / plano</strong>${escapeHtml(data.Material || "-")} · ${escapeHtml(data.PLANO ?? "-")}</div>
          <div><strong>OC / remito</strong>${escapeHtml(data["ORDEN DE COMPRA"] || "-")} · ${escapeHtml(data.Remito || "-")}</div>
          <div><strong>Fecha de control</strong>${escapeHtml(data["Fecha Control"] || "-")}</div>
          <div><strong>Recepcionó / controló</strong>${escapeHtml(data.Recibio || "-")} · ${escapeHtml(data.Controlo || "-")}</div>
          <div><strong>Observaciones</strong>${escapeHtml(data.NOTA || "-")}</div>
        </div>
        <div class="recepcion-table-wrap"><table class="recepcion-detail-table">
          <thead><tr><th>Control</th><th>Cota</th><th>Desviación</th><th>Aceptado</th></tr></thead>
          <tbody>${checks.length ? checks.map((check) => `<tr><td>${escapeHtml(check.CONTROL || "-")}</td><td>${escapeHtml(check.COTA || "-")}</td><td>${escapeHtml(check.DESVIACION || "-")}</td><td>${escapeHtml(check.ACEPTADO == null ? "-" : String(check.ACEPTADO))}</td></tr>`).join("") : '<tr><td colspan="4">Sin cotas CRD vinculadas</td></tr>'}</tbody>
        </table></div>`;
    } catch (error) {
      detail.innerHTML = `<p class="recepcion-detail-empty">${escapeHtml(error.message)}</p>`;
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
          <div><strong>Recepción / Control</strong>${escapeHtml(data.fecha_recepcion)} · ${escapeHtml(data.fecha_control || "Pendiente")}</div>
          <div><strong>Recibió</strong>${escapeHtml(data.usuario_recepcion_nombre || "No registrado")}</div>
          <div><strong>Control de calidad</strong>${escapeHtml(data.usuario_calidad_nombre || "Pendiente")}</div>
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
      const qualityPending = ["PENDIENTE", "EN_INSPECCIÓN"].includes(data.estado)
        && data.lineas.every((line) => !line.cotas.length);
      const qualityForm = writeEnabled && qualityPending ? `
        <form id="recepcion-calidad-form" data-recepcion-id="${Number(data.id)}" class="recepcion-quality-form">
          <h3>Registrar control de calidad</h3>
          <div class="recepcion-fields">
            <label>Realizó el control de calidad<input type="text" value="${escapeHtml(currentUserName)}" readonly></label>
            <label>Terminación superficial (%)<input name="terminacion_superficial" type="number" min="0" max="100" step="0.01"></label>
            <label>Control dimensional (%)<input name="control_dimensional" type="number" min="0" max="100" step="0.01"></label>
            <label>Embalaje (%)<input name="embalaje" type="number" min="0" max="100" step="0.01"></label>
          </div>
          <div class="cotas-head">
            <span>Cota / criterio</span><span>Especificación</span><span>Control</span><span>Desviación</span><span>Resultado</span><span></span>
          </div>
          <div id="calidad-cotas-list"></div>
          <div class="section-actions">
            <button class="recepcion-button secondary" type="button" data-quality-add>Agregar cota</button>
            <button class="recepcion-button save" type="submit">Guardar control de calidad</button>
          </div>
          <p class="recepcion-message" data-quality-message role="status" aria-live="polite"></p>
        </form>` : "";
      detail.innerHTML = header + (lines || '<p class="recepcion-detail-empty">La recepción no tiene líneas.</p>') + qualityForm;
    } catch (error) {
      detail.innerHTML = `<p class="recepcion-detail-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  document.getElementById("recepcion-search").addEventListener("click", loadRecepciones);
  rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-access-id]");
    if (button) loadAccessReceiptDetail(Number(button.dataset.accessId));
  });
  const detailContainer = document.getElementById("recepcion-detail");
  detailContainer.addEventListener("click", (event) => {
    if (event.target.closest("[data-quality-add]")) {
      addCota(document.getElementById("calidad-cotas-list"));
    }
  });
  detailContainer.addEventListener("submit", async (event) => {
    const qualityForm = event.target.closest("#recepcion-calidad-form");
    if (!qualityForm) return;
    event.preventDefault();
    const cotaRows = [...qualityForm.querySelectorAll(".cota-row")];
    if (!cotaRows.length) {
      qualityForm.querySelector("[data-quality-message]").textContent = "Agregá al menos una cota para registrar el control.";
      return;
    }
    const cotas = cotaRows.map((row) => Object.fromEntries(
      [...row.querySelectorAll("[data-field]")].map((control) => [control.dataset.field, control.value || null]),
    ));
    const qualityData = Object.fromEntries(new FormData(qualityForm).entries());
    for (const field of ["terminacion_superficial", "control_dimensional", "embalaje"]) {
      qualityData[field] = qualityData[field] === "" ? null : Number(qualityData[field]);
    }
    qualityData.cotas = cotas;
    const qualityMessage = qualityForm.querySelector("[data-quality-message]");
    try {
      const response = await fetch(`/api/recepcion/operativas/${Number(qualityForm.dataset.recepcionId)}/control-calidad`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(qualityData),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "No se pudo guardar el control de calidad");
      await loadDetail(Number(qualityForm.dataset.recepcionId));
      loadRecepciones();
    } catch (error) {
      qualityMessage.textContent = error.message;
      qualityMessage.classList.add("error");
    }
  });
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
    clearArticlePlanLink();
    articleSearchEntry.hidden = false;
    articleSearch.disabled = false;
    articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
    closeArticleSuggestions();
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
    if (planLookupPending) {
      message.textContent = "Esperá a que termine la búsqueda de la última revisión del plano.";
      message.classList.add("error");
      return;
    }
    const data = Object.fromEntries(new FormData(form).entries());
    for (const key of ["fecha_entrega_esperada", "nivel_inspeccion", "tamano_muestra", "porcentaje_muestreo", "material_utilizado", "numero_plano", "designacion", "lote_numero", "notas", "remito"]) {
      if (data[key] === "") data[key] = null;
    }
    for (const key of ["cantidad_solicitada", "cantidad_recibida", "cantidad_lote", "porcentaje_muestreo"]) {
      if (data[key] !== null && data[key] !== undefined) data[key] = Number(data[key]);
    }
    data.tamano_muestra = data.tamano_muestra ? Number(data.tamano_muestra) : null;
    data.cotas = [];
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
      clearArticlePlanLink();
      articleSearchEntry.hidden = false;
      articleSearch.disabled = false;
      articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
      closeArticleSuggestions();
      loadRecepciones();
    } catch (error) {
      message.textContent = error.message;
      message.classList.add("error");
    }
  });

  loadRecepciones();
})();