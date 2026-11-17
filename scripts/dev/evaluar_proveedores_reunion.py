"""Evaluación para reunión: Power BI 45/45/10, certificado ausente = cero.

Extraer con Python del repo; crear PDF con Python que disponga de reportlab.
No importa ni modifica registros de negocio.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

INICIO = date(2026, 1, 1)
FIN = date(2026, 7, 31)
SALIDA = Path("outputs/evaluacion_proveedores_20260101_20260731")


def nombre_clave(valor):
    from app.services.evaluacion_powerbi_service import nombre_clave as funcion
    return funcion(valor)


def resolver_maestro(*args):
    from app.services.evaluacion_powerbi_service import resolver_maestro as funcion
    return funcion(*args)


def puntuar(*args):
    from app.services.evaluacion_powerbi_service import puntuar as funcion
    return funcion(*args)


def clasificar(total):
    from app.services.evaluacion_powerbi_service import clasificar as funcion
    return funcion(total)


def extraer():
    from app.core.config import get_settings
    from app.services.access_read_service import _access_connection_lock, _access_read_connection
    from app.services.evaluacion_access_import_service import _normalizar_codigo

    with _access_connection_lock:
        connection = _access_read_connection()
        try:
            cur = connection.cursor()
            cur.execute("SELECT [ID_INT], [Codigo Proveedor], [PROVEEDOR], [Fecha de Entrega], "
                        "[FECHA EMISION OC], [Fecha Control], [PLAN MUESTREO], [TieneCertificado], [Estado] "
                        "FROM [CONTROL DE RECEPCION] WHERE [Fecha de Entrega]>=? AND [Fecha de Entrega]<? "
                        "ORDER BY [ID_INT]", [INICIO, FIN + timedelta(days=1)])
            cols = [c[0] for c in cur.description]
            controles = [dict(zip(cols, row)) for row in cur.fetchall()]
            cur.execute("SELECT [CODIGO], [PROVEEDOR], [RAZON SOCIAL], [DEMORA_ENTREGA], "
                        "[APLICA CERTIFICADO_CALIDAD], [EVALUAR], [INSUMO SERVICIO], [CLASIFICACION] "
                        "FROM [PROVEEDORES]")
            cols = [c[0] for c in cur.description]
            maestros = [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            connection.close()

    por_codigo = defaultdict(list)
    por_nombre = defaultdict(list)
    for m in maestros:
        clave = _normalizar_codigo(m["CODIGO"])
        if clave:
            por_codigo[clave].append(m)
            for nombre in {nombre_clave(m[c]) for c in ("PROVEEDOR", "RAZON SOCIAL")} - {""}:
                por_nombre[nombre].append(m)
    detalle, excluidos = [], []
    for fila in controles:
        codigo = _normalizar_codigo(fila["Codigo Proveedor"])
        m, asociacion = resolver_maestro(fila, por_codigo, por_nombre, _normalizar_codigo)
        motivo = asociacion if m is None else "No marcado EVALUAR"
        if m is None or not m["EVALUAR"]:
            excluidos.append({"id": fila["ID_INT"], "codigo": codigo,
                              "nombre": fila["PROVEEDOR"], "fecha": fila["Fecha de Entrega"], "motivo": motivo})
            continue
        codigo_resuelto = _normalizar_codigo(m["CODIGO"])
        calculo = puntuar(fila["PLAN MUESTREO"], fila["FECHA EMISION OC"], fila["Fecha de Entrega"],
                          m["DEMORA_ENTREGA"], fila["TieneCertificado"], m["APLICA CERTIFICADO_CALIDAD"])
        detalle.append({"id": fila["ID_INT"], "codigo": codigo_resuelto,
                        "codigo_origen": codigo, "nombre_origen": fila["PROVEEDOR"], "asociacion": asociacion,
                        "nombre": str(m["PROVEEDOR"] or m["RAZON SOCIAL"] or fila["PROVEEDOR"]),
                        "tipo": m["INSUMO SERVICIO"], "fecha": fila["Fecha de Entrega"],
                        "fecha_oc": fila["FECHA EMISION OC"], "fecha_control": fila["Fecha Control"],
                        "plan": fila["PLAN MUESTREO"], "tiene_certificado": bool(fila["TieneCertificado"]),
                        "certificado_sin_dato": fila["TieneCertificado"] is None,
                        "aplica_certificado": bool(m["APLICA CERTIFICADO_CALIDAD"]),
                        "demora": m["DEMORA_ENTREGA"], "estado": fila["Estado"], **calculo})
    if not detalle:
        raise RuntimeError("No hay recepciones evaluables; no se genera un informe vacío.")
    if len({d["id"] for d in detalle}) != len(detalle):
        raise RuntimeError("ID_INT duplicados: revisar antes de evaluar.")
    grupos = defaultdict(list)
    for fila in detalle:
        grupos[fila["codigo"]].append(fila)
    ranking = []
    for codigo, filas in grupos.items():
        n = len(filas)
        def media(campo):
            return sum((f[campo] for f in filas), Decimal(0)) / n
        total = media("total")
        ranking.append({"codigo": codigo, "nombre": filas[0]["nombre"], "tipo": filas[0]["tipo"],
                        "recepciones": n, "calidad": media("calidad"), "entrega": media("entrega"),
                        "certificado": media("certificado"), "total": total, "resultado": clasificar(total),
                        "sin_fecha_oc": sum(f["sin_fecha_oc"] for f in filas),
                        "sin_plan": sum(f["sin_plan"] for f in filas),
                        "sin_plazo": sum(f["sin_plazo"] for f in filas),
                        "con_certificado": sum(f["tiene_certificado"] for f in filas),
                        "sin_certificado": sum(not f["tiene_certificado"] for f in filas),
                        "identidad_por_nombre": sum(f["asociacion"].startswith("Nombre exacto") for f in filas),
                        "aplica_certificado": filas[0]["aplica_certificado"],
                        "rechazadas": sum(str(f["estado"]).strip().upper() == "RECHAZADO" for f in filas)})
    ranking.sort(key=lambda r: (-r["total"], r["nombre"], r["codigo"]))
    for posicion, fila in enumerate(ranking, 1):
        fila["posicion"] = posicion
    assert len(detalle) + len(excluidos) == len(controles)
    assert all(f["certificado"] == 0 for f in detalle if not f["tiene_certificado"])
    assert all(0 <= f["total"] <= 100 for f in detalle)
    assert all(INICIO <= f["fecha"].date() <= FIN for f in detalle)
    resumen = {"desde": INICIO, "hasta": FIN, "extraido": datetime.now().isoformat(timespec="seconds"),
               "metodologia": "PBIX-45-45-10-CERTIFICADO-AUSENTE-0-SIN-OC-EN-PLAZO",
               "origen": get_settings().access_db_path,
               "controles_periodo": len(controles), "controles_evaluados": len(detalle),
               "controles_excluidos": len(excluidos), "proveedores": len(ranking),
               "resultados": dict(Counter(r["resultado"] for r in ranking)),
               "promedio_recepciones": sum((f["total"] for f in detalle), Decimal(0)) / len(detalle),
               "sin_fecha_oc": sum(f["sin_fecha_oc"] for f in detalle),
               "sin_plan": sum(f["sin_plan"] for f in detalle), "sin_plazo": sum(f["sin_plazo"] for f in detalle),
               "sin_certificado": sum(not f["tiene_certificado"] for f in detalle),
               "certificado_sin_dato": sum(f["certificado_sin_dato"] for f in detalle),
               "identidad_por_nombre": sum(f["asociacion"].startswith("Nombre exacto") for f in detalle),
               "exclusiones_por_motivo": dict(Counter(f["motivo"] for f in excluidos)),
               "proveedores_con_faltantes": sum(bool(r["sin_fecha_oc"] or r["sin_plan"] or r["sin_plazo"]) for r in ranking)}
    payload = {"resumen": resumen, "ranking": ranking, "detalle": detalle, "excluidos": excluidos}
    SALIDA.mkdir(parents=True, exist_ok=True)
    def convertir(value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        raise TypeError(type(value).__name__)
    (SALIDA / "evaluacion.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=convertir), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=convertir))


def crear_pdf():
    from html import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    datos = json.loads((SALIDA / "evaluacion.json").read_text(encoding="utf-8"))
    r = datos["resumen"]
    no_aptos = [x for x in datos["ranking"] if x["resultado"] == "NO APTO"]
    nota_no_apto = "; ".join(
        f"{escape(x['nombre'])}: {x['total']:.2f} puntos, {x['sin_fecha_oc']} de {x['recepciones']} recepciones sin emisión OC"
        for x in no_aptos
    ) or "Ningún proveedor por debajo de 55 puntos."
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(name="Celda", fontName="Helvetica", fontSize=8, leading=10))
    estilos.add(ParagraphStyle(name="Nota", fontName="Helvetica", fontSize=9, leading=12))
    estilos.add(ParagraphStyle(name="EncabezadoTabla", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white))
    estilos["Title"].textColor = colors.HexColor("#17324D")
    estilos["Title"].alignment = 0
    estilos["Title"].fontSize = 23
    estilos["Title"].leading = 27
    contenido = []
    def p(texto, estilo="Nota"):
        return Paragraph(texto, estilos[estilo])
    def tabla(filas, anchos, cabecera=True):
        t = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0, hAlign="LEFT")
        comandos = [("VALIGN", (0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING", (0,0),(-1,-1),7),
                    ("RIGHTPADDING", (0,0),(-1,-1),7), ("TOPPADDING", (0,0),(-1,-1),6),
                    ("BOTTOMPADDING", (0,0),(-1,-1),6), ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
                    ("FONTSIZE",(0,0),(-1,-1),8), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F2F5F8")])]
        if cabecera:
            comandos.append(("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324D")))
        t.setStyle(TableStyle(comandos))
        return t
    contenido += [p("Evaluación de proveedores", "Title"), p("01/01/2026 al 31/07/2026", "Heading2"),
                  p("Informe para reunión | Método Power BI con certificado ausente = 0 puntos"), Spacer(1,6*mm)]
    conteos = [[p("PROVEEDORES", "EncabezadoTabla"), p("APROBADOS", "EncabezadoTabla"), p("CONDICIONALES", "EncabezadoTabla"), p("NO APTOS", "EncabezadoTabla")],
               [str(r["proveedores"]),str(r["resultados"].get("APROBADO",0)),str(r["resultados"].get("CONDICIONAL",0)),str(r["resultados"].get("NO APTO",0))]]
    contenido += [tabla(conteos,[63*mm]*4), Spacer(1,5*mm),
                  p(f"<b>{r['controles_evaluados']} recepciones evaluadas</b> de {r['controles_periodo']} del período. "
                    f"{r['controles_excluidos']} excluidas por filtro EVALUAR o coincidencia de maestro. "
                    f"Promedio global por recepción: <b>{r['promedio_recepciones']:.2f}/100</b>."),
                  p("<b>Resultado por proveedor:</b> promedio simple de los puntajes de sus recepciones, sin ponderar por cantidad. "
                    "Aprobado desde 70; Condicional desde 55 y menor que 70; No apto por debajo de 55. "
                    "Se clasifica con precisión completa y se muestran dos decimales."), Spacer(1,4*mm)]
    reglas = [[p("COMPONENTE", "EncabezadoTabla"),p("REGLA UTILIZADA", "EncabezadoTabla")],
              [p("Calidad · 45 %"),p("Muestreo Simplificada: 100; Normal: 67; Estricta: 33. Sin plan reconocido: aporte 0, como en el total del PBIX.")],
              [p("Entrega · 45 %"),p("Fecha prevista = emisión OC + plazo del proveedor. Hasta 21 días adicionales: 100; más: 33. Sin emisión OC: se considera dentro del plazo, base 100 y aporte 45 por criterio solicitado.")],
              [p("Certificado · 10 %"),p("10 puntos solo cuando aplica y la recepción tiene certificado. Sin certificado, sin dato o no aplicable: 0. No se redistribuye el peso.")]]
    contenido += [tabla(reglas,[42*mm,210*mm]), Spacer(1,4*mm), p("Datos que deben revisarse", "Heading2"),
                  p(f"{r['sin_fecha_oc']} recepciones sin emisión OC; {r['sin_plan']} sin plan reconocido; {r['sin_plazo']} sin plazo del maestro. "
                    f"Afectan a {r['proveedores_con_faltantes']} proveedores. {r['sin_certificado']} recepciones sin certificado reciben 0 puntos por ese componente."),
                  p(f"<b>Identidad de proveedores:</b> {r['identidad_por_nombre']} recepciones se asociaron por nombre exacto único debido a códigos de origen inconsistentes. "
                    "Se conservan código y nombre originales en el Excel. No se atribuyeron automáticamente recepciones de código 0 a YPF GAS."),
                  p("<b>Alcance:</b> Fecha de Entrega entre 01/01/2026 y 31/07/2026 inclusive, con EVALUAR verdadero en el maestro actual. "
                    "Recepciones y maestro consultados el 17/11/2026. El maestro no reconstruye su estado al 31/07/2026. "
                    "Se ajustan dos reglas del PBIX: certificado ausente aporta cero y sin emisión OC se considera entrega dentro del plazo. "
                    "La calificación no ejecuta bajas ni restricciones de compra automáticamente."),
                  Spacer(1,3*mm),p(f"<b>Resultado no apto a revisar:</b> {nota_no_apto}."),
                  p("El Excel adjunto contiene ranking, recepciones con fórmulas, exclusiones y metodología."), PageBreak(),
                  p("Ranking del período", "Title"),p("Calidad /45 · Entrega /45 · Certificado /10 · Total /100. OC y Plan indican recepciones con datos faltantes."),Spacer(1,4*mm)]
    cab = ["Pos.","Código","Proveedor","Rec.","Calidad","Entrega","Certif.","Total","Resultado","OC","Plan"]
    filas = [[p(c,"EncabezadoTabla") for c in cab]]
    for x in datos["ranking"]:
        filas.append([str(x["posicion"]),escape(x["codigo"]),p(escape(x["nombre"]),"Celda"),str(x["recepciones"]),
                      f"{x['calidad']:.2f}",f"{x['entrega']:.2f}",f"{x['certificado']:.2f}",f"{x['total']:.2f}",p(x["resultado"],"Celda"),str(x["sin_fecha_oc"]),str(x["sin_plan"])])
    ranking_tabla = tabla(filas,[12*mm,17*mm,67*mm,12*mm,19*mm,19*mm,18*mm,18*mm,29*mm,12*mm,12*mm])
    ranking_tabla.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    contenido.append(ranking_tabla)
    destino=SALIDA / "Evaluacion_proveedores_2026_01_01_al_07_31.pdf"
    def pie(canvas, doc):
        canvas.setFont("Helvetica",8)
        canvas.setFillColor(colors.HexColor("#536476"))
        canvas.drawString(15*mm,10*mm,"Período 01/01/2026 - 31/07/2026 | Elaborado 17/11/2026")
        canvas.drawRightString(282*mm,10*mm,f"Página {doc.page}")
    SimpleDocTemplate(str(destino),pagesize=landscape(A4),leftMargin=15*mm,rightMargin=15*mm,
                      topMargin=14*mm,bottomMargin=18*mm).build(contenido,onFirstPage=pie,onLaterPages=pie)
    print(destino)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",action="store_true")
    args=parser.parse_args()
    crear_pdf() if args.pdf else extraer()
