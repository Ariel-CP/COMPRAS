const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

function setup({ canWrite = true, validate, upload } = {}) {
  const elements = new Map();
  function element() { return { value: '', hidden: true, disabled: false, files: [{ name: 'datos.xlsx', size: 100 }], listeners: {}, children: [],
    addEventListener(name, fn) { this.listeners[name] = fn; },
    appendChild(p) { this.children.push(p); }, replaceChildren() { this.children = []; } }; }
  const get = (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  const pane = element();
  const document = { getElementById: (id) => get(id.replace('excel-', '')), createElement: element, querySelectorAll: () => [pane], addEventListener() {} };
  const requests = [], results = [];
  const preview = { valido: true, anio: 2026, mes: 5, anio_stock: 2026, mes_stock: 4, filas: { Plan_PT: 1 }, existentes: { LAF_Solicitado: 2 }, token: 'token-ficticio' };
  class FormData { constructor() { this.values = {}; } append(key, value) { this.values[key] = value; } }
  const runtime = { window: { confirm: () => true }, document, FormData,
    fetch: async (url, options) => {
      requests.push({ url, options });
      const json = url.endsWith('/validar') ? (validate ? await validate() : preview) : (upload ? await upload() : { importacion: preview, calculo: {} });
      return { ok: true, json: async () => json };
    } };
  vm.runInNewContext(readFileSync('app/static/js/wizard_excel.js', 'utf8'), runtime);
  runtime.window.iniciarWizardExcel({ periodo: () => '2026-05', puedeGuardar: canWrite, mostrar: async (data) => { results.push(data); } });
  return { get, pane, requests, results,
    validate: () => get('validar').listeners.click(), upload: () => get('importar').listeners.click() };
}

test('validar no guarda; confirmar sube el mismo archivo y token y muestra cálculo', async () => {
  const s = setup();
  await s.validate();
  assert.equal(s.results.length, 0);
  assert.equal(s.requests.length, 1);
  assert.equal(s.get('importar').disabled, false);
  await s.upload();
  assert.equal(s.requests[1].options.body.values.token, 'token-ficticio');
  assert.equal(s.requests[1].options.body.values.confirmar, 'true');
  assert.equal(s.results.length, 1);
  await s.upload();
  assert.equal(s.requests.length, 2);
});

test('errores por hoja impiden importar', async () => {
  const s = setup({ validate: async () => ({ valido: false, errores: [{ hoja: 'Stock_PT', fila: 2, campo: 'datos', mensaje: 'Falta cantidad' }], total_errores: 1 }) });
  await s.validate(); await s.upload();
  assert.equal(s.requests.length, 1);
  assert.equal(s.get('importar').disabled, true);
  assert.match(s.get('errores').children[0].textContent, /Stock_PT, fila 2/);
});

test('cambiar archivo o datos invalida confirmación', async () => {
  const s = setup(); await s.validate();
  s.get('archivo').listeners.change(); await s.upload();
  assert.equal(s.requests.length, 1);
  await s.validate(); s.pane.listeners.input(); await s.upload();
  assert.equal(s.requests.length, 2);
});

test('lector valida pero no puede guardar', async () => {
  const s = setup({ canWrite: false }); await s.validate(); await s.upload();
  assert.equal(s.get('importar').disabled, true);
  assert.equal(s.requests.length, 1);
});

test('bloquea doble confirmación durante envío', async () => {
  let resolve;
  const s = setup({ upload: () => new Promise((r) => { resolve = r; }) });
  await s.validate(); const pending = s.upload(); await s.upload();
  assert.equal(s.requests.length, 2);
  resolve({ importacion: {}, calculo: {} }); await pending;
  assert.equal(s.results.length, 1);
});
