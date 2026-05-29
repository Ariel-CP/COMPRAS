import csv
import hashlib
import io
import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile
from openpyxl import Workbook, load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..schemas.precio import PrecioImportResult


def _fix_mojibake_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    if not any(marker in text_value for marker in ("Ã", "Â", "â")):
        return text_value
    try:
        repaired = text_value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text_value
    return repaired.strip() or text_value


def _row_to_precio(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "producto_id": row.producto_id,
        "producto_codigo": row.producto_codigo,
        "producto_nombre": row.producto_nombre,
        "proveedor_codigo": row.proveedor_codigo,
        "proveedor_nombre": _fix_mojibake_text(row.proveedor_nombre),
        "fecha_precio": (
            row.fecha_precio.isoformat() if row.fecha_precio else None
        ),
        "precio_unitario": float(row.precio_unitario),
        "moneda": row.moneda,
        "origen": row.origen,
        "referencia_doc": _fix_mojibake_text(row.referencia_doc),
        "notas": _fix_mojibake_text(row.notas),
    }


def _safe_user_id(current_user_id: Optional[int]) -> Optional[int]:
    if current_user_id is None:
        return None
    try:
        value = int(current_user_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _json_dump(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _build_precio_snapshot(
    *,
    precio_unitario: float,
    proveedor_nombre: Optional[str],
    origen: str,
    referencia_doc: Optional[str],
    notas: Optional[str],
) -> Dict[str, Any]:
    return {
        "precio_unitario": float(precio_unitario),
        "proveedor_nombre": proveedor_nombre,
        "origen": origen,
        "referencia_doc": referencia_doc,
        "notas": notas,
    }


def _crear_import_lote(
    db: Session,
    *,
    archivo_nombre: str,
    archivo_hash: Optional[str],
    formato: str,
    usuario_id: Optional[int],
    total_registros: int,
) -> int:
    db.execute(
        text(
            """
            INSERT INTO precio_compra_import_lote
            (archivo_nombre, archivo_hash, formato, usuario_id, total_registros, estado)
            VALUES (:archivo_nombre, :archivo_hash, :formato, :usuario_id, :total_registros, 'ERROR')
            """
        ),
        {
            "archivo_nombre": archivo_nombre or None,
            "archivo_hash": archivo_hash,
            "formato": formato,
            "usuario_id": usuario_id,
            "total_registros": total_registros,
        },
    )
    return int(db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar() or 0)


def _cerrar_import_lote(
    db: Session,
    *,
    lote_id: int,
    insertados: int,
    actualizados: int,
    rechazados: int,
    estado: str,
    mensaje_error: Optional[str] = None,
) -> None:
    db.execute(
        text(
            """
            UPDATE precio_compra_import_lote
            SET fecha_fin = CURRENT_TIMESTAMP,
                insertados = :insertados,
                actualizados = :actualizados,
                rechazados = :rechazados,
                estado = :estado,
                mensaje_error = :mensaje_error
            WHERE id = :id
            """
        ),
        {
            "id": lote_id,
            "insertados": insertados,
            "actualizados": actualizados,
            "rechazados": rechazados,
            "estado": estado,
            "mensaje_error": mensaje_error,
        },
    )


def _registrar_auditoria_precio(
    db: Session,
    *,
    precio_compra_hist_id: int,
    import_lote_id: Optional[int],
    usuario_id: Optional[int],
    operacion: str,
    origen_cambio: str,
    producto_id: int,
    proveedor_codigo: str,
    fecha_precio: date,
    moneda: str,
    valores_nuevos: Dict[str, Any],
    valores_anteriores: Optional[Dict[str, Any]] = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO precio_compra_hist_audit
            (
                precio_compra_hist_id,
                import_lote_id,
                usuario_id,
                operacion,
                origen_cambio,
                producto_id,
                proveedor_codigo,
                fecha_precio,
                moneda,
                valores_anteriores,
                valores_nuevos
            ) VALUES (
                :precio_compra_hist_id,
                :import_lote_id,
                :usuario_id,
                :operacion,
                :origen_cambio,
                :producto_id,
                :proveedor_codigo,
                :fecha_precio,
                :moneda,
                :valores_anteriores,
                :valores_nuevos
            )
            """
        ),
        {
            "precio_compra_hist_id": precio_compra_hist_id,
            "import_lote_id": import_lote_id,
            "usuario_id": usuario_id,
            "operacion": operacion,
            "origen_cambio": origen_cambio,
            "producto_id": producto_id,
            "proveedor_codigo": proveedor_codigo,
            "fecha_precio": fecha_precio,
            "moneda": moneda,
            "valores_anteriores": (
                _json_dump(valores_anteriores)
                if valores_anteriores is not None
                else None
            ),
            "valores_nuevos": _json_dump(valores_nuevos),
        },
    )


def listar_precios_compra(
    db: Session,
    producto_id: Optional[int] = None,
    q: Optional[str] = None,
    proveedor: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    where = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if producto_id is not None:
        where.append("h.producto_id = :pid")
        params["pid"] = producto_id

    if q:
        where.append(
            "(p.codigo LIKE :q OR p.nombre LIKE :q"
            " OR h.proveedor_codigo LIKE :q"
            " OR h.proveedor_nombre LIKE :q)"
        )
        params["q"] = f"%{q}%"

    if proveedor:
        where.append(
            "(h.proveedor_codigo LIKE :prov OR h.proveedor_nombre LIKE :prov)"
        )
        params["prov"] = f"%{proveedor}%"

    if desde is not None:
        where.append("h.fecha_precio >= :desde")
        params["desde"] = desde

    if hasta is not None:
        where.append("h.fecha_precio <= :hasta")
        params["hasta"] = hasta

    sql = text(
        """
        SELECT h.id, h.producto_id, h.proveedor_codigo, h.proveedor_nombre,
               h.fecha_precio, h.precio_unitario, h.moneda, h.origen,
               h.referencia_doc, h.notas,
               p.codigo AS producto_codigo, p.nombre AS producto_nombre
        FROM precio_compra_hist h
        JOIN producto p ON p.id = h.producto_id
        WHERE """
        + " AND ".join(where)
        + " ORDER BY h.fecha_precio DESC, h.id DESC"
        + " LIMIT :limit OFFSET :offset"
    )

    rows = db.execute(sql, params).fetchall()
    return [_row_to_precio(r) for r in rows]


def crear_precio_compra_manual(
    db: Session,
    *,
    producto_id: int,
    proveedor_codigo: str,
    proveedor_nombre: Optional[str],
    fecha_precio: date,
    precio_unitario: float,
    moneda: str,
    referencia_doc: Optional[str],
    notas: Optional[str],
    current_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    producto = db.execute(
        text("SELECT id, codigo, nombre FROM producto WHERE id = :id LIMIT 1"),
        {"id": producto_id},
    ).first()
    if not producto:
        raise ValueError("Articulo no encontrado")

    proveedor_codigo_value = (proveedor_codigo or "").strip()
    if not proveedor_codigo_value:
        raise ValueError("Proveedor codigo es obligatorio")

    try:
        precio_raw = str(precio_unitario).strip().replace(",", ".")
        precio_value = float(precio_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Precio unitario invalido") from exc
    if precio_value <= 0:
        raise ValueError("Precio unitario debe ser mayor a cero")

    moneda_value = _normalize_moneda_value(moneda, "ARS")
    if not moneda_value:
        raise ValueError("Moneda invalida")

    proveedor_nombre_value = (
        _fix_mojibake_text(proveedor_nombre) or proveedor_codigo_value
    )
    referencia_value = _fix_mojibake_text(referencia_doc)
    notas_value = _fix_mojibake_text(notas)

    usuario_id = _safe_user_id(current_user_id)

    existing = db.execute(
        text(
            "SELECT id, precio_unitario, proveedor_nombre, origen, referencia_doc, notas "
            "FROM precio_compra_hist "
            "WHERE producto_id=:pid AND proveedor_codigo=:prov "
            "AND fecha_precio=:fecha AND moneda=:moneda"
        ),
        {
            "pid": producto_id,
            "prov": proveedor_codigo_value,
            "fecha": fecha_precio,
            "moneda": moneda_value,
        },
    ).first()

    if existing:
        before_snapshot = _build_precio_snapshot(
            precio_unitario=float(existing[1]),
            proveedor_nombre=existing[2],
            origen=existing[3],
            referencia_doc=existing[4],
            notas=existing[5],
        )
        after_snapshot = _build_precio_snapshot(
            precio_unitario=precio_value,
            proveedor_nombre=proveedor_nombre_value,
            origen="MANUAL",
            referencia_doc=referencia_value,
            notas=notas_value,
        )
        db.execute(
            text(
                "UPDATE precio_compra_hist SET "
                "proveedor_nombre=:prov_nom, precio_unitario=:precio, "
                "origen='MANUAL', referencia_doc=:ref, notas=:notas "
                "WHERE id=:id"
            ),
            {
                "prov_nom": proveedor_nombre_value,
                "precio": precio_value,
                "ref": referencia_value,
                "notas": notas_value,
                "id": existing[0],
            },
        )
        target_id = int(existing[0])
        _registrar_auditoria_precio(
            db,
            precio_compra_hist_id=target_id,
            import_lote_id=None,
            usuario_id=usuario_id,
            operacion="UPDATE",
            origen_cambio="MANUAL",
            producto_id=producto_id,
            proveedor_codigo=proveedor_codigo_value,
            fecha_precio=fecha_precio,
            moneda=moneda_value,
            valores_anteriores=before_snapshot,
            valores_nuevos=after_snapshot,
        )
    else:
        db.execute(
            text(
                "INSERT INTO precio_compra_hist "
                "(producto_id, proveedor_codigo, proveedor_nombre, fecha_precio, "
                "precio_unitario, moneda, origen, referencia_doc, notas) VALUES "
                "(:pid, :prov, :prov_nom, :fecha, :precio, :moneda, 'MANUAL', :ref, :notas)"
            ),
            {
                "pid": producto_id,
                "prov": proveedor_codigo_value,
                "prov_nom": proveedor_nombre_value,
                "fecha": fecha_precio,
                "precio": precio_value,
                "moneda": moneda_value,
                "ref": referencia_value,
                "notas": notas_value,
            },
        )
        target_id = int(db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar() or 0)
        _registrar_auditoria_precio(
            db,
            precio_compra_hist_id=target_id,
            import_lote_id=None,
            usuario_id=usuario_id,
            operacion="INSERT",
            origen_cambio="MANUAL",
            producto_id=producto_id,
            proveedor_codigo=proveedor_codigo_value,
            fecha_precio=fecha_precio,
            moneda=moneda_value,
            valores_nuevos=_build_precio_snapshot(
                precio_unitario=precio_value,
                proveedor_nombre=proveedor_nombre_value,
                origen="MANUAL",
                referencia_doc=referencia_value,
                notas=notas_value,
            ),
        )

    db.commit()

    row = db.execute(
        text(
            """
            SELECT h.id, h.producto_id, h.proveedor_codigo, h.proveedor_nombre,
                   h.fecha_precio, h.precio_unitario, h.moneda, h.origen,
                   h.referencia_doc, h.notas,
                   p.codigo AS producto_codigo, p.nombre AS producto_nombre
            FROM precio_compra_hist h
            JOIN producto p ON p.id = h.producto_id
            WHERE h.id = :id
            LIMIT 1
            """
        ),
        {"id": target_id},
    ).first()
    if not row:
        raise ValueError("No se pudo recuperar el precio guardado")
    return _row_to_precio(row)


ALLOWED_MONEDAS = {"ARS", "USD", "USD_MAY", "EUR"}
CURRENCY_ALIASES = {
    "ARS": "ARS",
    "PESO": "ARS",
    "PESOS": "ARS",
    "USD": "USD",
    "US": "USD",
    "DOLAR": "USD",
    "DOLARES": "USD",
    "EURO": "EUR",
    "EUROS": "EUR",
    "EUR": "EUR",
    "USD MAY": "USD_MAY",
    "USDMAY": "USD_MAY",
    "DOLAR MAY": "USD_MAY",
    "DOLARES MAY": "USD_MAY",
    "DOLAR MAYORISTA": "USD_MAY",
    "USD MAYORISTA": "USD_MAY",
}
ALLOWED_ORIGENES = {"ERP_FLEXXUS", "MANUAL", "OTRO"}
DEFAULT_PROVEEDOR_CODIGO = "PROV_GENERICO"
DEFAULT_PROVEEDOR_NOMBRE = "Proveedor Genérico"
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d")
DATETIME_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
)


def _normalize_datetime_text(raw: str) -> str:
    normalized = raw.replace("\xa0", " ").strip()
    normalized = " ".join(normalized.split())
    return re.sub(
        r"(?i)\b([ap])\.?\s*m\.?\b",
        lambda match: match.group(1).upper() + "M",
        normalized,
    )


def _sanitize_currency_key(raw: str) -> str:
    cleaned = raw.replace("\xa0", " ").strip().upper()
    cleaned = cleaned.replace("_", " ")
    cleaned = " ".join(cleaned.split())
    return re.sub(r"[^A-Z0-9 ]+", "", cleaned)


def _normalize_moneda_value(
    value: Any,
    default: Optional[str] = None
) -> Optional[str]:
    candidate = value if value not in (None, "") else default
    if candidate is None:
        return None
    key = _sanitize_currency_key(str(candidate))
    if not key:
        return None
    mapped = CURRENCY_ALIASES.get(key)
    return mapped if mapped in ALLOWED_MONEDAS else None


def _parse_fecha_precio(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw_text = str(value).strip()
    if not raw_text:
        return None
    cleaned = _normalize_datetime_text(raw_text)
    if not cleaned:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _decode_csv_content(content: bytes) -> str:
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"No se pudo decodificar el archivo: {exc}",
            ) from exc


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        norm_key = str(key).strip().lower()
        if isinstance(value, str):
            normalized[norm_key] = _fix_mojibake_text(value)
        else:
            normalized[norm_key] = value
    return normalized


def _parse_csv_rows(content: bytes) -> List[Dict[str, Any]]:
    decoded = _decode_csv_content(content)
    text_stream = io.StringIO(decoded)
    sample = text_stream.read(2048)
    text_stream.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo detectar el formato del CSV: {exc}",
        ) from exc
    reader = csv.DictReader(text_stream, dialect=dialect)
    return [_normalize_row(row) for row in reader]


def _parse_xlsx_rows(content: bytes) -> List[Dict[str, Any]]:
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo XLSX inválido: {exc}",
        ) from exc
    ws = wb.active
    if ws is None:
        return []
    try:
        headers = [
            str(c.value).strip().lower() if c.value is not None else ""
            for c in next(ws.iter_rows(min_row=1, max_row=1))
        ]
    except StopIteration:
        return []
    rows: List[Dict[str, Any]] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        row_dict: Dict[str, Any] = {}
        for idx, cell in enumerate(r):
            key = headers[idx] if idx < len(headers) else f"col_{idx}"
            if isinstance(cell, str):
                row_dict[key] = cell.strip()
            else:
                row_dict[key] = cell
        rows.append(row_dict)
    return rows


def _get_producto_id(
    db: Session, cache: Dict[str, Optional[int]], codigo: str
) -> Optional[int]:
    if codigo in cache:
        return cache[codigo]
    res = db.execute(
        text("SELECT id FROM producto WHERE codigo = :codigo"),
        {"codigo": codigo},
    ).first()
    cache[codigo] = int(res[0]) if res else None
    return cache[codigo]


def generar_template_precios() -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("No se pudo crear la hoja activa")
    ws.title = "precios"
    ws.append(
        [
            "producto_codigo",
            "proveedor_codigo",
            "proveedor_nombre",
            "fecha_precio",
            "precio_unitario",
            "moneda",
            "origen",
            "referencia_doc",
            "notas",
        ]
    )
    ws.append(
        [
            "MAT-001",
            "PROV01",
            "Proveedor Demo",
            datetime.today().date().isoformat(),
            "123.45",
            "ARS",
            "MANUAL",
            "OC-123",
            "Observaciones",
        ]
    )
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def importar_precios_desde_archivo(
    db: Session,
    archivo: UploadFile,
    current_user_id: Optional[int] = None,
) -> PrecioImportResult:
    filename = archivo.filename or ""
    content = archivo.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    if filename.lower().endswith(".xlsx"):
        rows = _parse_xlsx_rows(content)
    elif filename.lower().endswith(".csv") or filename == "":
        rows = _parse_csv_rows(content)
    else:
        raise HTTPException(
            status_code=400,
            detail="Extensión no soportada (usar .csv o .xlsx)",
        )

    if not rows:
        return PrecioImportResult(
            insertados=0,
            actualizados=0,
            rechazados=0,
            errores=["Archivo vacío"],
        )

    required = {
        "producto_codigo",
        "fecha_precio",
        "precio_unitario",
        "moneda",
    }
    missing = required - set(rows[0].keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Faltan columnas requeridas: {', '.join(sorted(missing))}",
        )

    insertados = actualizados = rechazados = 0
    errores: List[str] = []
    cache: Dict[str, Optional[int]] = {}
    lote_id = 0
    usuario_id = _safe_user_id(current_user_id)

    formato = "XLSX" if filename.lower().endswith(".xlsx") else "CSV"
    archivo_hash = hashlib.sha256(content).hexdigest()
    lote_id = _crear_import_lote(
        db,
        archivo_nombre=filename,
        archivo_hash=archivo_hash,
        formato=formato,
        usuario_id=usuario_id,
        total_registros=len(rows),
    )
    db.commit()

    try:
        for idx, raw_row in enumerate(rows, start=2):
            row = _normalize_row(raw_row)
            codigo = row.get("producto_codigo", "") or ""
            prov_codigo = (
                row.get("proveedor_codigo", "") or DEFAULT_PROVEEDOR_CODIGO
            )
            if not codigo:
                rechazados += 1
                errores.append(f"Fila {idx}: producto_codigo vacío")
                continue

            prod_id = _get_producto_id(db, cache, codigo)
            if not prod_id:
                rechazados += 1
                errores.append(
                    f"Fila {idx}: producto no encontrado ({codigo})"
                )
                continue

            fecha_precio = _parse_fecha_precio(row.get("fecha_precio"))
            if not fecha_precio:
                rechazados += 1
                errores.append(f"Fila {idx}: fecha_precio inválida")
                continue

            precio_raw = row.get("precio_unitario")
            try:
                precio = float(str(precio_raw).replace(",", "."))
                if precio <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                rechazados += 1
                errores.append(f"Fila {idx}: precio_unitario inválido")
                continue

            moneda_raw = row.get("moneda")
            moneda = _normalize_moneda_value(moneda_raw, "ARS")
            if not moneda:
                rechazados += 1
                errores.append(
                    f"Fila {idx}: moneda inválida ({moneda_raw or ''})"
                )
                continue

            origen = (row.get("origen") or "MANUAL").upper()
            if origen not in ALLOWED_ORIGENES:
                rechazados += 1
                errores.append(f"Fila {idx}: origen inválido ({origen})")
                continue

            prov_nombre = _fix_mojibake_text(
                row.get("proveedor_nombre") or DEFAULT_PROVEEDOR_NOMBRE
            ) or DEFAULT_PROVEEDOR_NOMBRE
            referencia = _fix_mojibake_text(row.get("referencia_doc"))
            notas = _fix_mojibake_text(row.get("notas"))

            existing = db.execute(
                text(
                    "SELECT id, precio_unitario, proveedor_nombre, origen, referencia_doc, notas "
                    "FROM precio_compra_hist "
                    "WHERE producto_id=:pid AND proveedor_codigo=:prov "
                    "AND fecha_precio=:fecha AND moneda=:moneda"
                ),
                {
                    "pid": prod_id,
                    "prov": prov_codigo,
                    "fecha": fecha_precio,
                    "moneda": moneda,
                },
            ).first()

            if existing:
                before_snapshot = _build_precio_snapshot(
                    precio_unitario=float(existing[1]),
                    proveedor_nombre=existing[2],
                    origen=existing[3],
                    referencia_doc=existing[4],
                    notas=existing[5],
                )
                after_snapshot = _build_precio_snapshot(
                    precio_unitario=precio,
                    proveedor_nombre=prov_nombre,
                    origen=origen,
                    referencia_doc=referencia,
                    notas=notas,
                )
                db.execute(
                    text(
                        "UPDATE precio_compra_hist SET "
                        "precio_unitario=:precio, proveedor_nombre=:prov_nom, "
                        "origen=:origen, referencia_doc=:ref, notas=:notas "
                        "WHERE id=:id"
                    ),
                    {
                        "precio": precio,
                        "prov_nom": prov_nombre,
                        "origen": origen,
                        "ref": referencia,
                        "notas": notas,
                        "id": existing[0],
                    },
                )
                _registrar_auditoria_precio(
                    db,
                    precio_compra_hist_id=int(existing[0]),
                    import_lote_id=lote_id,
                    usuario_id=usuario_id,
                    operacion="UPDATE",
                    origen_cambio="IMPORT",
                    producto_id=int(prod_id),
                    proveedor_codigo=prov_codigo,
                    fecha_precio=fecha_precio,
                    moneda=moneda,
                    valores_anteriores=before_snapshot,
                    valores_nuevos=after_snapshot,
                )
                actualizados += 1
            else:
                db.execute(
                    text(
                        "INSERT INTO precio_compra_hist "
                        "(producto_id, proveedor_codigo, proveedor_nombre, "
                        "fecha_precio, precio_unitario, moneda, origen, "
                        "referencia_doc, notas) VALUES "
                        "(:pid, :prov, :prov_nom, :fecha, :precio, :moneda, "
                        ":origen, :ref, :notas)"
                    ),
                    {
                        "pid": prod_id,
                        "prov": prov_codigo,
                        "prov_nom": prov_nombre,
                        "fecha": fecha_precio,
                        "precio": precio,
                        "moneda": moneda,
                        "origen": origen,
                        "ref": referencia,
                        "notas": notas,
                    },
                )
                inserted_id = int(
                    db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar() or 0
                )
                _registrar_auditoria_precio(
                    db,
                    precio_compra_hist_id=inserted_id,
                    import_lote_id=lote_id,
                    usuario_id=usuario_id,
                    operacion="INSERT",
                    origen_cambio="IMPORT",
                    producto_id=int(prod_id),
                    proveedor_codigo=prov_codigo,
                    fecha_precio=fecha_precio,
                    moneda=moneda,
                    valores_nuevos=_build_precio_snapshot(
                        precio_unitario=precio,
                        proveedor_nombre=prov_nombre,
                        origen=origen,
                        referencia_doc=referencia,
                        notas=notas,
                    ),
                )
                insertados += 1

        estado = "EXITOSA" if rechazados == 0 else "PARCIAL"
        _cerrar_import_lote(
            db,
            lote_id=lote_id,
            insertados=insertados,
            actualizados=actualizados,
            rechazados=rechazados,
            estado=estado,
            mensaje_error=("\n".join(errores[:20]) if errores else None),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        if lote_id:
            try:
                _cerrar_import_lote(
                    db,
                    lote_id=lote_id,
                    insertados=insertados,
                    actualizados=actualizados,
                    rechazados=rechazados,
                    estado="ERROR",
                    mensaje_error="Error HTTP durante importación",
                )
                db.commit()
            except Exception:
                db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logging.exception("Error importando precios")
        if lote_id:
            try:
                _cerrar_import_lote(
                    db,
                    lote_id=lote_id,
                    insertados=insertados,
                    actualizados=actualizados,
                    rechazados=rechazados,
                    estado="ERROR",
                    mensaje_error=str(exc),
                )
                db.commit()
            except Exception:
                db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error importando precios: {exc}",
        ) from exc

    return PrecioImportResult(
        importacion_id=lote_id,
        insertados=insertados,
        actualizados=actualizados,
        rechazados=rechazados,
        errores=errores,
    )


def listar_importaciones_precios(
    db: Session,
    *,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    estado: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    where = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if desde is not None:
        where.append("DATE(l.fecha_inicio) >= :desde")
        params["desde"] = desde
    if hasta is not None:
        where.append("DATE(l.fecha_inicio) <= :hasta")
        params["hasta"] = hasta
    if estado:
        where.append("l.estado = :estado")
        params["estado"] = estado.upper()

    rows = db.execute(
        text(
            """
            SELECT
                l.id,
                l.archivo_nombre,
                l.archivo_hash,
                l.formato,
                l.fecha_inicio,
                l.fecha_fin,
                l.total_registros,
                l.insertados,
                l.actualizados,
                l.rechazados,
                l.estado,
                l.mensaje_error,
                l.usuario_id,
                u.nombre AS usuario_nombre,
                u.email AS usuario_email
            FROM precio_compra_import_lote l
            LEFT JOIN usuario u ON u.id = l.usuario_id
            WHERE """
            + " AND ".join(where)
            + " ORDER BY l.fecha_inicio DESC, l.id DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings().all()

    return [dict(row) for row in rows]


def _query_historial_variaciones(
    db: Session,
    *,
    producto_id: Optional[int],
    proveedor: Optional[str],
    desde: Optional[date],
    hasta: Optional[date],
) -> List[Dict[str, Any]]:
    where = ["1=1"]
    params: Dict[str, Any] = {}

    if producto_id is not None:
        where.append("h.producto_id = :producto_id")
        params["producto_id"] = producto_id
    if proveedor:
        where.append(
            "(h.proveedor_codigo LIKE :proveedor OR h.proveedor_nombre LIKE :proveedor)"
        )
        params["proveedor"] = f"%{proveedor}%"
    if desde is not None:
        where.append("h.fecha_precio >= :desde")
        params["desde"] = desde
    if hasta is not None:
        where.append("h.fecha_precio <= :hasta")
        params["hasta"] = hasta

    rows = db.execute(
        text(
            """
            SELECT
                h.id,
                h.producto_id,
                p.codigo AS producto_codigo,
                p.nombre AS producto_nombre,
                h.proveedor_codigo,
                h.proveedor_nombre,
                h.fecha_precio,
                h.precio_unitario,
                h.moneda,
                h.origen
            FROM precio_compra_hist h
            JOIN producto p ON p.id = h.producto_id
            WHERE """
            + " AND ".join(where)
            + " ORDER BY h.producto_id, h.proveedor_codigo, h.moneda, h.fecha_precio, h.id"
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _variacion_payload(
    *,
    base_row: Dict[str, Any],
    comp_row: Dict[str, Any],
    modo: str,
) -> Dict[str, Any]:
    precio_base = float(base_row["precio_unitario"])
    precio_nuevo = float(comp_row["precio_unitario"])
    variacion_abs = precio_nuevo - precio_base
    variacion_pct = None
    if precio_base != 0:
        variacion_pct = (variacion_abs / precio_base) * 100

    return {
        "modo": modo,
        "producto_id": int(comp_row["producto_id"]),
        "producto_codigo": comp_row["producto_codigo"],
        "producto_nombre": comp_row["producto_nombre"],
        "proveedor_codigo": comp_row["proveedor_codigo"],
        "proveedor_nombre": comp_row["proveedor_nombre"],
        "moneda": comp_row["moneda"],
        "fecha_base": base_row["fecha_precio"],
        "fecha_nueva": comp_row["fecha_precio"],
        "precio_base": precio_base,
        "precio_nuevo": precio_nuevo,
        "variacion_abs": variacion_abs,
        "variacion_pct": variacion_pct,
    }


def listar_variaciones_precios(
    db: Session,
    *,
    modo: str = "ultima_vs_anterior",
    producto_id: Optional[int] = None,
    proveedor: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    modo_normalizado = (modo or "ultima_vs_anterior").lower().strip()
    if modo_normalizado not in {"ultima_vs_anterior", "mensual", "entre_fechas"}:
        raise ValueError(
            "Modo inválido. Use: ultima_vs_anterior, mensual o entre_fechas"
        )
    if modo_normalizado == "entre_fechas" and (desde is None or hasta is None):
        raise ValueError("El modo entre_fechas requiere completar desde y hasta")

    rows = _query_historial_variaciones(
        db,
        producto_id=producto_id,
        proveedor=proveedor,
        desde=desde,
        hasta=hasta,
    )

    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for row in rows:
        key = (row["producto_id"], row["proveedor_codigo"], row["moneda"])
        grouped.setdefault(key, []).append(row)

    variaciones: List[Dict[str, Any]] = []

    if modo_normalizado == "ultima_vs_anterior":
        for values in grouped.values():
            if len(values) < 2:
                continue
            base_row = values[-2]
            comp_row = values[-1]
            variaciones.append(
                _variacion_payload(
                    base_row=base_row,
                    comp_row=comp_row,
                    modo=modo_normalizado,
                )
            )
    elif modo_normalizado == "mensual":
        for values in grouped.values():
            monthly_latest: Dict[tuple, Dict[str, Any]] = {}
            for row in values:
                month_key = (row["fecha_precio"].year, row["fecha_precio"].month)
                prev = monthly_latest.get(month_key)
                if prev is None or row["fecha_precio"] > prev["fecha_precio"] or (
                    row["fecha_precio"] == prev["fecha_precio"]
                    and int(row["id"]) > int(prev["id"])
                ):
                    monthly_latest[month_key] = row

            ordered_months = sorted(monthly_latest.keys())
            for index in range(1, len(ordered_months)):
                base_row = monthly_latest[ordered_months[index - 1]]
                comp_row = monthly_latest[ordered_months[index]]
                variaciones.append(
                    _variacion_payload(
                        base_row=base_row,
                        comp_row=comp_row,
                        modo=modo_normalizado,
                    )
                )
    else:
        for values in grouped.values():
            rows_by_date: Dict[date, Dict[str, Any]] = {}
            for row in values:
                current = rows_by_date.get(row["fecha_precio"])
                if current is None or int(row["id"]) > int(current["id"]):
                    rows_by_date[row["fecha_precio"]] = row

            base_row = rows_by_date.get(desde)
            comp_row = rows_by_date.get(hasta)
            if base_row is None or comp_row is None:
                continue
            variaciones.append(
                _variacion_payload(
                    base_row=base_row,
                    comp_row=comp_row,
                    modo=modo_normalizado,
                )
            )

    variaciones.sort(
        key=lambda item: (
            item["fecha_nueva"],
            abs(item["variacion_abs"]),
            item["producto_codigo"],
            item["proveedor_codigo"],
        ),
        reverse=True,
    )
    return variaciones[offset : offset + limit]


def exportar_variaciones_csv(rows: List[Dict[str, Any]]) -> io.BytesIO:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "modo",
            "producto_id",
            "producto_codigo",
            "producto_nombre",
            "proveedor_codigo",
            "proveedor_nombre",
            "moneda",
            "fecha_base",
            "fecha_nueva",
            "precio_base",
            "precio_nuevo",
            "variacion_abs",
            "variacion_pct",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["modo"],
                row["producto_id"],
                row["producto_codigo"],
                row["producto_nombre"],
                row["proveedor_codigo"],
                row.get("proveedor_nombre") or "",
                row["moneda"],
                row["fecha_base"],
                row["fecha_nueva"],
                row["precio_base"],
                row["precio_nuevo"],
                row["variacion_abs"],
                row["variacion_pct"],
            ]
        )
    data = io.BytesIO()
    data.write(output.getvalue().encode("utf-8-sig"))
    data.seek(0)
    return data


def exportar_variaciones_xlsx(rows: List[Dict[str, Any]]) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("No se pudo crear la hoja activa")
    ws.title = "variaciones"
    ws.append(
        [
            "modo",
            "producto_id",
            "producto_codigo",
            "producto_nombre",
            "proveedor_codigo",
            "proveedor_nombre",
            "moneda",
            "fecha_base",
            "fecha_nueva",
            "precio_base",
            "precio_nuevo",
            "variacion_abs",
            "variacion_pct",
        ]
    )
    for row in rows:
        ws.append(
            [
                row["modo"],
                row["producto_id"],
                row["producto_codigo"],
                row["producto_nombre"],
                row["proveedor_codigo"],
                row.get("proveedor_nombre") or "",
                row["moneda"],
                row["fecha_base"],
                row["fecha_nueva"],
                row["precio_base"],
                row["precio_nuevo"],
                row["variacion_abs"],
                row["variacion_pct"],
            ]
        )

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
