/* Guía local: usa únicamente las acciones explícitas del Wizard. */
(function (root) {
  "use strict";
  const pasos = [
    { titulo: "¿Para qué período necesitás materiales?", texto: "Indicá año y mes en el paso 1. Voy a cargar el plan y los ajustes guardados. Si el período no tiene plan, primero cargalo en Plan mensual.", pane: 1, foco: "anioPlan", accion: "Cargar plan y continuar" },
    { titulo: "Necesito que revises el stock MP y los pedidos LAF", texto: "En el paso 2, revisá año, mes y fecha de corte del stock. Importá el stock de Flexxus si corresponde y comprobá los pedidos LAF ya emitidos. Las importaciones y cargas guardan datos; ejecutalas con sus botones. Confirmá cuando la información esté lista.", pane: 2, foco: "anioStock", accion: "Confirmo: revisé stock MP y LAF" },
    { titulo: "¿Cuánto producto terminado tenés disponible?", texto: "Revisá el stock PT del paso 3. Podés conservar los valores guardados o importar y guardar un CSV/XLSX actualizado. Una tabla vacía no demuestra stock cero: verificá el dato antes de confirmar.", pane: 3, foco: "archivoStockPt", accion: "Confirmo: revisé el stock PT" },
    { titulo: "¿Qué cantidades quedan pendientes de entregar a clientes?", texto: "Revisá la deuda a clientes del paso 4. Si cambió, importá y guardá el archivo actualizado. Confirmá los valores, incluso cuando sean cero; la guía no completa cantidades por su cuenta.", pane: 4, foco: "archivoDeudaClientes", accion: "Confirmo: revisé la deuda de clientes" },
    { titulo: "Los datos están revisados. ¿Simulamos los materiales a comprar?", texto: "Voy a usar el cálculo existente con el plan, stock y deuda revisados. Esta acción no guarda sugerencias ni corridas. Después revisá cantidades, unidades y alertas antes de guardar o exportar.", pane: 5, foco: "btnCalcularOc", accion: "Simular materiales" },
    { titulo: "Revisá la propuesta de materiales", texto: "El resultado está en el paso 5. Revisá faltantes y alertas. Podés exportar la propuesta con los botones existentes o guardar sugerencias mediante la opción de persistencia y Calcular OC. Esta guía no emite pedidos a proveedores.", pane: 5, foco: "tablaFaltantesOc", accion: "Ver la propuesta" },
  ];

  function iniciarGuiaWizard(api) {
    const panel = document.getElementById("wizard-guia");
    if (!panel) return;
    const titulo = document.getElementById("guia-titulo");
    const mensaje = document.getElementById("guia-mensaje");
    const estado = document.getElementById("guia-estado");
    const continuar = document.getElementById("guia-continuar");
    const volver = document.getElementById("guia-volver");
    const lista = document.getElementById("guia-lista");
    let paso = 0;
    let ocupado = false;
    let revision = 0;

    function mostrar(navegar = true) {
      const actual = pasos[paso];
      titulo.textContent = actual.titulo;
      mensaje.textContent = actual.texto;
      continuar.textContent = actual.accion;
      continuar.disabled = ocupado;
      volver.disabled = ocupado || paso === 0;
      lista.replaceChildren();
      pasos.forEach((item, index) => {
        const li = document.createElement("li");
        li.textContent = `${index < paso ? "✓" : index === paso ? "→" : "○"} ${["Período y plan", "Stock MP y LAF", "Stock PT", "Deuda a clientes", "Simulación", "Revisión final"][index]}`;
        if (index === paso) li.setAttribute("aria-current", "step");
        lista.appendChild(li);
      });
      if (navegar) api.ir(pasos[paso].pane);
    }

    function invalidar(desde = 0) {
      revision += 1;
      paso = Math.min(paso, desde);
      estado.textContent = "Se modificaron datos. Volvé a revisar los pasos afectados antes de simular.";
      mostrar(false);
    }

    // Un cambio invalida la revisión, sin borrar ni modificar los datos del Wizard.
    document.querySelectorAll(".wizard-body").forEach((pane) => {
      pane.addEventListener("input", (event) => {
        if (event.target.id !== "persistirSugerencias") {
          const desde = ["anioPlan", "mesPlan"].includes(event.target.id) ? 0 : Math.max(1, Number(pane.dataset.pane) - 1);
          invalidar(desde);
        }
      });
      pane.addEventListener("change", (event) => {
        if (event.target.id !== "persistirSugerencias") {
          const desde = ["anioPlan", "mesPlan"].includes(event.target.id) ? 0 : Math.max(1, Number(pane.dataset.pane) - 1);
          invalidar(desde);
        }
      });
    });
    document.addEventListener("wizard:datos-modificados", (event) => invalidar(event.detail.desde));
    volver.addEventListener("click", () => {
      paso = Math.max(0, paso - 1);
      estado.textContent = "Revisá este paso nuevamente.";
      mostrar();
    });
    document.getElementById("guia-ir-paso").addEventListener("click", () => {
      api.ir(pasos[paso].pane);
      const campo = document.getElementById(pasos[paso].foco);
      campo.scrollIntoView({ behavior: "smooth", block: "center" });
      campo.focus({ preventScroll: true });
    });
    continuar.addEventListener("click", async () => {
      if (ocupado) return;
      ocupado = true;
      const version = revision;
      estado.textContent = "";
      mostrar();
      try {
        if (paso === 0 || paso === 4) {
          estado.textContent = paso === 0 ? "Cargando el plan y los ajustes…" : "Calculando materiales sin guardar…";
          const ok = await (paso === 0 ? api.cargarPlan() : api.simular());
          if (version !== revision) return;
          if (!ok) {
            estado.textContent = "No se pudo completar la acción. Revisá el mensaje del paso y corregí los datos antes de continuar.";
            return;
          }
        }
        if (version !== revision) return;
        paso = Math.min(paso + 1, pasos.length - 1);
        estado.textContent = paso === 5 ? "Simulación completada. Falta tu revisión final." : "Continuemos con el siguiente dato.";
      } catch (_error) {
        estado.textContent = "No se pudo completar la acción. Revisá la conexión y los mensajes del Wizard; no se avanzó de paso.";
      } finally {
        ocupado = false;
        mostrar();
      }
    });
    mostrar();
  }
  root.iniciarGuiaWizard = iniciarGuiaWizard;
})(window);
