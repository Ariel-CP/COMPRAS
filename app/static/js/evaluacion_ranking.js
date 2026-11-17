(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = $('ranking-form');
  if (!form) return;
  let ranking = null, rankingRequest = null, historyRequest = null;
  let rankVersion = 0, historyVersion = 0;
  const number = value => Number(value).toLocaleString('es-AR', {maximumFractionDigits: 2});
  const dateLabel = value => value.split('-').reverse().join('/');
  const label = value => ({APROBADO: 'Aprobado', CONDICIONAL: 'Condicional', 'NO APTO': 'No apto'}[value] || value);
  const text = (tag, value, className) => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  function svgNode(tag, attrs = {}, value) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, val]) => node.setAttribute(key, String(val)));
    if (value !== undefined) node.textContent = value;
    return node;
  }
  function axes(svg, left, top, width, height) {
    for (const mark of [0, 25, 50, 75, 100]) {
      const x = left + width * mark / 100;
      svg.append(svgNode('line', {x1:x, x2:x, y1:top, y2:top+height, class:'eje'}));
      svg.append(svgNode('text', {x, y:top-9, 'text-anchor':'middle', 'font-size':11}, mark));
    }
  }
  function bars(containerId, rows, color) {
    const container = $(containerId);
    container.replaceChildren();
    if (!rows.length) { container.append(text('p', 'Sin proveedores en el período.')); return; }
    const left=245, width=300, top=30, rowHeight=30;
    const svg = svgNode('svg', {viewBox:`0 0 620 ${top+rows.length*rowHeight+10}`, role:'img', 'aria-label':containerId.includes('mejores') ? 'Puntaje de los mejores proveedores' : 'Puntaje de los peores proveedores'});
    axes(svg, left, top, width, rows.length*rowHeight);
    rows.forEach((r,i) => {
      const y=top+i*rowHeight, full=`${r.codigo} · ${r.nombre}`;
      const group=svgNode('g', {role:'button', tabindex:0, 'aria-label':`Ver historia de ${full}, ${number(r.total)} puntos`});
      group.append(svgNode('title', {}, `${full}: ${number(r.total)} puntos, ${r.recepciones} recepciones`));
      group.append(svgNode('text', {x:left-10,y:y+17,'text-anchor':'end','font-size':11},full.length>34 ? full.slice(0,32)+'…' : full));
      group.append(svgNode('rect', {x:left,y:y+4,width:width*Number(r.total)/100,height:20,rx:3,fill:color}));
      group.append(svgNode('text', {x:left+width*Number(r.total)/100+7,y:y+18,'font-size':11},number(r.total)));
      group.addEventListener('click', () => selectProvider(r.codigo));
      group.addEventListener('keydown', event => { if (event.key==='Enter' || event.key===' ') {event.preventDefault();selectProvider(r.codigo);} });
      svg.append(group);
    });
    container.append(svg);
  }
  function historyChart(rows) {
    const container=$('grafico-historia');
    container.replaceChildren();
    if (!rows.length) return;
    const width=900, height=290, left=55, right=30, top=25, bottom=55;
    const plotWidth=width-left-right, plotHeight=height-top-bottom;
    const x=i => left+(rows.length===1 ? plotWidth/2 : plotWidth*i/(rows.length-1));
    const y=value => top+plotHeight*(1-Number(value)/100);
    const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Evolución del puntaje total, escala de cero a cien'});
    for (const value of [0,25,50,55,70,100]) {
      svg.append(svgNode('line',{x1:left,x2:width-right,y1:y(value),y2:y(value),class:value===55||value===70 ? 'eje umbral':'eje'}));
      svg.append(svgNode('text',{x:left-10,y:y(value)+4,'text-anchor':'end','font-size':11},value));
    }
    svg.append(svgNode('polyline',{points:rows.map((r,i)=>`${x(i)},${y(r.total)}`).join(' '),fill:'none',stroke:'#17689b','stroke-width':3}));
    rows.forEach((r,i)=>{
      const point=svgNode('circle',{cx:x(i),cy:y(r.total),r:4,fill:'#17689b'});
      point.append(svgNode('title',{},`${r.periodo}: ${number(r.total)} puntos, ${r.recepciones} recepciones`));svg.append(point);
      if (i===0 || i===rows.length-1 || i%Math.max(1,Math.ceil(rows.length/12))===0)
        svg.append(svgNode('text',{x:x(i),y:height-22,'text-anchor':'middle','font-size':11},r.periodo));
    });
    container.append(svg);
  }
  function resultCell(value) {return text('td',label(value),'resultado-'+value.toLowerCase().replaceAll(' ','-'));}
  function table(id, rows) {
    const body=$(id);body.replaceChildren();
    const showRejects=id==='tabla-peores';
    if (!rows.length) {const cell=text('td','Sin proveedores en el período.');cell.colSpan=showRejects?6:5;const row=document.createElement('tr');row.append(cell);body.append(row);return;}
    rows.forEach(r=>{
      const row=document.createElement('tr');
      row.append(text('td',`${r.codigo} · ${r.nombre}`),text('td',number(r.total)),text('td',r.recepciones),resultCell(r.resultado));
      if(showRejects){
        const rejected=document.createElement('td');
        if(r.rechazos){
          const details=document.createElement('details');details.append(text('summary',`${r.rechazos} rechazo${r.rechazos===1?'':'s'} · ver controles`));
          const list=document.createElement('ul');
          (r.controles_rechazados||[]).forEach(control=>{
            const item=document.createElement('li'),link=text('a',`Control ${control.id} · ${dateLabel(control.fecha)}`);
            link.href=`/ui/recepcion/historial-access?access_id=${encodeURIComponent(control.id)}`;link.target='_blank';link.rel='noopener';item.append(link);list.append(item);
          });details.append(list);rejected.append(details);
        }else rejected.textContent='Sin rechazos';
        row.append(rejected);
      }
      const cell=document.createElement('td'), button=text('button','Ver historia','btn-accion');button.type='button';
      button.addEventListener('click',()=>selectProvider(r.codigo));cell.append(button);row.append(cell);body.append(row);
    });
  }
  function fillProviders() {
    const select=$('historial-proveedor'), selected=select.value;
    const term=$('historial-buscar').value.trim().toLocaleLowerCase('es');
    select.replaceChildren(new Option('Seleccionar…',''));
    (ranking?.proveedores || []).filter(r=>r.codigo===selected || `${r.codigo} ${r.nombre}`.toLocaleLowerCase('es').includes(term))
      .forEach(r=>select.append(new Option(`${r.codigo} · ${r.nombre}`,r.codigo)));
    select.value=selected;
  }
  function clearHistory() {
    historyVersion+=1;historyRequest?.abort();$('historial-resultados').hidden=true;
    $('historial-mensaje').textContent='Seleccioná un proveedor y presioná Ver historia.';
  }
  function invalidate() {
    rankVersion+=1;rankingRequest?.abort();clearHistory();ranking=null;
    $('ranking-resultados').hidden=true;$('ranking-exportar').disabled=true;$('ranking-imprimir').disabled=true;
    $('ranking-email').disabled=true;$('ranking-email-mensaje').textContent='';
  }
  async function jsonResponse(response) {
    if (response.status===401) throw new Error('La sesión venció. Iniciá sesión nuevamente.');
    if (response.status===403) throw new Error('Tu usuario no tiene permiso para esta consulta.');
    const data=await response.json();
    if (!response.ok) throw new Error(typeof data.detail==='string' ? data.detail : 'No se pudo consultar. Revisá el período.');
    return data;
  }
  form.addEventListener('submit',async event=>{
    event.preventDefault();invalidate();
    const version=rankVersion, desde=$('ranking-desde').value,hasta=$('ranking-hasta').value;
    const message=$('ranking-mensaje');message.className='';
    if (!desde||!hasta||desde>hasta) {message.textContent='Seleccioná un período válido: Desde no puede ser posterior a Hasta.';message.className='ranking-error';return;}
    rankingRequest=new AbortController();$('ranking-analizar').disabled=true;message.textContent='Consultando Access y calculando el período…';
    try {
      const data=await jsonResponse(await fetch(`/api/evaluaciones/powerbi/ranking?${new URLSearchParams({desde,hasta})}`,{signal:rankingRequest.signal}));
      if (version!==rankVersion) return;
      ranking=data;$('ranking-resultados').hidden=false;
      $('ranking-periodo').textContent=`Período evaluado: ${dateLabel(data.desde)} al ${dateLabel(data.hasta)} · Fecha de Entrega · Consultado ${new Date(data.calculado_en).toLocaleString('es-AR')}`;
      const kpis=$('ranking-kpis');kpis.replaceChildren();
      for (const [title,value] of [['Proveedores',data.resumen.proveedores],['Aprobados',data.resumen.resultados.APROBADO||0],['Condicionales',data.resumen.resultados.CONDICIONAL||0],['No aptos',data.resumen.resultados['NO APTO']||0]]) {
        const card=document.createElement('div');card.className='ranking-kpi';card.append(text('span',title),text('strong',value));kpis.append(card);
      }
      const summary=data.resumen, notes=$('ranking-advertencias');notes.replaceChildren();
      for (const line of [
        `${summary.controles_evaluados} recepciones evaluadas de ${summary.controles_periodo}; ${summary.controles_excluidos} excluidas.`,
        `${summary.sin_fecha_oc} sin emisión OC (consideradas dentro del plazo por criterio solicitado); ${summary.sin_plan} sin plan reconocido; ${summary.sin_plazo} sin plazo. Las fechas faltantes no se completan.`,
        `${summary.identidad_por_nombre} recepciones asociadas por nombre exacto único por código inconsistente. No se atribuye automáticamente código 0 a YPF GAS.`,
        ...Object.entries(summary.exclusiones_por_motivo).map(([reason,count])=>`Excluidas: ${reason}: ${count}.`),
      ]) notes.append(text('p',line));
      bars('grafico-mejores',data.mejores_20,'#2a8054');bars('grafico-peores',data.peores_20,'#bb6146');
      table('tabla-mejores',data.mejores_20);table('tabla-peores',data.peores_20);
      $('historial-buscar').value='';$('historial-proveedor').replaceChildren();fillProviders();
      $('ranking-exportar').disabled=!data.proveedores.length;$('ranking-imprimir').disabled=false;
      $('ranking-email').disabled=!data.proveedores.length;
      message.textContent=data.proveedores.length ? 'Ranking actualizado. Elegí un proveedor para consultar su historia.' : 'No hay proveedores evaluables en ese período.';
    } catch(error) {if (error.name!=='AbortError'&&version===rankVersion){message.textContent=error.message;message.className='ranking-error';}}
    finally {if(version===rankVersion)$('ranking-analizar').disabled=false;}
  });
  for (const id of ['ranking-desde','ranking-hasta']) $(id).addEventListener('change',()=>{invalidate();$('ranking-analizar').disabled=false;$('ranking-mensaje').textContent='Período modificado. Presioná Analizar período para actualizar.';});
  function selectProvider(code) {
    if (!ranking) return;
    $('historial-buscar').value='';fillProviders();$('historial-proveedor').value=code;
    $('historial-form').requestSubmit();$('historial-seccion').scrollIntoView({behavior:'smooth',block:'start'});
  }
  $('historial-buscar').addEventListener('input',fillProviders);
  for(const id of ['historial-proveedor','historial-alcance','historial-grupo']) $(id).addEventListener('change',clearHistory);
  $('historial-form').addEventListener('submit',async event=>{
    event.preventDefault();clearHistory();if(!ranking)return;
    const codigo=$('historial-proveedor').value;if(!codigo)return;
    const version=historyVersion, message=$('historial-mensaje');message.className='';
    const params=new URLSearchParams({hasta:ranking.hasta,agrupacion:$('historial-grupo').value});
    if($('historial-alcance').value==='periodo')params.set('desde',ranking.desde);
    historyRequest=new AbortController();message.textContent='Consultando la historia del proveedor…';
    try{
      const data=await jsonResponse(await fetch(`/api/evaluaciones/powerbi/proveedor/${encodeURIComponent(codigo)}/historial?${params}`,{signal:historyRequest.signal}));
      if(version!==historyVersion)return;
      if(!data.serie.length){message.textContent='No hay recepciones evaluables de ese proveedor en el alcance seleccionado.';return;}
      $('historial-resultados').hidden=false;$('historial-titulo').textContent=`${data.codigo} · ${data.proveedor.nombre}`;
      $('historial-resumen').textContent=`${data.desde ? dateLabel(data.desde) : 'Todo lo disponible'} al ${dateLabel(data.hasta)} · ${data.proveedor.recepciones} recepciones · Promedio del alcance: ${number(data.proveedor.total)} · ${label(data.proveedor.resultado)}. Sin emisión OC: ${data.proveedor.sin_fecha_oc}.`;
      historyChart(data.serie);const body=$('tabla-historia');body.replaceChildren();
      data.serie.forEach(r=>{const row=document.createElement('tr');row.append(text('td',r.periodo));for(const key of ['calidad','entrega','certificado','total'])row.append(text('td',number(r[key])));row.append(resultCell(r.resultado),text('td',r.recepciones),text('td',r.sin_fecha_oc),text('td',r.sin_plan));body.append(row);});
      message.textContent='Historia recalculada. Los períodos sin recepciones no generan calificación.';
    }catch(error){if(error.name!=='AbortError'&&version===historyVersion){message.textContent=error.message;message.className='ranking-error';}}
  });
  $('ranking-exportar').addEventListener('click',()=>{
    if(!ranking)return;
    const quote=value=>{let s=String(value??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
    const rows=[['Desde','Hasta','Código','Proveedor','Recepciones','Calidad45','Entrega45','Certificado10','Total100','Resultado','SinFechaOC','IdentidadPorNombre'],
      ...ranking.proveedores.map(r=>[ranking.desde,ranking.hasta,r.codigo,r.nombre,r.recepciones,r.calidad,r.entrega,r.certificado,r.total,r.resultado,r.sin_fecha_oc,r.identidad_por_nombre])];
    const blob=new Blob(['\uFEFF'+rows.map(row=>row.map(quote).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'});
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`ranking_${ranking.desde}_${ranking.hasta}.csv`;a.click();URL.revokeObjectURL(url);
  });
  $('ranking-imprimir').addEventListener('click',()=>window.print());
  $('ranking-email').addEventListener('click',()=>{
    if(!ranking?.proveedores.length)return;
    try {
      const report=$('ranking-resultados').cloneNode(true);
      report.querySelectorAll('[hidden],form,button,#historial-mensaje').forEach(node=>node.remove());
      if($('historial-resultados').hidden)report.querySelector('#historial-seccion')?.remove();
      const method=document.querySelector('.ranking-metodo').cloneNode(true);method.open=true;
      const html='<!doctype html><html lang="es"><meta charset="utf-8"><title>Evaluación de proveedores</title><style>body{font:14px Arial;color:#17324d;margin:24px}table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ccd6df;padding:8px;text-align:left}th{background:#edf2f7}svg{width:100%;max-width:900px;height:auto}svg text{fill:#34495d}.eje{stroke:#d7e0e8}.umbral{stroke-dasharray:5 5}.ranking-kpis{display:flex;gap:32px}.ranking-kpi strong{display:block;font-size:24px}.ranking-advertencias{background:#fff8eb;padding:12px}.tabla-scroll{overflow:auto}@media print{article{break-before:page}}</style><body><h1>Evaluación de proveedores</h1>'+method.outerHTML+report.outerHTML+'</body></html>';
      const draft=RankingEmail.createDraft({desde:ranking.desde,hasta:ranking.hasta,html});
      const url=URL.createObjectURL(new Blob([draft],{type:'message/rfc822'}));
      const a=document.createElement('a');a.href=url;a.download=`informe_proveedores_${ranking.desde}_${ranking.hasta}.eml`;a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      $('ranking-email-mensaje').textContent='Borrador descargado (.eml). Abrilo en Outlook u otro cliente compatible, completá el destinatario y enviá. Incluye el informe HTML con gráficos y la historia si está visible. Todavía no se envió ningún correo.';
    } catch(error) {$('ranking-email-mensaje').textContent='No se pudo preparar el email. '+error.message;}
  });
  form.requestSubmit();
})();
