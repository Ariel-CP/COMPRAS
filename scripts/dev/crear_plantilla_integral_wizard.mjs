// Plantilla base. La API completa catálogo y período con las dependencias Python existentes.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const contract = JSON.parse(await fs.readFile(path.join(root, 'app/resources/wizard_oc_columnas.json'), 'utf8'));
const out = path.join(root, 'outputs/wizard_oc_20261113');
await fs.mkdir(out, { recursive: true });
const wb = Workbook.create();
const instructions = wb.worksheets.add('Instrucciones');
instructions.showGridLines = false;
instructions.getRange('A1:B19').format.font = { name: 'Arial', size: 11 };
instructions.getRange('A:A').format.columnWidth = 25;
instructions.getRange('B:B').format.columnWidth = 105;
instructions.getRange('A2').values = [['Requerimiento de materiales']];
instructions.getRange('A2').format.font = { name: 'Arial', size: 16, bold: true, color: '#0B5CAB' };
const help = [
  ['1. Parámetros', 'Elegí año y mes. Completá las tres fechas de corte. Stock MP corresponde al mes anterior al plan.'],
  ['2. Plan_PT', 'Completá cantidades del plan para cada producto terminado. Escribí 0 si no tiene producción prevista.'],
  ['3. Stock_MP', 'Completá el stock de materiales y componentes en sus unidades del catálogo. No mezcles unidades.'],
  ['4. Stock_PT', 'Completá el stock disponible de cada producto terminado. Una celda vacía no equivale a cero.'],
  ['5. Deuda_Clientes', 'Completá las cantidades pendientes de fabricar o entregar de cada PT. Escribí 0 cuando corresponda.'],
  ['6. LAF_Solicitado', 'Listá pedidos ya solicitados, con proveedor, cantidades y estado. Podés repetir un código en pedidos distintos.'],
  ['Sin pedidos LAF', 'Si no hay pedidos LAF, dejá la hoja vacía y escribí SI en sin_laf, en Parametros.'],
  ['Datos existentes', 'La descarga muestra los valores guardados disponibles. Revisalos antes de volver a subir el archivo.'],
  ['Qué se guarda', 'Se actualizan plan, stock MP, stock PT y deuda de los códigos listados. Se reemplaza la lista LAF completa del período.'],
  ['Antes de guardar', 'La pantalla valida todas las hojas y muestra un resumen. Confirmá para guardar y calcular en una sola operación.'],
  ['Cantidades', 'Usá números de Excel, hasta 6 decimales, sin negativos. No uses fórmulas. Cero es válido y debe escribirse.'],
  ['Códigos y unidades', 'Conservá códigos como texto y unidades del catálogo. Nombre es solo referencia y no modifica artículos.'],
  ['LAF parcial', 'cantidad_total mantiene la regla actual del Wizard. No representa un saldo recibido independiente.'],
  ['Datos del sistema', 'Catálogo, unidades y MBOM se toman del sistema. Deben estar configurados antes del cálculo.'],
  ['Resultado', 'Se calcula una propuesta sin guardar sugerencias ni emitir OC. El archivo no se envía a un proveedor de IA.'],
];
instructions.getRange('A4:B18').values = help;
instructions.getRange('A4:A18').format.font = { name: 'Arial', size: 11, bold: true };
instructions.getRange('B4:B18').format.wrapText = true;
instructions.getRange('A4:B18').format.rowHeight = 38;
instructions.getRange('A4:B18').format.verticalAlignment = 'center';
for (const [name, headers] of Object.entries(contract)) {
  const sheet = wb.worksheets.add(name);
  sheet.showGridLines = false;
  const width = headers.length;
  const col = String.fromCharCode(64 + width);
  sheet.getRange(`A1:${col}1`).values = [headers];
  sheet.getRange(`A1:${col}21`).format.font = { name: 'Arial', size: 11 };
  sheet.getRange(`A1:${col}1`).format = { fill: '#0B5CAB', font: { name: 'Arial', size: 11, bold: true, color: '#FFFFFF' }, rowHeight: 38, wrapText: true, horizontalAlignment: 'center', verticalAlignment: 'center' };
  sheet.getRange(`A2:${col}21`).format.rowHeight = 23;
  sheet.getRange(`A1:${col}21`).format.columnWidth = 24;
  sheet.freezePanes.freezeRows(1);
  sheet.getRange('A2:A21').setNumberFormat('@');
  sheet.getRange(`A2:${col}21`).format.verticalAlignment = 'center';
  sheet.getRange('A2:A21').format.horizontalAlignment = 'left';
  if (name === 'Parametros') {
    sheet.getRange('A2:G2').values = [[1, null, null, null, null, null, 'NO']];
    sheet.getRange('A2:G2').format.fill = '#FFF2CC';
    sheet.getRange('D2:F2').setNumberFormat('dd/mm/yyyy');
    sheet.getRange('B2:C2').setNumberFormat('0');
    sheet.getRange('G2').dataValidation = { rule: { type: 'list', values: ['SI', 'NO'] } };
  } else if (name === 'LAF_Solicitado') {
    sheet.getRange('B:B').format.columnWidth = 60;
    sheet.getRange('B2:B21').format.wrapText = true;
    sheet.getRange('E2:G21').setNumberFormat('#,##0.######');
    sheet.getRange('E2:K21').format.fill = '#FFF2CC';
    sheet.getRange('H2:I21').setNumberFormat('dd/mm/yyyy');
    sheet.getRange('J2:J21').dataValidation = { rule: { type: 'list', values: ['PENDIENTE', 'PARCIAL', 'RECIBIDO', 'CANCELADO'] } };
    sheet.getRange('K:K').format.columnWidth = 42;
  } else {
    sheet.getRange('B:B').format.columnWidth = 60;
    sheet.getRange('B2:B21').format.wrapText = true;
    sheet.getRange('C:C').format.columnWidth = 15;
    sheet.getRange('D2:D21').format.fill = '#FFF2CC';
    sheet.getRange('D2:D21').setNumberFormat('#,##0.######');
  }
}
wb.recalculate();
console.log((await wb.inspect({ kind: 'sheet', include: 'name', maxChars: 1000 })).ndjson);
for (const name of process.argv.includes('--sin-vistas') ? [] : ['Instrucciones', ...Object.keys(contract)]) {
  const preview = await wb.render({ sheetName: name, range: name === 'Instrucciones' ? 'A1:B18' : `A1:${String.fromCharCode(64 + contract[name].length)}6`, scale: 1.5, format: 'png' });
  await fs.writeFile(path.join(out, `${name}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(path.join(root, 'app/resources/plantilla_integral_wizard_oc.xlsx'));
await file.save(path.join(out, 'plantilla_integral_wizard_oc.xlsx'));
console.log('Plantilla base y vistas previas exportadas.');
