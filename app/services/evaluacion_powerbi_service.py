"""Ranking e historial recalculados desde Access, sin persistir evaluaciones."""

from __future__ import annotations

import logging
from collections import Counter, OrderedDict, defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from time import monotonic
from typing import Any

from app.services.access_read_service import (
    AccessReadError,
    _access_connection_lock,
    _access_read_connection,
)
from app.services.evaluacion_access_import_service import _normalizar_codigo

logger = logging.getLogger(__name__)
METODOLOGIA = "PBIX-45-45-10-CERTIFICADO-AUSENTE-0-SIN-OC-EN-PLAZO"
_cache: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()
_cache_lock = Lock()
_TTL = 60


def nombre_clave(valor: Any) -> str:
    return " ".join(str(valor or "").split()).casefold()


def resolver_maestro(fila, por_codigo, por_nombre, normalizar=_normalizar_codigo):
    codigo = normalizar(fila["Codigo Proveedor"])
    nombre = nombre_clave(fila["PROVEEDOR"])
    matches = por_codigo.get(codigo, [])
    if len(matches) == 1 and nombre in {
        nombre_clave(matches[0][c]) for c in ("PROVEEDOR", "RAZON SOCIAL")
    }:
        return matches[0], "Código y nombre coinciden"
    alternativas = por_nombre.get(nombre, []) if nombre else []
    if len(alternativas) == 1:
        return alternativas[0], "Nombre exacto único; código de origen inconsistente"
    return None, "Identidad sin coincidencia exacta única"


def puntuar(plan, emision, entrega, demora, certificado, aplica) -> dict:
    calidad = {"simplificada": 100, "normal": 67, "estricta": 33}.get(
        str(plan or "").strip().casefold(), 0
    )
    falta_oc, falta_plazo = emision is None, demora is None
    plazo = int(demora or 0)
    retraso = (
        max(0, (entrega.date() - (emision.date() + timedelta(days=plazo))).days)
        if emision
        else None
    )
    entrega_base = 33 if retraso is not None and retraso > 21 else 100
    q, e = Decimal(calidad) * Decimal("0.45"), Decimal(entrega_base) * Decimal("0.45")
    c = Decimal(10) if certificado and aplica else Decimal(0)
    return {
        "calidad_base": calidad,
        "entrega_base": entrega_base,
        "retraso_dias": retraso,
        "calidad": q,
        "entrega": e,
        "certificado": c,
        "total": q + e + c,
        "sin_fecha_oc": falta_oc,
        "sin_plazo": falta_plazo,
        "sin_plan": calidad == 0,
    }


def clasificar(total: Decimal) -> str:
    return "APROBADO" if total >= 70 else "CONDICIONAL" if total >= 55 else "NO APTO"


def validar_periodo(desde: date | None, hasta: date) -> None:
    if hasta == date.max or (desde and desde > hasta):
        raise ValueError(
            "El período es inválido: Desde debe ser anterior o igual a Hasta."
        )


