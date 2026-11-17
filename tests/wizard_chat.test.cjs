const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

async function setup(reply) {
  const elements = new Map();
  const element = () => ({ value: '', hidden: true, disabled: false, listeners: {},
    addEventListener(name, fn) { this.listeners[name] = fn; },
    appendChild() {}, replaceChildren() {}, textContent: '' });
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const pane = element();
  const document = { ...element(), getElementById: (id) => get(id.replace('wizard-chat-', '')),
    createElement: element, createTextNode: (s) => s, querySelectorAll: () => [pane] };
  const calls = [];
  const actions = [];
  const context = { anio: 2026, mes: 12, paso: 1, productos_plan: 0, registros_stock_pt: 0, registros_deuda: 0 };
  const runtime = { window: {}, document, fetch: async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => options?.method === 'POST' ? await reply() : { disponible: true, modelo: 'ficticio' } };
  } };
  vm.runInNewContext(readFileSync('app/static/js/wizard_chat.js', 'utf8'), runtime);
  runtime.window.iniciarWizardChat({ contexto: () => ({ ...context }), aplicar: async (p) => { actions.push(p); return true; } });
  await new Promise((resolve) => setImmediate(resolve));
  get('pregunta').value = 'Necesito materiales';
  return { get, calls, actions, pane, context,
    prepare: () => get('form').listeners.submit({ preventDefault() {} }),
    send: () => get('enviar').listeners.click(), apply: () => get('aplicar').listeners.click() };
}

test('preview no envía; envío confirmado no ejecuta hasta aplicar', async () => {
  const s = await setup(async () => ({ mensaje: 'Carguemos el plan', accion: 'cargar_plan', anio: null, mes: null }));
  s.prepare();
  assert.equal(s.calls.length, 1); // solo estado
  assert.match(s.get('envio').textContent, /Necesito materiales/);
  await s.send();
  assert.equal(s.actions.length, 0);
  const payload = JSON.parse(s.calls[1].options.body);
  assert.equal(payload.confirmar_envio, true);
  assert.equal(payload.contexto.productos_plan, 0);
  await s.apply();
  assert.equal(s.actions.length, 1);
});

test('editar datos después de la propuesta impide aplicarla', async () => {
  const s = await setup(async () => ({ mensaje: 'Calcular', accion: 'simular' }));
  s.prepare(); await s.send();
  s.pane.listeners.input();
  await s.apply();
  assert.equal(s.actions.length, 0);
});

test('cambio durante la consulta invalida respuesta aunque los contadores sean iguales', async () => {
  let resolve;
  const s = await setup(() => new Promise((r) => { resolve = r; }));
  s.prepare();
  const pending = s.send();
  await new Promise((r) => setImmediate(r));
  s.pane.listeners.change();
  resolve({ mensaje: 'Importar', accion: 'importar_mp' });
  await pending;
  await s.apply();
  assert.equal(s.actions.length, 0);
  assert.match(s.get('estado').textContent, /estado anterior/);
});

test('acción fuera de la lista no se ofrece para ejecutar', async () => {
  const s = await setup(async () => ({ mensaje: '<script>texto</script>', accion: 'ejecutar_sql' }));
  s.prepare(); await s.send(); await s.apply();
  assert.equal(s.actions.length, 0);
  assert.equal(s.get('propuesta').hidden, true);
});
