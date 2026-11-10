(() => {
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  window.printReceptionLabel = (data, labelType, existingWindow = null) => {
    if (!data) return false;
    const printWindow = existingWindow || window.open("", "_blank");
    if (!printWindow) return false;

    const line = data.lineas?.[0] || {};
    const accepted = labelType === "accepted";
    const labelWidth = accepted ? 148 : 150;
    const labelHeight = accepted ? 40 : 64.8;
    const fechaRecepcion = data.fecha_recepcion
      ? new Date(`${String(data.fecha_recepcion).slice(0, 10)}T00:00:00`).toLocaleDateString("es-AR")
      : "";
    const printHtml = `<!doctype html>
      <html lang="es">
      <head>
        <meta charset="utf-8">
        <title>Etiqueta ${escapeHtml(data.numero_recepcion)}</title>
        <style>
          @page { size: ${labelWidth}mm ${labelHeight}mm; margin: 0; }
          * { box-sizing: border-box; }
          body { width: ${labelWidth}mm; height: ${labelHeight}mm; margin: 0; color: #111; font: 6pt Arial, sans-serif; }
          .label { width: ${labelWidth}mm; height: ${labelHeight}mm; overflow: hidden; }
          .yellow { position: relative; }
          .field { position: absolute; overflow: hidden; color: #111; font-size: 6pt; font-weight: 700; line-height: 1.1; overflow-wrap: anywhere; }
          .denominacion { top: 40mm; left: 7mm; width: 92mm; height: 4mm; }
          .proveedor { top: 48mm; left: 7mm; width: 92mm; height: 4mm; }
          .fecha { top: 54mm; left: 18mm; width: 27mm; height: 4mm; }
          .remito { top: 54mm; left: 52mm; width: 47mm; height: 4mm; }
          .responsable { top: 59mm; left: 17mm; width: 40mm; height: 4mm; }
          .acta { top: 41mm; left: 103mm; width: 43mm; height: 4mm; text-align: center; }
          .observaciones { top: 50mm; left: 103mm; width: 43mm; height: 12mm; white-space: pre-line; }
          .accepted { position: relative; }
          .inspection-number { position: absolute; top: 24mm; right: 3mm; width: 28mm; height: 8mm; overflow: hidden; color: #111; font-size: 8pt; font-weight: 700; text-align: center; }
        </style>
      </head>
      <body>
        ${accepted
          ? `<main class="label accepted"><div class="inspection-number">${escapeHtml(data.numero_recepcion || "")}</div></main>`
          : `<main class="label yellow">
              <div class="field denominacion">${escapeHtml(line.designacion || line.producto_nombre || "")}</div>
              <div class="field proveedor">${escapeHtml(data.proveedor_nombre || data.proveedor_codigo || "")}</div>
              <div class="field fecha">${escapeHtml(fechaRecepcion)}</div>
              <div class="field remito">${escapeHtml(data.remito || "")}</div>
              <div class="field responsable">${escapeHtml(data.usuario_recepcion_nombre || "")}</div>
              <div class="field acta">${escapeHtml(data.numero_recepcion || "")}</div>
              <div class="field observaciones">${escapeHtml(data.notas || "")}</div>
            </main>`}
      </body>
      </html>`;
    printWindow.addEventListener("load", () => {
      printWindow.focus();
      printWindow.print();
    }, { once: true });
    printWindow.document.open();
    printWindow.document.write(printHtml);
    printWindow.document.close();
    return true;
  };

  window.printReceptionYellowLabel = (data, existingWindow = null) =>
    window.printReceptionLabel(data, "reception", existingWindow);
  window.printReceptionAcceptedLabel = (data, existingWindow = null) =>
    window.printReceptionLabel(data, "accepted", existingWindow);
})();