def leer_fuentes(desde: date | None, hasta: date) -> tuple[list[dict], list[dict]]:
    validar_periodo(desde, hasta)
    where = "[Fecha de Entrega] < ?"
    params: list[Any] = [hasta + timedelta(days=1)]
    if desde:
        where += " AND [Fecha de Entrega] >= ?"
        params.append(desde)
    with _access_connection_lock:
        connection = _access_read_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT [ID_INT], [Codigo Proveedor], [PROVEEDOR], [Fecha de Entrega], "
                "[FECHA EMISION OC], [Fecha Control], [PLAN MUESTREO], [TieneCertificado], [Estado] "
                f"FROM [CONTROL DE RECEPCION] WHERE {where} ORDER BY [ID_INT]",
                params,
            )
            columnas = [c[0] for c in cursor.description]
            controles = [dict(zip(columnas, r)) for r in cursor.fetchall()]
            cursor.execute(
                "SELECT [CODIGO], [PROVEEDOR], [RAZON SOCIAL], [DEMORA_ENTREGA], "
                "[APLICA CERTIFICADO_CALIDAD], [EVALUAR], [INSUMO SERVICIO], [CLASIFICACION] "
                "FROM [PROVEEDORES]"
            )
            columnas = [c[0] for c in cursor.description]
            return controles, [dict(zip(columnas, r)) for r in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Error consultando fuentes del ranking Power BI")
            raise AccessReadError("No se pudo consultar el ranking de Access") from exc
        finally:
            connection.close()


def analizar_fuentes(controles: list[dict], maestros: list[dict]) -> dict:
    por_codigo, por_nombre = defaultdict(list), defaultdict(list)
    for m in maestros:
        clave = _normalizar_codigo(m["CODIGO"])
        if clave:
            por_codigo[clave].append(m)
            for nombre in {
                nombre_clave(m[c]) for c in ("PROVEEDOR", "RAZON SOCIAL")
            } - {""}:
                por_nombre[nombre].append(m)
    detalle, excluidos = [], []
    for fila in controles:
        codigo = _normalizar_codigo(fila["Codigo Proveedor"])
        m, asociacion = resolver_maestro(fila, por_codigo, por_nombre)
        if m is None or not m["EVALUAR"]:
            excluidos.append(
                {
                    "id": fila["ID_INT"],
                    "codigo": codigo,
                    "nombre": fila["PROVEEDOR"],
                    "fecha": fila["Fecha de Entrega"],
                    "motivo": asociacion if m is None else "No marcado EVALUAR",
                }
            )
            continue
        calculo = puntuar(
            fila["PLAN MUESTREO"],
            fila["FECHA EMISION OC"],
            fila["Fecha de Entrega"],
            m["DEMORA_ENTREGA"],
            fila["TieneCertificado"],
            m["APLICA CERTIFICADO_CALIDAD"],
        )
        detalle.append(
            {
                "id": fila["ID_INT"],
                "codigo": _normalizar_codigo(m["CODIGO"]),
                "codigo_origen": codigo,
                "nombre_origen": fila["PROVEEDOR"],
                "asociacion": asociacion,
                "nombre": str(m["PROVEEDOR"] or m["RAZON SOCIAL"] or fila["PROVEEDOR"]),
                "tipo": m["INSUMO SERVICIO"],
                "fecha": fila["Fecha de Entrega"],
                "tiene_certificado": bool(fila["TieneCertificado"]),
                "estado": str(fila["Estado"] or "").strip(),
                **calculo,
            }
        )
    if len({d["id"] for d in detalle}) != len(detalle):
        raise AccessReadError(
            "Se detectaron ID_INT duplicados; revisar los datos antes de evaluar."
        )
    grupos = defaultdict(list)
    for fila in detalle:
        grupos[fila["codigo"]].append(fila)
    proveedores = [
        resumir_grupo(filas, codigo=codigo) for codigo, filas in grupos.items()
    ]
    proveedores.sort(key=lambda r: (-r["total"], r["nombre"].casefold(), r["codigo"]))
    resumen = {
        "controles_periodo": len(controles),
        "controles_evaluados": len(detalle),
        "controles_excluidos": len(excluidos),
        "proveedores": len(proveedores),
        "resultados": dict(Counter(p["resultado"] for p in proveedores)),
        "sin_fecha_oc": sum(f["sin_fecha_oc"] for f in detalle),
        "sin_plan": sum(f["sin_plan"] for f in detalle),
        "sin_plazo": sum(f["sin_plazo"] for f in detalle),
        "identidad_por_nombre": sum(
            f["asociacion"].startswith("Nombre exacto") for f in detalle
        ),
        "exclusiones_por_motivo": dict(Counter(f["motivo"] for f in excluidos)),
    }
    return {"resumen": resumen, "proveedores": proveedores, "detalle": detalle}


def resumir_grupo(
    filas: list[dict], *, codigo: str, periodo: str | None = None
) -> dict:
    n = len(filas)

    def media(campo):
        return sum((f[campo] for f in filas), Decimal(0)) / n

    total = media("total")
    return {
        "codigo": codigo,
        "nombre": filas[0]["nombre"],
        "periodo": periodo,
        "recepciones": n,
        "rechazos": sum(f.get("estado", "").casefold() == "rechazado" for f in filas),
        "controles_rechazados": [
            {"id": f["id"], "fecha": f["fecha"].date()}
            for f in sorted(filas, key=lambda f: (f["fecha"], f["id"]))
            if f.get("estado", "").casefold() == "rechazado"
        ],
        "calidad": media("calidad"),
        "entrega": media("entrega"),
        "certificado": media("certificado"),
        "total": total,
        "resultado": clasificar(total),
        "sin_fecha_oc": sum(f["sin_fecha_oc"] for f in filas),
        "sin_plan": sum(f["sin_plan"] for f in filas),
        "sin_plazo": sum(f["sin_plazo"] for f in filas),
        "identidad_por_nombre": sum(
            f["asociacion"].startswith("Nombre exacto") for f in filas
        ),
    }


def _datos(desde: date | None, hasta: date) -> dict:
    validar_periodo(desde, hasta)
    key = (desde, hasta)
    with _cache_lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < _TTL:
            _cache.move_to_end(key)
            return deepcopy(cached[1])
    controles, maestros = leer_fuentes(desde, hasta)
    resultado = analizar_fuentes(controles, maestros)
    resultado["calculado_en"] = datetime.now(timezone.utc)
    with _cache_lock:
        _cache[key] = (monotonic(), resultado)
        _cache.move_to_end(key)
        while len(_cache) > 6:
            _cache.popitem(last=False)
    return deepcopy(resultado)


def ranking_periodo(desde: date, hasta: date) -> dict:
    datos = _datos(desde, hasta)
    proveedores = datos["proveedores"]
    return {
        "desde": desde,
        "hasta": hasta,
        "metodologia": METODOLOGIA,
        "calculado_en": datos["calculado_en"],
        "resumen": datos["resumen"],
        "proveedores": proveedores,
        "mejores_20": proveedores[:20],
        "peores_20": sorted(
            proveedores, key=lambda r: (r["total"], r["nombre"].casefold(), r["codigo"])
        )[:20],
    }


def historial_proveedor(
    codigo: str, hasta: date, desde: date | None = None, agrupacion: str = "anual"
) -> dict:
    if agrupacion not in {"anual", "mensual"}:
        raise ValueError("La agrupación debe ser anual o mensual.")
    clave = _normalizar_codigo(codigo)
    if not clave:
        raise ValueError("El código de proveedor es obligatorio.")
    datos = _datos(desde, hasta)
    proveedor = next((p for p in datos["proveedores"] if p["codigo"] == clave), None)
    filas = [f for f in datos["detalle"] if f["codigo"] == clave]
    grupos = defaultdict(list)
    for fila in filas:
        periodo = fila["fecha"].strftime("%Y" if agrupacion == "anual" else "%Y-%m")
        grupos[periodo].append(fila)
    serie = [resumir_grupo(grupos[p], codigo=clave, periodo=p) for p in sorted(grupos)]
    return {
        "codigo": clave,
        "proveedor": proveedor,
        "desde": desde,
        "hasta": hasta,
        "agrupacion": agrupacion,
        "metodologia": METODOLOGIA,
        "calculado_en": datos["calculado_en"],
        "serie": serie,
    }
