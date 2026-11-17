"""Extrae fórmulas y contrasta valores guardados, sin refrescar ni editar el PBIX.

Dependencia de diagnóstico: pbixray (no forma parte de la API).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from pbixray import PBIXRay


def inspeccionar(archivo: Path, salida: Path) -> dict:
    huella = hashlib.sha256(archivo.read_bytes()).hexdigest()
    salida.mkdir(parents=True, exist_ok=True)
    modelo = PBIXRay(str(archivo))
    try:
        columnas = modelo.dax_columns
        formulas = columnas[columnas.TableName == "CONTROL DE RECEPCION"]
        formulas.to_json(salida / "formulas_dax.json", orient="records", force_ascii=False, indent=2)
        modelo.power_query.to_json(salida / "consultas_power_query.json", orient="records", force_ascii=False, indent=2)
        modelo.relationships.to_json(salida / "relaciones.json", orient="records", force_ascii=False, indent=2)
        (salida / "formulas.dax").write_text("\n\n".join(
            f"// {r.ColumnName}\n{r.Expression}" for r in formulas.itertuples()
        ), encoding="utf-8")
        with ZipFile(archivo) as zipfile:
            layout = json.loads(zipfile.read("Report/Layout").decode("utf-16-le"))
        visuales = []
        for pagina in layout["sections"]:
            for visual in pagina["visualContainers"]:
                config = json.loads(visual["config"])
                visuales.append({"pagina": pagina["displayName"],
                                 "tipo": config.get("singleVisual", {}).get("visualType"),
                                 "filtros_pagina": pagina.get("filters"),
                                 "query": json.loads(visual["query"]) if visual.get("query") else None})
        (salida / "visuales.json").write_text(json.dumps(visuales, ensure_ascii=False, indent=2), encoding="utf-8")
        campos = ["ID_INT", "Codigo Proveedor", "Año", "Fecha de Entrega", "FECHA EMISION OC",
                  "PLAN MUESTREO", "TieneCertificado", "PuntajeDemoraEfectiva", "PuntajeCalidadProveedor",
                  "PuntajeCalidadPonderado", "PorcentajeEntregasConCertificado", "PuntajeCertificadoCalidad",
                  "PuntajeCertificadoPonderado", "PuntajeEntregaPonderado", "PuntajeTotalProveedor",
                  "ClasificacionProveedor"]
        datos = modelo.get_table("CONTROL DE RECEPCION", columns=campos)
        proveedores = modelo.get_table("PROVEEDORES", columns=["CODIGO", "DEMORA_ENTREGA", "APLICA CERTIFICADO_CALIDAD", "EVALUAR"])
        unido = datos.merge(proveedores, left_on="Codigo Proveedor", right_on="CODIGO", how="left", validate="many_to_one")

        def discrepancias(observado, calculado):
            iguales = observado.isna() & calculado.isna()
            iguales |= (observado - calculado).abs().lt(0.000001).fillna(False)
            return int((~iguales).sum())

        calidad = datos["PLAN MUESTREO"].str.casefold().map({"normal": 67, "simplificada": 100, "estricta": 33}).astype("Float64")
        certificado = unido["PuntajeCertificadoCalidad"].astype("Float64") * 0.10
        certificado = certificado.where(unido["APLICA CERTIFICADO_CALIDAD"].fillna(False))
        total = datos["PuntajeCalidadPonderado"].fillna(0) + datos["PuntajeEntregaPonderado"].fillna(0) + datos["PuntajeCertificadoPonderado"].fillna(0)
        comprobaciones = {
            "calidad_vs_plan": discrepancias(datos["PuntajeCalidadProveedor"], calidad),
            "calidad_45": discrepancias(datos["PuntajeCalidadPonderado"], datos["PuntajeCalidadProveedor"] * 0.45),
            "entrega_45": discrepancias(datos["PuntajeEntregaPonderado"], datos["PuntajeDemoraEfectiva"] * 0.45),
            "certificado_10_si_aplica": discrepancias(unido["PuntajeCertificadoPonderado"], certificado),
            "total_suma_blancos_cero": discrepancias(datos["PuntajeTotalProveedor"], total),
        }
        fechas_validas = unido["FECHA EMISION OC"].notna() & unido["Fecha de Entrega"].notna() & unido["DEMORA_ENTREGA"].notna()
        validos = unido[fechas_validas].copy()
        prevista = validos["FECHA EMISION OC"] + pd.to_timedelta(validos["DEMORA_ENTREGA"].astype(float), unit="D")
        retraso = (validos["Fecha de Entrega"].dt.normalize() - prevista.dt.normalize()).dt.days
        previsto = retraso.map(lambda d: 100 if d <= 21 else 33).astype("Float64")
        comprobaciones["entrega_con_fechas_validas"] = discrepancias(validos["PuntajeDemoraEfectiva"], previsto)
        anuales = unido[unido["Año"] == 2025]
        visibles = anuales[anuales["EVALUAR"].fillna(False)]
        agrupados = visibles.groupby("Codigo Proveedor")["PuntajeTotalProveedor"].agg(["count", "mean", "min", "max", "last"])
        grupos_variables = datos.groupby(["Codigo Proveedor", "Año"])["PuntajeTotalProveedor"].nunique()
        sin_fecha = datos["FECHA EMISION OC"].isna()
        resumen = {
            "sha256": huella, "tablas": len(modelo.tables), "medidas_dax": len(modelo.dax_measures),
            "columnas_calculadas_negocio": len(formulas), "filas_recepcion": len(datos),
            "filas_2025_fecha_entrega": len(anuales), "filas_2025_evaluar_true": len(visibles),
            "proveedores_2025_evaluar_true": len(agrupados),
            "grupos_proveedor_anio_con_total_variable": int((grupos_variables > 1).sum()),
            "proveedores_2025_promedio_distinto_ultimo": int((agrupados["mean"] - agrupados["last"]).abs().gt(0.000001).sum()),
            "discrepancias": comprobaciones,
            "filas_entrega_con_fechas_verificables": len(validos),
            "sin_fecha_emision_oc": int(sin_fecha.sum()),
            "sin_fecha_emision_oc_penalizados_33": int((sin_fecha & (datos["PuntajeDemoraEfectiva"] == 33)).sum()),
            "certificado_porcentaje_valores": {str(k): int(v) for k,v in datos["PorcentajeEntregasConCertificado"].value_counts(dropna=False).items()},
            "sin_plan_muestreo": int(datos["PLAN MUESTREO"].isna().sum()),
            "sha256_sin_cambios": hashlib.sha256(archivo.read_bytes()).hexdigest() == huella,
        }
        agrupados.reset_index().to_json(salida / "promedios_2025.json", orient="records", force_ascii=False, indent=2)
        (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        return resumen
    finally:
        modelo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--salida", type=Path, default=Path("outputs/evaluacion_powerbi"))
    args = parser.parse_args()
    print(json.dumps(inspeccionar(args.archivo, args.salida), ensure_ascii=False, indent=2))
