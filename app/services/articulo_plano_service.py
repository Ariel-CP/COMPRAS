import re
from typing import Any
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.plano_service import catalogar_planos_pdf


def listar_articulos_con_planos(
    db: Session, q: str | None = None, directorio: str | None = None
) -> list[dict[str, Any]]:
    """Lista PDFs y los relaciona por los cuatro dígitos finales del artículo."""
    filas = (
        db.execute(
            text("""
                SELECT p.id AS producto_id, p.codigo AS articulo_codigo,
                       p.nombre AS articulo_nombre,
                      p.tipo_producto,
                       MAX(NULLIF(TRIM(rl.designacion), '')) AS descripcion
                FROM producto p
                LEFT JOIN recepcion_linea rl ON rl.producto_id = p.id
                GROUP BY p.id, p.codigo, p.nombre
                ORDER BY p.codigo
            """),
            {},
        )
        .mappings()
        .all()
    )
    filas_mbom = (
        db.execute(
            text("""
                SELECT DISTINCT componente.id AS componente_producto_id,
                       padre.id AS producto_padre_id,
                       padre.codigo AS padre_codigo,
                       padre.nombre AS padre_nombre
                FROM mbom_cabecera cab
                JOIN mbom_detalle det ON det.mbom_id = cab.id
                JOIN producto componente
                  ON componente.id = det.componente_producto_id
                JOIN producto padre ON padre.id = cab.producto_padre_id
                WHERE cab.estado = 'ACTIVO'
                  AND (cab.vigencia_desde IS NULL OR cab.vigencia_desde <= CURRENT_DATE())
                  AND (cab.vigencia_hasta IS NULL OR cab.vigencia_hasta >= CURRENT_DATE())
                  AND componente.tipo_producto = 'WIP'
                  AND componente.activo = 1
                  AND padre.activo = 1
                ORDER BY componente.id, padre.codigo
            """),
            {},
        )
        .mappings()
        .all()
    )
    catalogo = catalogar_planos_pdf(directorio)
    relaciones_por_numero: dict[str, list[dict[str, Any]]] = {}
    padres_por_componente: dict[int, list[dict[str, Any]]] = {}
    for fila in filas_mbom:
        padres_por_componente.setdefault(fila["componente_producto_id"], []).append(
            {
                "producto_id": fila["producto_padre_id"],
                "codigo": fila["padre_codigo"],
                "nombre": fila["padre_nombre"],
            }
        )

    for fila in filas:
        match = re.search(r"(\d{4})$", str(fila["articulo_codigo"] or ""))
        if not match:
            continue
        numero_base = match.group(1)
        if numero_base not in catalogo:
            continue
        relacion = {
            "producto_id": fila["producto_id"],
            "articulo_codigo": fila["articulo_codigo"],
            "articulo_nombre": fila["articulo_nombre"],
            "tipo_producto": fila["tipo_producto"],
            "descripcion": fila["descripcion"],
            "mbom_padres": padres_por_componente.get(fila["producto_id"], []),
        }
        relaciones_por_numero.setdefault(numero_base, []).append(relacion)

    resultados = []
    for numero_base, revisiones in catalogo.items():
        for revision, archivo in revisiones.items():
            numero_archivo = f"{numero_base}-{revision}" if revision else numero_base
            asociaciones = relaciones_por_numero.get(numero_base, [])

            articulos = sorted(
                {
                    f"{item['articulo_codigo']} · {item['articulo_nombre']}"
                    for item in asociaciones
                    if item["articulo_codigo"] or item["articulo_nombre"]
                }
            )
            codigos_articulo = sorted(
                {
                    item["articulo_codigo"]
                    for item in asociaciones
                    if item["articulo_codigo"]
                }
            )
            nombres_articulo = sorted(
                {
                    item["articulo_nombre"]
                    for item in asociaciones
                    if item["articulo_nombre"]
                }
            )
            descripciones = sorted({item["descripcion"] for item in asociaciones if item["descripcion"]})
            padres_mbom_por_clave = {
                (padre["producto_id"], padre["codigo"], padre["nombre"]): padre
                for item in asociaciones
                for padre in item["mbom_padres"]
            }
            padres_mbom = sorted(
                padres_mbom_por_clave.values(),
                key=lambda padre: (padre["codigo"], padre["nombre"]),
            )
            wip_asociados = [item for item in asociaciones if item["tipo_producto"] == "WIP"]
            resultados.append(
                {
                    "numero_plano": numero_archivo,
                    "numero_base": numero_base,
                    "revision": revision or "Sin revisión",
                    "tiene_revision": bool(revision),
                    "archivo": archivo.name,
                    "disponible": True,
                    "articulos": articulos,
                    "codigos_articulo": codigos_articulo,
                    "nombres_articulo": nombres_articulo,
                    "articulos_texto": ", ".join(articulos) if articulos else "Sin artículo asociado",
                    "producto_ids": sorted({item["producto_id"] for item in asociaciones}),
                    "asociaciones": asociaciones,
                    "tipos_producto": sorted({item["tipo_producto"] for item in asociaciones}),
                    "es_semielaborado": bool(wip_asociados),
                    "usado_en_mbom": bool(padres_mbom),
                    "mbom_padres": padres_mbom,
                    "mbom_padres_texto": ", ".join(
                        f"{padre['codigo']} · {padre['nombre']}" for padre in padres_mbom
                    ) if padres_mbom else "No aparece en una MBOM activa/vigente",
                    "descripcion": "; ".join(descripciones) if descripciones else "Sin descripción registrada.",
                    "asociado": bool(articulos),
                    "pdf_url": f"/api/productos/planos/{quote(numero_archivo, safe='')}/pdf",
                }
            )

    if q and q.strip():
        consulta = q.strip().casefold()
        resultados = [
            item for item in resultados
            if any(
                consulta in str(item[clave]).casefold()
                for clave in ("numero_plano", "numero_base", "revision", "archivo", "articulos_texto", "descripcion")
            )
        ]
    resultados.sort(key=lambda item: (item["numero_base"], item["revision"]))
    return resultados
