const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createDraft}=require('../app/static/js/evaluacion_email.js');
test('borrador MIME conserva adjunto UTF-8 y no inventa destinatarios',()=>{
 const html='<h1>Evaluación · SAITTA</h1><svg></svg>';
 const result=createDraft({desde:'2026-01-01',hasta:'2026-07-31',html});
 assert.match(result,/X-Unsent: 1\r\n/);
 assert.doesNotMatch(result,/^To:/m);
 assert.match(result,/filename="informe_proveedores_2026-01-01_2026-07-31.html"/);
 const attachment=result.split('Content-Disposition: attachment;')[1].split('\r\n\r\n')[1].split('\r\n--')[0];
 assert.equal(Buffer.from(attachment.replaceAll('\r\n',''),'base64').toString('utf8'),html);
});
test('no acepta inyección en encabezados por fechas',()=>{
 assert.throws(()=>createDraft({desde:'2026-01-01\r\nTo: otro',hasta:'2026-07-31',html:''}));
});
