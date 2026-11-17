(() => {
  "use strict";
  const form = document.getElementById("consulta-ia-form");
  if (!form) return;
  const periodo = document.getElementById("consulta-ia-periodo");
  const tema = document.getElementById("consulta-ia-tema");
  const pregunta = document.getElementById("consulta-ia-pregunta");
  const resultado = document.getElementById("consulta-ia-resultado");
  const hoy = new Date();
  periodo.defaultValue = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;

  form.querySelectorAll("[data-pregunta]").forEach((boton) => {
    boton.addEventListener("click", () => {
      pregunta.value = boton.dataset.pregunta;
      pregunta.setCustomValidity("");
      tema.value = boton.dataset.tema;
      resultado.hidden = true;
      pregunta.focus();
    });
  });
  form.addEventListener("input", () => { resultado.hidden = true; });
  form.addEventListener("change", () => { resultado.hidden = true; });
  form.addEventListener("reset", () => {
    resultado.hidden = true;
    pregunta.setCustomValidity("");
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!pregunta.value.trim()) {
      pregunta.setCustomValidity("Escribí una pregunta para preparar la consulta.");
      pregunta.reportValidity();
      return;
    }
    document.getElementById("consulta-ia-contexto").textContent =
      `Período: ${periodo.value} · Tema: ${tema.options[tema.selectedIndex].text}`;
    document.getElementById("consulta-ia-texto").textContent = pregunta.value.trim();
    resultado.hidden = false;
  });
  pregunta.addEventListener("input", () => { pregunta.setCustomValidity(""); });
})();
