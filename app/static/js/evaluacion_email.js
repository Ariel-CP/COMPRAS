(function(root) {
  'use strict';
  function base64(value) {
    const bytes = new TextEncoder().encode(value);
    let binary = '';
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary);
  }
  function createDraft({desde, hasta, html}) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(desde) || !/^\d{4}-\d{2}-\d{2}$/.test(hasta)) throw new Error('Período inválido');
    const boundary = 'ranking_' + Date.now() + '_' + Math.random().toString(36).slice(2);
    const encode = value => base64(value).match(/.{1,76}/g)?.join('\r\n') || '';
    const filename = `informe_proveedores_${desde}_${hasta}.html`;
    return [
      'X-Unsent: 1',
      `Subject: =?UTF-8?B?${base64(`Evaluación de proveedores ${desde} al ${hasta}`)}?=`,
      'MIME-Version: 1.0',
      `Content-Type: multipart/mixed; boundary="${boundary}"`, '',
      `--${boundary}`, 'Content-Type: text/plain; charset=UTF-8', 'Content-Transfer-Encoding: base64', '',
      encode(`Adjunto el informe de evaluación de proveedores del ${desde} al ${hasta}, con los rankings y gráficos del período.\n\nCriterios: sin emisión OC se considera dentro del plazo; sin certificado suma cero. Resultados recalculados con el maestro actual.\n\nAbrir el adjunto HTML en el navegador para ver el informe.`),
      `--${boundary}`, 'Content-Type: text/html; charset=UTF-8',
      `Content-Disposition: attachment; filename="${filename}"`, 'Content-Transfer-Encoding: base64', '', encode(html),
      `--${boundary}--`, ''
    ].join('\r\n');
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {createDraft};
  else root.RankingEmail = {createDraft};
})(globalThis);
