const test=require('node:test');
const assert=require('node:assert/strict');
const {createReport,period}=require('../app/static/js/evaluacion_informe_calidad.js');

function data() {
  return {desde:'2026-01-01',hasta:'2026-07-31',calculado_en:'2026-11-18T14:00:00Z',metodologia:'METODO-PRUEBA',
    proveedores:Array.from({length:36},(_,i)=>({codigo:String(i),nombre:`Proveedor ${String(i).padStart(2,'0')}`,total:String(60+i)})),
    resumen:{puntaje_general:'88.84248554913294797687861272',controles_evaluados:519,controles_periodo:536,controles_excluidos:17,sin_fecha_oc:415,certificado_conflictos:1}};
}

test('incluye todos los proveedores, el promedio general y siete menores sin alterar la fuente',()=>{
  const source=data(),before=JSON.stringify(source),html=createReport(source);
  assert.equal(JSON.stringify(source),before);
  assert.equal((html.match(/fill="#155c8a"/g)||[]).length,36);
  assert.ok(html.includes('88,84'));
  assert.ok(!html.includes('77,83'));
  assert.ok(html.includes('519 recepciones evaluadas de 536'));
  const table=html.match(/<tbody>(.*?)<\/tbody>/s)[1];
  assert.equal((table.match(/<tr>/g)||[]).length,7);
  assert.ok(table.includes('Proveedor 00') && table.includes('Proveedor 06'));
  assert.ok(!table.includes('Proveedor 35'));
  assert.ok(html.includes('Aprobado ≥ 70') && html.includes('Condicional ≥ 55'));
});

test('reconoce cuatrimestres y semestres completos sin rotular enero-julio como semestre',()=>{
  assert.equal(period('2026-01-01','2026-07-31'),'01/01/2026 al 31/07/2026');
  assert.equal(period('2024-09-01','2024-12-31'),'3.er cuatrimestre 2024');
  assert.equal(period('2026-01-01','2026-06-30'),'1.er semestre 2026');
  assert.equal(period('2026-01-01','2026-12-31'),'Año 2026');
});

test('escapa nombres/codigos/metodologia y no carga recursos externos',()=>{
  const source=data();source.proveedores[0].nombre='</text><script>alert(1)</script>';
  source.proveedores[0].codigo='<img src=x>';
  source.metodologia='<svg onload=alert(1)>';
  const html=createReport(source);
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<img src=x>'));
  assert.ok(!/https?:\/\//.test(html));
  assert.ok(html.includes('size:A4 landscape'));
});

test('no fabrica resultado para periodos vacios o puntajes invalidos',()=>{
  let source=data();source.resumen.puntaje_general=null;
  assert.throws(()=>createReport(source),/puntajes válidos/);
  source=data();source.proveedores=[];
  assert.throws(()=>createReport(source),/puntajes válidos/);
  source=data();source.proveedores[0].total='NaN';
  assert.throws(()=>createReport(source),/puntajes válidos/);
  source=data();source.hasta='2025-01-01';
  assert.throws(()=>createReport(source),/Período inválido/);
});
