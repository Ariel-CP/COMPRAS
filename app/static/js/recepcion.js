(() => {
  const form = document.getElementById("recepcion-form");
  if (!form) return;

  const page = document.querySelector(".recepcion-page");
  const message = document.getElementById("recepcion-message");
  const providerSearch = document.getElementById("proveedor-search");
  const providerSearchEntry = document.getElementById("proveedor-search-entry");
  const providerId = document.getElementById("proveedor-id");
  const providerSelected = document.getElementById("proveedor-selected");
  const providerSelectedCode = document.getElementById("proveedor-selected-code");
  const providerSelectedName = document.getElementById("proveedor-selected-name");
  const providerSuggestions = document.getElementById("proveedor-suggestions");
  const inspectionLevel = form.elements.namedItem("nivel_inspeccion");
  const inspectionRecommendation = document.getElementById("nivel-inspeccion-recomendacion");
  const samplePlanRecommendation = document.getElementById("plan-muestreo-recomendacion");
  const lotSize = document.getElementById("cantidad-recibida");
  const lotIdentifier = form.elements.namedItem("lote_numero");
  const sampleSize = form.elements.namedItem("tamano_muestra");
  const samplePercentage = form.elements.namedItem("porcentaje_muestreo");
  const articleSearch = document.getElementById("articulo-search");
  const articleSearchEntry = document.getElementById("articulo-search-entry");
  const articleId = document.getElementById("articulo-id");
  const articleSelected = document.getElementById("articulo-selected");
  const articleSelectedCode = document.getElementById("articulo-selected-code");
  const articleSelectedName = document.getElementById("articulo-selected-name");
  const articleUnitHint = document.getElementById("articulo-unidad-hint");
  const articlePlanActions = document.getElementById("articulo-plan-actions");
  const articlePlanLink = document.getElementById("articulo-open-plan");
  const articlePlanNumber = document.getElementById("numero_plano");
  const articleSuggestions = document.getElementById("articulo-suggestions");
  inspectionLevel.disabled = true;
  const writeEnabled = page?.dataset.canWrite === "true";
  const currentUserName = page?.dataset.currentUserName || "Usuario actual";
  let providerSearchTimer;
  let providerSearchController;
  let recommendationController;
  let recommendationGeneration = 0;
  let samplePlanController;
  let samplePlanGeneration = 0;
  let activeProviderOption = -1;
  let articleSearchTimer;
  let articleSearchController;
  let activeArticleOption = -1;
  let planLookupGeneration = 0;
  let planLookupPending = false;
  let selectedProviderCode = "";
  let editingReceptionId = null;
  let activeReceptionDetails = null;
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

  function setInspectionRecommendation(text, isError = false) {
    inspectionRecommendation.textContent = text;
    inspectionRecommendation.hidden = !text;
    inspectionRecommendation.classList.toggle("error", isError);
  }

  function setSamplePlanRecommendation(text, isError = false) {
    samplePlanRecommendation.textContent = text;
    samplePlanRecommendation.hidden = !text;
    samplePlanRecommendation.classList.toggle("error", isError);
  }

  async function updateSamplePlan() {
    samplePlanController?.abort();
    samplePlanController = null;
    const generation = ++samplePlanGeneration;
    sampleSize.value = "";
    samplePercentage.value = "";
    const nivel = inspectionLevel.value;
    const lote = lotSize.value.trim() || lotIdentifier.value.trim();
    if (!nivel || !lote) {
      setSamplePlanRecommendation("");
      return;
    }

    samplePlanController = new AbortController();
    setSamplePlanRecommendation("Calculando plan de muestreo...");
    try {
      const params = new URLSearchParams({ nivel, lote });
      const response = await fetch(`/api/recepcion/plan-muestreo?${params}`, {
        signal: samplePlanController.signal,
        cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "No se pudo calcular el plan");
      if (generation !== samplePlanGeneration) return;

      sampleSize.value = String(result.tamano_muestra);
      samplePercentage.value = String(result.porcentaje_muestreo);
      setSamplePlanRecommendation(
        `Plan ${result.nivel_inspeccion}: lote ${result.cantidad_lote}, letra ${result.letra_codigo}, muestra ${result.tamano_muestra} unidades (${result.porcentaje_muestreo} %). La aceptación Ac/Re requiere definir el AQL aplicable.`,
      );
    } catch (error) {
      if (error.name === "AbortError" || generation !== samplePlanGeneration) return;
      setSamplePlanRecommendation(error.message, true);
    }
  }

  async function loadInspectionRecommendation(provider) {
    recommendationController?.abort();
    recommendationController = new AbortController();
    const generation = ++recommendationGeneration;
    inspectionLevel.value = "";
    setInspectionRecommendation("Consultando entregas registradas en el año calendario...");
    updateSamplePlan();

    try {
      const response = await fetch(
        `/api/recepcion/proveedores/${encodeURIComponent(provider.id)}/recomendacion-control`,
        { signal: recommendationController.signal, cache: "no-store" },
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "No se pudo consultar el historial");
      if (generation !== recommendationGeneration || providerId.value !== String(provider.id)) return;

      if (result.estado === "CALCULADO") {
        inspectionLevel.value = result.nivel_recomendado;
        const porcentaje = Number(result.porcentaje_entregas_rechazadas).toLocaleString("es-AR", {
          maximumFractionDigits: 3,
        });
        setInspectionRecommendation(
          `${result.nivel_recomendado}: ${result.rechazados} de ${result.total_entregas} entregas rechazadas (${porcentaje} %) en ${new Date(result.hasta).getFullYear()}, según PG-4.10.01.`,
        );
        updateSamplePlan();
        return;
      }

      inspectionLevel.value = "";
      setInspectionRecommendation(
        result.mensaje || "No se pudo determinar una recomendación.",
        ["HISTORIAL_INCOMPLETO", "HISTORIAL_INVALIDO"].includes(result.estado),
      );
      updateSamplePlan();
    } catch (error) {
      if (error.name === "AbortError" || generation !== recommendationGeneration) return;
      inspectionLevel.value = "";
      setInspectionRecommendation(
        `No se pudo obtener la recomendación de desempeño: ${error.message}`,
        true,
      );
      updateSamplePlan();
    }
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
    loadInspectionRecommendation(provider);
    loadRecepciones();
    document.getElementById("orden_compra").focus();
  }

  function clearProviderSelection() {
    recommendationGeneration += 1;
    recommendationController?.abort();
    inspectionLevel.value = "";
    setInspectionRecommendation("");
    updateSamplePlan();
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
    articleUnitHint.textContent = article.unidad_medida
      ? `Unidad de medida: ${article.unidad_medida}`
      : "La unidad de medida no está configurada para este artículo.";
    articleUnitHint.hidden = false;
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
    articleUnitHint.hidden = true;
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
      ><strong>${escapeHtml(article.codigo)}</strong>${escapeHtml(article.nombre)}${article.unidad_medida ? ` <small>${escapeHtml(article.unidad_medida)}</small>` : ""}</button>
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
  lotSize.addEventListener("input", updateSamplePlan);
  lotIdentifier.addEventListener("input", updateSamplePlan);
  inspectionLevel.addEventListener("change", updateSamplePlan);
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
    return;
    /* La consulta de controles vive en recepcion_controles.js. */
    /* istanbul ignore next */
    const query = document.getElementById("recepcion-query").value.trim();
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    if (selectedProviderCode) params.set("proveedor_codigo", selectedProviderCode);
    rows.innerHTML = '<tr><td colspan="5">Cargando...</td></tr>';

    const fetchList = async (url) => {
      const response = await fetch(url);
      const body = await response.text();
      let data;
      try {
        data = body ? JSON.parse(body) : [];
      } catch {
        throw new Error(`Respuesta no válida del servidor (HTTP ${response.status})`);
      }
      if (!response.ok) {
        throw new Error(data.detail || `No se pudo cargar el listado (HTTP ${response.status})`);
      }
      return data;
    };

    try {
      const [operativasResult, accessResult] = await Promise.allSettled([
        fetchList(`/api/recepcion/operativas?${params}`),
        fetchList(`/api/recepcion/access/controles?${params}`),
      ]);
      const operativas = operativasResult.status === "fulfilled"
        ? operativasResult.value.map((item) => ({
          origen: "operativo",
          id: Number(item.id),
          numero: item.numero_recepcion,
          fecha: item.fecha_control || item.fecha_recepcion,
          proveedorCodigo: item.proveedor_codigo,
          proveedorNombre: item.proveedor_nombre,
          ordenCompra: item.orden_compra,
          remito: item.remito,
          estado: item.estado,
          soloLectura: item.recepcion_staging_id != null,
        }))
        : [];
      const access = accessResult.status === "fulfilled"
        ? accessResult.value.map((item) => ({
          origen: "access",
          id: Number(item.ID_INT),
          numero: `ID_INT ${item.ID_INT}`,
          fecha: item["Fecha Control"],
          proveedorCodigo: item["Codigo Proveedor"],
          proveedorNombre: item.PROVEEDOR,
          ordenCompra: item["ORDEN DE COMPRA"],
          remito: item.Remito,
          estado: item.Estado,
        }))
        : [];
      const recepciones = [...operativas, ...access].sort((first, second) => {
        const firstDate = Date.parse(first.fecha || "") || 0;
        const secondDate = Date.parse(second.fecha || "") || 0;
        return secondDate - firstDate || second.id - first.id;
      });
      const errors = [operativasResult, accessResult]
        .filter((result) => result.status === "rejected")
        .map((result) => escapeHtml(result.reason.message));
      const receiptRows = recepciones.map((item) => {
        const openButton = item.origen === "access"
          ? `<button class="recepcion-open" type="button" data-access-id="${item.id}">${escapeHtml(item.numero)}</button><br><small>Access</small>`
          : `<button class="recepcion-open" type="button" data-recepcion-id="${item.id}">${escapeHtml(item.numero)}</button><br><small>COMPRAS</small>`;
        const actions = !writeEnabled || item.soloLectura
          ? '<span class="recepcion-source">Solo lectura</span>'
          : item.origen === "access"
          ? '<span class="recepcion-source">Solo lectura</span>'
          : `<div class="recepcion-row-actions">
              <button class="recepcion-row-action" type="button" data-edit-recepcion="${item.id}">Editar</button>
              <button class="recepcion-row-action danger" type="button" data-delete-recepcion="${item.id}">Borrar</button>
            </div>`;
        return `<tr><td>${openButton}<br>${escapeHtml(item.fecha || "")}</td>
          <td>${escapeHtml(item.proveedorCodigo || "")}<br>${escapeHtml(item.proveedorNombre || "")}</td>
          <td>${escapeHtml(item.ordenCompra || "")}${item.remito ? `<br>Rto. ${escapeHtml(item.remito)}` : ""}</td>
          <td><span class="state-pill">${escapeHtml(item.estado || "Sin estado")}</span></td>
          <td>${actions}</td></tr>`;
      });
      if (!recepciones.length && !errors.length) {
        receiptRows.push('<tr><td colspan="5">Sin recepciones encontradas</td></tr>');
      }
      if (errors.length) {
        receiptRows.push(`<tr><td colspan="5">Listado parcial: ${errors.join(" · ")}</td></tr>`);
      }
      rows.innerHTML = receiptRows.join("");
    } catch (error) {
      rows.innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  async function loadAccessReceiptDetail(accessId) {
    const detail = document.getElementById("recepcion-detail");
    activeReceptionDetails = null;
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
    activeReceptionDetails = null;
    detail.innerHTML = '<p class="recepcion-detail-empty">Cargando detalle...</p>';
    try {
      const response = await fetch(`/api/recepcion/operativas/${recepcionId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el detalle");
      activeReceptionDetails = data;
      const header = `
        <div class="recepcion-detail-heading">
          <h3>${escapeHtml(data.numero_recepcion)} · ${escapeHtml(data.estado)}</h3>
          <button class="recepcion-button secondary" type="button" data-print-yellow-label>
            <span aria-hidden="true">&#128424;</span> Imprimir etiqueta amarilla
          </button>
        </div>
        <div class="recepcion-detail-grid">
          <div><strong>Proveedor</strong>${escapeHtml(data.proveedor_codigo)} · ${escapeHtml(data.proveedor_nombre)}</div>
          <div><strong>OC / Remito</strong>${escapeHtml(data.orden_compra)} · ${escapeHtml(data.remito || "Sin remito")}</div>
          <div><strong>Recepción / Control</strong>${escapeHtml(data.fecha_recepcion)} · ${escapeHtml(data.fecha_control || "Pendiente")}</div>
          <div><strong>Recibió</strong>${escapeHtml(data.usuario_recepcion_nombre || "No registrado")}</div>
          <div><strong>Control de calidad</strong>${escapeHtml(data.usuario_calidad_nombre || "Pendiente")}</div>
          <div><strong>Embalaje de ingreso</strong>${escapeHtml(data.estado_embalaje || "-")}</div>
          <div><strong>Observaciones</strong>${escapeHtml(data.notas || "Sin observaciones")}</div>
        </div>`;
      const lines = data.lineas.map((line) => `
        <div class="recepcion-detail-line">
          <h3>Línea ${Number(line.numero_linea)} · ${escapeHtml(line.producto_codigo)} · ${escapeHtml(line.designacion || line.producto_nombre)}</h3>
          <div class="recepcion-detail-grid">
            <div><strong>Plano</strong>${escapeHtml(line.numero_plano || "-")}</div>
            <div><strong>Lote / cantidad recibida</strong>${escapeHtml(line.lote_numero || "-")} · ${escapeHtml(line.cantidad_recibida ?? "-")}</div>
            <div><strong>Inspección / muestra</strong>${escapeHtml(line.nivel_inspeccion || "Plan pendiente")} · letra ${escapeHtml(line.letra_codigo_muestreo || "-")} · ${escapeHtml(line.tamano_muestra ?? "-")} unidades (${escapeHtml(line.porcentaje_muestreo ?? "-")}%)</div>
            <div><strong>Estado del embalaje</strong>${escapeHtml(data.estado_embalaje || "-")}</div>
            <div><strong>Material utilizado</strong>${escapeHtml(line.material_utilizado || "-")}</div>
          </div>
          ${["NO_INSPECCIONADO", "PENDIENTE", "RECHAZADO"].includes(line.estado_inspeccion) ? `<p><a class="recepcion-button secondary" href="/ui/recepcion/calidad?linea=${Number(line.id)}">Abrir control de calidad</a></p>` : ""}
          <div class="recepcion-table-wrap"><table class="recepcion-detail-table"><thead><tr><th>Cota</th><th>Especificación</th><th>Control</th><th>Desviación</th><th>Resultado</th></tr></thead><tbody>
            ${line.cotas.length ? line.cotas.map((cota) => `<tr><td>${escapeHtml(cota.criterio_nombre)}</td><td>${escapeHtml(cota.especificacion || "-")}</td><td>${escapeHtml(cota.valor_medido || "-")}</td><td>${escapeHtml(cota.desviacion || "-")}</td><td>${escapeHtml(cota.resultado)}</td></tr>`).join("") : '<tr><td colspan="5">Sin cotas registradas</td></tr>'}
          </tbody></table></div>
        </div>`).join("");
      detail.innerHTML = header + (lines || '<p class="recepcion-detail-empty">La recepción no tiene líneas.</p>');
    } catch (error) {
      activeReceptionDetails = null;
      detail.innerHTML = `<p class="recepcion-detail-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  function printYellowLabel(data = activeReceptionDetails, existingWindow = null) {
    if (!window.printReceptionYellowLabel(data)) {
      message.textContent = "El navegador bloqueó la ventana de impresión. Permití las ventanas emergentes para este sitio.";
      message.className = "recepcion-message error";
    }
  }

  function setFormDate(name, value) {
    form.elements.namedItem(name).value = value ? String(value).slice(0, 10) : "";
  }

  async function editReception(recepcionId) {
    message.textContent = "Cargando control para editar...";
    message.className = "recepcion-message";
    try {
      const response = await fetch(`/api/recepcion/operativas/${recepcionId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el control");
      if (data.lineas.length !== 1) {
        throw new Error("La edición solo está disponible para controles de una línea");
      }
      const line = data.lineas[0];
      editingReceptionId = Number(data.id);
      providerId.value = String(data.proveedor_id);
      providerSearch.value = `${data.proveedor_codigo} · ${data.proveedor_nombre}`;
      providerSearch.setCustomValidity("");
      providerSelectedCode.textContent = data.proveedor_codigo || "";
      providerSelectedName.textContent = data.proveedor_nombre || "";
      providerSelected.hidden = false;
      providerSearchEntry.hidden = true;
      selectedProviderCode = String(data.proveedor_codigo || "");

      articleId.value = String(line.producto_id);
      articleSearch.value = `${line.producto_codigo} · ${line.producto_nombre}`;
      articleSearch.setCustomValidity("");
      articleSelectedCode.textContent = line.producto_codigo || "";
      articleSelectedName.textContent = line.producto_nombre || "";
      articleUnitHint.textContent = line.unidad_medida
        ? `Unidad de medida: ${line.unidad_medida}`
        : "La unidad de medida no está configurada para este artículo.";
      articleUnitHint.hidden = false;
      articleSelected.hidden = false;
      articleSearchEntry.hidden = true;

      setFormDate("fecha_recepcion", data.fecha_recepcion);
      setFormDate("fecha_entrega_esperada", data.fecha_entrega_esperada);
      for (const [name, value] of Object.entries({
        orden_compra: data.orden_compra,
        remito: data.remito,
        numero_plano: line.numero_plano,
        lote_numero: line.lote_numero,
        cantidad_solicitada: line.cantidad_solicitada,
        cantidad_recibida: line.cantidad_recibida,
        estado_embalaje: data.estado_embalaje,
        material_utilizado: line.material_utilizado,
        nivel_inspeccion: line.nivel_inspeccion,
        tamano_muestra: line.tamano_muestra,
        porcentaje_muestreo: line.porcentaje_muestreo,
        notas: data.notas,
      })) {
        form.elements.namedItem(name).value = value ?? "";
      }
      updateSamplePlan();
      form.elements.namedItem("designacion").value = line.designacion || "";
      for (const name of ["terminacion_superficial", "control_dimensional", "embalaje"]) {
        form.elements.namedItem(name).value = data[name] ?? "";
      }

      const cotasList = document.getElementById("recepcion-edit-cotas");
      cotasList.replaceChildren();
      line.cotas.forEach((cota) => addCota(cotasList, cota));
      document.getElementById("recepcion-edit-controls").hidden = false;
      document.getElementById("recepcion-save").textContent = "Actualizar control";
      document.getElementById("recepcion-reset").textContent = "Cancelar edición";
      message.textContent = `Editando ${data.numero_recepcion}. Los controles actuales se conservarán si los dejas sin cambios.`;
      await loadDetail(recepcionId);
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      message.textContent = error.message;
      message.classList.add("error");
    }
  }

  function resetReceptionForm() {
    editingReceptionId = null;
    form.reset();
    providerId.value = "";
    recommendationGeneration += 1;
    recommendationController?.abort();
    inspectionLevel.value = "";
    setInspectionRecommendation("");
    samplePlanController?.abort();
    samplePlanGeneration += 1;
    sampleSize.value = "";
    samplePercentage.value = "";
    setSamplePlanRecommendation("");
    selectedProviderCode = "";
    providerSelected.hidden = true;
    providerSearchEntry.hidden = false;
    providerSearch.disabled = false;
    providerSearch.setCustomValidity("Seleccioná un proveedor de la lista.");
    closeProviderSuggestions();
    articleId.value = "";
    articleSelected.hidden = true;
    articleUnitHint.hidden = true;
    clearArticlePlanLink();
    articleSearchEntry.hidden = false;
    articleSearch.disabled = false;
    articleSearch.setCustomValidity("Seleccioná un artículo de la lista.");
    closeArticleSuggestions();
    document.getElementById("recepcion-edit-controls").hidden = true;
    document.getElementById("recepcion-edit-cotas").replaceChildren();
    document.getElementById("recepcion-save").textContent = "Guardar recepción";
    document.getElementById("recepcion-reset").textContent = "Nueva inspección";
    message.textContent = "";
    message.className = "recepcion-message";
  }

  async function deleteReception(recepcionId) {
    if (!window.confirm("¿Borrar este control local de COMPRAS? Esta acción no se puede deshacer.")) {
      return;
    }
    try {
      const response = await fetch(`/api/recepcion/operativas/${recepcionId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.detail || "No se pudo borrar el control");
      }
      document.getElementById("recepcion-detail").innerHTML =
        '<p class="recepcion-detail-empty">El control se borró.</p>';
      await loadRecepciones();
    } catch (error) {
      message.textContent = error.message;
      message.className = "recepcion-message error";
    }
  }

  const detailContainer = document.getElementById("recepcion-detail");
  detailContainer.addEventListener("click", (event) => {
    if (event.target.closest("[data-print-yellow-label]")) printYellowLabel();
  });
  form.addEventListener("click", (event) => {
    if (event.target.closest("[data-edit-cota-add]")) {
      addCota(document.getElementById("recepcion-edit-cotas"));
    }
  });
  document.getElementById("recepcion-reset").addEventListener("click", resetReceptionForm);
  document.getElementById("recepcion-reset-bottom").addEventListener("click", resetReceptionForm);

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
    for (const key of ["fecha_entrega_esperada", "nivel_inspeccion", "tamano_muestra", "porcentaje_muestreo", "material_utilizado", "numero_plano", "designacion", "lote_numero", "notas", "remito", "terminacion_superficial", "control_dimensional", "embalaje", "cantidad_solicitada", "cantidad_recibida", "estado_embalaje"]) {
      if (data[key] === "") data[key] = null;
    }
    for (const key of ["porcentaje_muestreo", "terminacion_superficial", "control_dimensional", "embalaje", "cantidad_solicitada", "cantidad_recibida"]) {
      if (data[key] !== null && data[key] !== undefined) data[key] = Number(data[key]);
    }
    data.nivel_inspeccion = inspectionLevel.value || null;
    data.tamano_muestra = data.tamano_muestra ? Number(data.tamano_muestra) : null;
    data.cotas = editingReceptionId
      ? [...document.querySelectorAll("#recepcion-edit-cotas .cota-row")].map((row) =>
        Object.fromEntries(
          [...row.querySelectorAll("[data-field]")].map((control) => [
            control.dataset.field,
            control.value || null,
          ]),
        ),
      )
      : [];
    try {
      const url = editingReceptionId
        ? `/api/recepcion/operativas/${editingReceptionId}`
        : "/api/recepcion/operativas";
      const response = await fetch(url, {
        method: editingReceptionId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "No se pudo guardar la recepción");
      const savedId = editingReceptionId || Number(result.id);
      const wasEditing = Boolean(editingReceptionId);
      const successMessage = wasEditing
        ? "Control actualizado."
        : `Recepción ${result.numero_recepcion} guardada (${result.estado}).`;
      await resetReceptionForm();
      message.textContent = successMessage;
      message.classList.add("success");
      await loadRecepciones();
      if (savedId) await loadDetail(savedId);
    } catch (error) {
      message.textContent = error.message;
      message.classList.add("error");
    }
  });

  loadRecepciones();
  const editId = Number(new URLSearchParams(window.location.search).get("editar"));
  if (Number.isInteger(editId) && editId > 0) editReception(editId);
})();