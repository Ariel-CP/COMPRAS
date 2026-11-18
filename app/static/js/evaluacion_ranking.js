(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = $('ranking-form');
  if (!form) return;
  let ranking = null, rankingRequest = null, historyRequest = null;
  let rankVersion = 0, historyVersion = 0;
  const number = value => Number(value).toLocaleString('es-AR', {maximumFractionDigits: 2});
  const scoreNumber = value => Number(value).toLocaleString('es-AR', {minimumFractionDigits:2,maximumFractionDigits:2});
  const referenceKey = 'evaluacion-ranking-referencia-v1';
  let reference = {periodo:$('ranking-ref-periodo').value,valor:Number($('ranking-ref-valor').value)};
  try {
    const saved=JSON.parse(localStorage.getItem(referenceKey));
    if(saved && typeof saved.periodo==='string' && saved.periodo.trim() && saved.periodo.length<=100 && typeof saved.valor==='number' && Number.isFinite(saved.valor) && saved.valor>=0 && saved.valor<=100) reference=saved;
  } catch {}
  $('ranking-ref-periodo').value=reference.periodo;$('ranking-ref-valor').value=reference.valor;
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
      const y = top + height * (1 - mark / 100);
      svg.append(svgNode('line', {x1:left, x2:left+width, y1:y, y2:y, class:'eje'}));
      svg.append(svgNode('text', {x:left-12, y:y+4, 'text-anchor':'end', 'font-size':12}, mark));
    }
  }
  function generalScore(summary) {
    const container=$('ranking-medidor');container.replaceChildren();
    const score=summary.puntaje_general==null ? null : Number(summary.puntaje_general);
    const category=summary.resultado_general;
    $('ranking-referencia-periodo').textContent=reference.periodo;
    $('ranking-referencia-valor').textContent=`${scoreNumber(reference.valor)} / 100`;
    if(score===null || !Number.isFinite(score)) {
      container.append(text('p','Sin recepciones evaluables para calcular el promedio general.'));
      $('ranking-general-resultado').textContent='Sin calificación';
      $('ranking-general-variacion').textContent='Sin comparación disponible.';
      return;
    }
    const color=category==='APROBADO' ? '#24613a' : category==='CONDICIONAL' ? '#8a4c00' : '#922b2b';
    const svg=svgNode('svg',{viewBox:'0 0 340 220',role:'img','aria-label':`Promedio general: ${scoreNumber(score)} de 100. ${label(category)}. Referencia histórica: ${scoreNumber(reference.valor)}.`});
    const path='M 30 170 A 140 140 0 0 1 310 170';
    svg.append(svgNode('path',{d:path,fill:'none',stroke:'#dce4eb','stroke-width':28}));
    svg.append(svgNode('path',{d:path,fill:'none',stroke:color,'stroke-width':28,pathLength:100,'stroke-dasharray':`${score} 100`}));
    const angle=Math.PI*(1-reference.valor/100);
    const marker=svgNode('line',{x1:170+120*Math.cos(angle),y1:170-120*Math.sin(angle),x2:170+160*Math.cos(angle),y2:170-160*Math.sin(angle),stroke:'#17324d','stroke-width':3});
    marker.append(svgNode('title',{},`Referencia histórica: ${scoreNumber(reference.valor)}`));svg.append(marker);
    svg.append(svgNode('text',{x:170,y:125,'text-anchor':'middle','font-size':38,'font-weight':700,fill:color},`${scoreNumber(score)} %`));
    svg.append(svgNode('text',{x:170,y:152,'text-anchor':'middle','font-size':13,fill:'#526576'},'puntaje sobre 100'));
    svg.append(svgNode('text',{x:22,y:205,'font-size':12},'0'));
    svg.append(svgNode('text',{x:318,y:205,'text-anchor':'end','font-size':12},'100'));
    container.append(svg);
    $('ranking-general-resultado').textContent=label(category);
    const difference=score-reference.valor;
    const delta=Math.abs(difference)<0.005 ? 0 : difference;
    $('ranking-general-variacion').textContent=`Diferencia respecto de la referencia: ${delta>0 ? '+' : ''}${scoreNumber(delta)} puntos sobre 100.`;
  }
  function bars(containerId, rows, color) {
    const container = $(containerId);
    container.replaceChildren();
    if (!rows.length) { container.append(text('p', 'Sin proveedores en el período.')); return; }
    const left=60, width=1160, top=35, plotHeight=300, slot=width/rows.length;
    const svg = svgNode('svg', {viewBox:'0 0 1280 550', class:'ranking-barras', role:'img', 'aria-label':containerId.includes('mejores') ? 'Puntaje de los mejores proveedores' : 'Puntaje de los peores proveedores'});
    axes(svg, left, top, width, plotHeight);
    rows.forEach((r,i) => {
      const x=left+(i+0.5)*slot, barHeight=plotHeight*Number(r.total)/100, y=top+plotHeight-barHeight, full=`${r.codigo} · ${r.nombre}`;
      const group=svgNode('g', {role:'button', tabindex:0, 'aria-label':`Ver historia de ${full}, ${number(r.total)} puntos`});
      group.append(svgNode('title', {}, `${full}: ${number(r.total)} puntos, ${r.recepciones} recepciones`));
      const labelY=top+plotHeight+18;
      group.append(svgNode('text', {x,y:labelY,transform:`rotate(-50 ${x} ${labelY})`,'text-anchor':'end','font-size':12},full.length>30 ? full.slice(0,28)+'…' : full));
      group.append(svgNode('rect', {x:x-Math.min(38,slot*0.65)/2,y,width:Math.min(38,slot*0.65),height:barHeight,rx:3,fill:color}));
      group.append(svgNode('text', {x,y:y-8,'text-anchor':'middle','font-size':12},number(r.total)));
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
      generalScore(data.resumen);
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
        `Certificados: ${summary.con_certificado} recepciones con evidencia; ${summary.certificado_por_adjunto} con adjunto y ${summary.certificado_por_nota} con nota explícita (pueden coincidir). La leyenda genérica de cumplimiento no cuenta.`,
        ...(summary.certificado_conflictos ? [`Revisar ${summary.certificado_conflictos} ${summary.certificado_conflictos===1 ? 'recepción' : 'recepciones'} con evidencia de certificado y nota de ausencia: se reconoce la casilla o el adjunto, conservando la contradicción de origen.`] : []),
        ...Object.entries(summary.exclusiones_por_motivo).map(([reason,count])=>`Excluidas: ${reason}: ${count}.`),
      ]) notes.append(text('p',line));
      if (summary.controles_certificado_conflicto?.length) {
        const details=document.createElement('details');
        details.append(text('summary','Ver controles con nota de ausencia y evidencia de certificado (requiere permiso de historial Access)'));
        const list=document.createElement('ul');
        summary.controles_certificado_conflicto.forEach(control=>{
          const item=document.createElement('li'),link=text('a',`${control.proveedor} · Control ${control.id} · ${dateLabel(control.fecha)}`);
          link.href=`/ui/recepcion/historial-access?access_id=${encodeURIComponent(control.id)}`;link.target='_blank';link.rel='noopener';item.append(link);list.append(item);
        });
        details.append(list);notes.append(details);
      }
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
  function qualityReport() {
    let html=RankingInformeCalidad.createReport(ranking);
    if(!$('historial-resultados').hidden) {
      const history=$('historial-resultados').cloneNode(true);
      history.querySelectorAll('[hidden],form,button').forEach(node=>node.remove());
      html=html.replace('</body>','<section class="quality-history"><h2>Historia del proveedor</h2>'+history.outerHTML+'</section><style>.quality-history{background:white;max-width:1440px;margin:20px auto;padding:24px;font-size:13px}.quality-history svg{width:100%;height:auto;max-width:1000px}.quality-history .eje{stroke:#d7e0e8}.quality-history table{border-collapse:collapse;width:100%}.quality-history th,.quality-history td{padding:6px;border:1px solid #ccd6df}@media print{.quality-history{break-before:page;margin:0;padding:0}}</style></body>');
    }
    return html;
  }
  $('ranking-imprimir').addEventListener('click',()=>{
    if(!ranking?.proveedores.length)return;
    try {
      const html=qualityReport(),preview=window.open('','_blank');
      if(!preview)throw new Error('Permití las ventanas emergentes para abrir el informe.');
      preview.opener=null;preview.document.open();preview.document.write(html);preview.document.close();
    } catch(error) {$('ranking-mensaje').textContent=error.message;}
  });
  $('ranking-referencia-form').addEventListener('submit',event=>{
    event.preventDefault();
    const periodo=$('ranking-ref-periodo').value.trim(),valor=Number($('ranking-ref-valor').value);
    if(!periodo || $('ranking-ref-valor').value==='' || !Number.isFinite(valor) || valor<0 || valor>100)return;
    reference={periodo,valor};
    try{localStorage.setItem(referenceKey,JSON.stringify(reference));}catch{}
    if(ranking)generalScore(ranking.resumen);
  });
  let detailsBeforePrint=false;
  window.addEventListener('beforeprint',()=>{detailsBeforePrint=$('ranking-detalles').open;$('ranking-detalles').open=true;});
  window.addEventListener('afterprint',()=>{$('ranking-detalles').open=detailsBeforePrint;});
  $('ranking-email').addEventListener('click',()=>{
    if(!ranking?.proveedores.length)return;
    try {
      const html=qualityReport();
      const draft=RankingEmail.createDraft({desde:ranking.desde,hasta:ranking.hasta,html});
      const url=URL.createObjectURL(new Blob([draft],{type:'message/rfc822'}));
      const a=document.createElement('a');a.href=url;a.download=`informe_proveedores_${ranking.desde}_${ranking.hasta}.eml`;a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      $('ranking-email-mensaje').textContent='Borrador descargado (.eml). Abrilo en Outlook u otro cliente compatible, completá el destinatario y enviá. Incluye el Informe de Calidad con el formato horizontal y la historia si está visible. Todavía no se envió ningún correo.';
    } catch(error) {$('ranking-email-mensaje').textContent='No se pudo preparar el email. '+error.message;}
  });
  form.requestSubmit();
})();
