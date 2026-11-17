const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

function setup(overrides = {}) {
  function element() {
    return { textContent: '', disabled: false, dataset: {}, listeners: {},
      addEventListener(name, fn) { this.listeners[name] = fn; },
      replaceChildren() {}, appendChild() {}, setAttribute() {},
      scrollIntoView() {}, focus() {} };
  }
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const panes = [1, 2, 3, 4, 5].map((n) => ({ ...element(), dataset: { pane: String(n) } }));
  const document = { ...element(), getElementById: get, createElement: element, querySelectorAll: () => panes };
  const context = { window: {}, document };
  vm.runInNewContext(readFileSync('app/static/js/wizard_guia.js', 'utf8'), context);
  const calls = [];
  const api = {
    ir: (n) => calls.push(n),
    cargarPlan: async () => true,
    simular: async () => true,
    ...overrides,
  };
  context.window.iniciarGuiaWizard(api);
  return { get, panes, document, calls, click: () => get('guia-continuar').listeners.click() };
}

test('solicita revisiones antes de simular y llega a la propuesta', async () => {
  let simulations = 0;
  const s = setup({ simular: async () => { simulations++; return true; } });
  await s.click();
  assert.match(s.get('guia-titulo').textContent, /stock MP/);
  for (let i = 0; i < 3; i++) await s.click();
  assert.equal(simulations, 0);
  await s.click();
  assert.equal(simulations, 1);
  assert.match(s.get('guia-titulo').textContent, /propuesta/);
});

test('plan vacío o error de conexión no permite avanzar', async () => {
  for (const cargarPlan of [async () => false, async () => { throw Error('offline'); }]) {
    const s = setup({ cargarPlan });
    await s.click();
    assert.match(s.get('guia-titulo').textContent, /período/);
    assert.match(s.get('guia-estado').textContent, /No se pudo/);
    assert.equal(s.get('guia-continuar').disabled, false);
  }
});

test('editar el período durante la carga invalida el avance y evita doble envío', async () => {
  let resolve;
  let loads = 0;
  const s = setup({ cargarPlan: () => { loads++; return new Promise((r) => { resolve = r; }); } });
  const pending = s.click();
  await s.click();
  assert.equal(loads, 1);
  s.panes[0].listeners.input({ target: { id: 'mesPlan' } });
  resolve(true);
  await pending;
  assert.match(s.get('guia-titulo').textContent, /período/);
});

test('cambios en datos importados exigen nueva revisión sin mover el foco de carga', async () => {
  const s = setup();
  for (let i = 0; i < 5; i++) await s.click();
  const navigations = s.calls.length;
  s.document.listeners['wizard:datos-modificados']({ detail: { desde: 2 } });
  assert.match(s.get('guia-titulo').textContent, /producto terminado/);
  assert.equal(s.calls.length, navigations);
});

test('fallo al calcular conserva el paso de simulación', async () => {
  const s = setup({ simular: async () => false });
  for (let i = 0; i < 5; i++) await s.click();
  assert.match(s.get('guia-titulo').textContent, /Simulamos|simulamos/);
  assert.match(s.get('guia-estado').textContent, /No se pudo/);
});

test('simulación de la guía nunca persiste aunque la casilla esté marcada', async () => {
  const html = readFileSync('app/templates/plan/plan_asistente_oc.html', 'utf8');
  const start = html.indexOf('  async function calcularOc(');
  const end = html.indexOf('  btnCargarPresuncion.addEventListener', start);
  const urls = [];
  const context = {
    anioPlan: { value: '2026' }, mesPlan: { value: '11' },
    presuncionItems: [{}], CAN_WRITE: true,
    periodoPlanCargado: '2026-11',
    persistirSugerencias: { checked: true }, ocFeedback: {}, API_OC: '/calcular',
    buildAjustesPt: () => [],
    fetch: async (url) => { urls.push(url); return { ok: true, json: async () => ({}) }; },
    renderKpi() {}, renderDemandaNeta() {}, renderFaltantes() {}, renderAlertas() {},
    cargarCorridas: async () => {},
  };
  vm.createContext(context);
  vm.runInContext(html.slice(start, end), context);
  assert.equal(await vm.runInContext('calcularOc(false)', context), true);
  assert.match(urls[0], /persistir_sugerencias=false/);
  await vm.runInContext('calcularOc()', context);
  assert.match(urls[1], /persistir_sugerencias=true/);
});
