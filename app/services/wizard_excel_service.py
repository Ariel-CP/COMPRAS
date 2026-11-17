"""Plantilla integral y carga atómica de los cinco listados del Wizard OC."""

import hashlib
import io
import json
import math
import zipfile
from copy import copy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import jwt
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.plan_produccion_service import calcular_asistente_oc

RESOURCES = Path(__file__).resolve().parents[1] / "resources"
HEADERS: dict[str, list[str]] = json.loads(
    (RESOURCES / "wizard_oc_columnas.json").read_text(encoding="utf-8")
)
MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 10000
TABLES = {
    "Plan_PT": "plan_produccion_mensual",
    "Stock_MP": "stock_disponible_mes",
    "Stock_PT": "asistente_oc_stock_pt_mes",
    "Deuda_Clientes": "asistente_oc_deuda_cliente_mes",
    "LAF_Solicitado": "asistente_oc_laf_solicitado",
}
QUANTITIES = {
    "Plan_PT": "cantidad_planificada",
    "Stock_MP": "stock_disponible",
    "Stock_PT": "stock_pt",
    "Deuda_Clientes": "deuda_clientes",
}


class WorkbookError(ValueError):
    pass


class PreviewExpired(WorkbookError):
    pass


def previous_period(year: int, month: int) -> tuple[int, int]:
    previous = date(year, month, 1) - timedelta(days=1)
    return previous.year, previous.month


def catalog(db: Session) -> list[dict]:
    return [
        dict(row)
        for row in db.execute(
            text(
                "SELECT p.id, p.codigo, p.nombre, p.tipo_producto, p.rubro, u.codigo AS unidad "
                "FROM producto p JOIN unidad_medida u ON u.id=p.unidad_medida_id "
                "WHERE p.activo=1 ORDER BY p.codigo"
            )
        ).mappings()
    ]


def _snapshot(db: Session, year: int, month: int, lock: bool = False) -> dict:
    result = {}
    for sheet, table in TABLES.items():
        y, m = previous_period(year, month) if sheet == "Stock_MP" else (year, month)
        query = f"SELECT * FROM {table} WHERE anio=:anio AND mes=:mes ORDER BY id"
        if lock:
            query += " FOR UPDATE"
        result[sheet] = [
            dict(row)
            for row in db.execute(text(query), {"anio": y, "mes": m}).mappings()
        ]
    return result


def _fingerprint(snapshot: dict, products: list[dict]) -> str:
    content = json.dumps(
        [snapshot, products], sort_keys=True, default=str, ensure_ascii=False
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _text_cell(cell, value) -> None:
    cell.value = "" if value is None else str(value)
    cell.data_type = "s"
    cell.number_format = "@"


def template(db: Session, year: int, month: int) -> bytes:
    products = catalog(db)
    snapshot = _snapshot(db, year, month)
    wb = load_workbook(RESOURCES / "plantilla_integral_wizard_oc.xlsx")
    parameters = wb["Parametros"]
    parameters.cell(2, 1, 1)
    parameters.cell(2, 2, year)
    parameters.cell(2, 3, month)
    for column, sheet in enumerate(("Stock_MP", "Stock_PT", "Deuda_Clientes"), start=4):
        dates = {str(row["fecha_corte"]) for row in snapshot[sheet]}
        if len(dates) == 1:
            parameters.cell(2, column, date.fromisoformat(next(iter(dates))))
    parameters.cell(2, 7, "NO")
    by_id = {p["id"]: p for p in products}
    for sheet, quantity in QUANTITIES.items():
        ws = wb[sheet]
        existing = {row["producto_id"]: row[quantity] for row in snapshot[sheet]}
        selected = [
            p for p in products if (p["tipo_producto"] == "PT") == (sheet != "Stock_MP")
        ]
        for row_number, p in enumerate(selected, start=2):
            ws.row_dimensions[row_number].height = max(
                23, math.ceil(len(str(p["nombre"])) / 55) * 18
            )
            for column, value in enumerate(
                (p["codigo"], p["nombre"], p["unidad"]), start=1
            ):
                _text_cell(ws.cell(row_number, column), value)
            ws.cell(row_number, 4, existing.get(p["id"]))
            for column in range(1, 5):
                ws.cell(row_number, column)._style = copy(ws.cell(2, column)._style)
        ws.auto_filter.ref = f"A1:D{max(2, len(selected) + 1)}"
    ws = wb["LAF_Solicitado"]
    for row_number, item in enumerate(snapshot["LAF_Solicitado"], start=2):
        p = by_id.get(item["producto_id"])
        if p is None:
            # No ocultar un pedido existente de un artículo que ya no esté activo.
            raise WorkbookError(
                "Hay pedidos LAF de artículos inactivos. Revisalos antes de descargar la plantilla integral."
            )
        ws.row_dimensions[row_number].height = max(
            23, math.ceil(len(str(p["nombre"])) / 55) * 18
        )
        values = [
            p["codigo"],
            p["nombre"],
            p["unidad"],
            item["proveedor_nombre"],
            item["cantidad_total"],
            item["cantidad_q1"],
            item["cantidad_q2"],
            item["fecha_pedido"],
            item["fecha_entrega_estimada"],
            item["estado"],
            item["observaciones"],
        ]
        for column, value in enumerate(values, start=1):
            cell = ws.cell(row_number, column)
            cell._style = copy(ws.cell(2, column)._style)
            if column in (1, 2, 3, 4, 10, 11):
                _text_cell(cell, value)
            else:
                cell.value = value
    ws.auto_filter.ref = f"A1:K{max(2, len(snapshot['LAF_Solicitado']) + 1)}"
    buffer = io.BytesIO()
    wb.save(buffer)
    wb.close()
    return buffer.getvalue()


def _quantity(value) -> Decimal:
    if value is None or isinstance(value, (str, bool)):
        raise ValueError(
            "Ingresá un número de Excel. Una celda vacía no equivale a cero."
        )
    try:
        number = Decimal(str(value))
        if (
            not number.is_finite()
            or number < 0
            or number > Decimal("999999999999.999999")
        ):
            raise ValueError("Cantidad fuera de rango o negativa.")
        if number != number.quantize(Decimal("0.000001")):
            raise ValueError("Se admiten hasta 6 decimales.")
        return number
    except InvalidOperation:
        raise ValueError("Cantidad inválida.") from None


def _date(value) -> date:
    if isinstance(value, datetime):
        result = value.date()
    elif isinstance(value, date):
        result = value
    elif isinstance(value, str):
        result = date.fromisoformat(value.strip())
    else:
        raise ValueError("Ingresá una fecha de Excel o YYYY-MM-DD.")
    if result.year < 1000:
        raise ValueError("La fecha está fuera del rango admitido por la base.")
    return result


def _open(content: bytes):
    if not content or len(content) > MAX_BYTES:
        raise WorkbookError("El archivo está vacío o supera 20 MB.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > 2000
                or sum(item.file_size for item in entries) > 60 * 1024 * 1024
            ):
                raise WorkbookError(
                    "El contenido del Excel supera el tamaño permitido."
                )
            if any(
                "vbaproject" in item.filename.lower()
                or "externallinks/" in item.filename.lower()
                for item in entries
            ):
                raise WorkbookError("No se admiten macros ni vínculos externos.")
        return load_workbook(
            io.BytesIO(content), read_only=True, data_only=False, keep_links=False
        )
    except Exception as exc:
        if isinstance(exc, WorkbookError):
            raise
        raise WorkbookError(
            "No se pudo leer el archivo XLSX. Usá la plantilla integral del Wizard."
        ) from None


def validate(content: bytes, products: list[dict]) -> tuple[dict, dict | None]:
    errors = []
    error_count = 0

    def error(sheet, row, field, message):
        nonlocal error_count
        error_count += 1
        if len(errors) < 100:
            errors.append(
                {"hoja": sheet, "fila": row, "campo": field, "mensaje": message}
            )

    by_code = {str(p["codigo"]).strip().upper(): p for p in products}
    rows = {}
    wb = _open(content)
    try:
        for sheet, headers in HEADERS.items():
            if sheet not in wb.sheetnames:
                error(sheet, 1, "hoja", "Falta la hoja requerida.")
                continue
            ws = wb[sheet]
            if ws.max_row > MAX_ROWS + 1 or ws.max_column > len(headers):
                error(
                    sheet,
                    1,
                    "tamaño",
                    "Demasiadas filas o columnas. Conservá el formato de la plantilla.",
                )
                continue
            actual = [
                cell.value
                for cell in next(
                    ws.iter_rows(min_row=1, max_row=1, max_col=len(headers))
                )
            ]
            if actual != headers:
                error(
                    sheet,
                    1,
                    "encabezados",
                    "Conservá los encabezados y su orden: " + ", ".join(headers),
                )
                continue
            data = []
            for row_number, cells in enumerate(
                ws.iter_rows(min_row=2, max_col=len(headers)), start=2
            ):
                values = [cell.value for cell in cells]
                if all(value is None or value == "" for value in values):
                    continue
                if any(
                    cell.data_type == "f" or cell.data_type == "e" for cell in cells
                ):
                    error(
                        sheet,
                        row_number,
                        "fórmula",
                        "Pegá valores, sin fórmulas ni errores de Excel.",
                    )
                    continue
                data.append((row_number, dict(zip(headers, values))))
            rows[sheet] = data
    finally:
        wb.close()
    if any(sheet not in rows for sheet in HEADERS):
        return {"valido": False, "errores": errors, "total_errores": error_count}, None
    params = rows["Parametros"]
    if len(params) != 1:
        error(
            "Parametros",
            2,
            "parámetros",
            "Debe haber exactamente una fila de parámetros.",
        )
        return {"valido": False, "errores": errors, "total_errores": error_count}, None
    _, p = params[0]
    try:
        if p["version"] != 1 or isinstance(p["version"], bool):
            raise ValueError("Versión de plantilla no admitida.")
        year, month = p["anio"], p["mes"]
        if (
            isinstance(year, bool)
            or isinstance(month, bool)
            or not isinstance(year, (int, float))
            or not isinstance(month, (int, float))
            or year != int(year)
            or month != int(month)
            or not 2000 <= year <= 2100
            or not 1 <= month <= 12
        ):
            raise ValueError("Año entre 2000 y 2100 y mes entre 1 y 12, como enteros.")
        year, month = int(year), int(month)
        dates = {
            key: _date(p[key])
            for key in ("fecha_corte_mp", "fecha_corte_pt", "fecha_corte_deuda")
        }
        stock_year, stock_month = previous_period(year, month)
        if (dates["fecha_corte_mp"].year, dates["fecha_corte_mp"].month) != (
            stock_year,
            stock_month,
        ):
            raise ValueError(
                "La fecha de corte MP debe pertenecer al mes anterior al plan."
            )
        no_laf = str(p["sin_laf"] or "").strip().upper()
        if no_laf not in {"SI", "NO"}:
            raise ValueError("sin_laf debe ser SI o NO.")
    except (ValueError, TypeError, OverflowError) as exc:
        error("Parametros", 2, "parámetros", str(exc))
        return {"valido": False, "errores": errors, "total_errores": error_count}, None
    batch = {"anio": year, "mes": month, "fechas": dates, "listas": {}}
    for sheet in TABLES:
        normalized = []
        seen = set()
        for row_number, item in rows[sheet]:
            try:
                raw = item["codigo"]
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError(
                        "El código debe ser texto y existir en el catálogo."
                    )
                code = raw.strip().upper()
                product = by_code.get(code)
                if product is None:
                    raise ValueError("Código desconocido o artículo inactivo.")
                is_pt = product["tipo_producto"] == "PT"
                if sheet != "LAF_Solicitado" and is_pt != (sheet != "Stock_MP"):
                    raise ValueError("Tipo de artículo incorrecto para esta hoja.")
                if str(item["unidad"] or "").strip() != str(product["unidad"]):
                    raise ValueError(
                        "Unidad distinta del catálogo. No se realizan conversiones."
                    )
                record = {"producto_id": int(product["id"])}
                if sheet in QUANTITIES:
                    if code in seen:
                        raise ValueError("Código duplicado en la hoja.")
                    seen.add(code)
                    field = QUANTITIES[sheet]
                    record[field] = _quantity(item[field])
                else:
                    if (
                        product["tipo_producto"] != "MP"
                        or "LAF" not in str(product.get("rubro") or "").upper()
                    ):
                        raise ValueError(
                            "El artículo no es una materia prima LAF activa."
                        )
                    provider = str(item["proveedor_nombre"] or "").strip()
                    notes = str(item["observaciones"] or "").strip()
                    if not provider or len(provider) > 160 or len(notes) > 255:
                        raise ValueError(
                            "Proveedor obligatorio (máx. 160 caracteres) y observaciones máx. 255."
                        )
                    for field in ("cantidad_total", "cantidad_q1", "cantidad_q2"):
                        record[field] = _quantity(item[field])
                    if (
                        record["cantidad_q1"] + record["cantidad_q2"]
                        > record["cantidad_total"]
                    ):
                        raise ValueError("Q1 + Q2 no puede superar cantidad_total.")
                    state = str(item["estado"] or "").strip().upper()
                    if state not in {"PENDIENTE", "PARCIAL", "RECIBIDO", "CANCELADO"}:
                        raise ValueError("Estado LAF inválido.")
                    record.update(
                        proveedor_nombre=provider,
                        observaciones=notes or None,
                        estado=state,
                    )
                    for field in ("fecha_pedido", "fecha_entrega_estimada"):
                        record[field] = (
                            _date(item[field]) if item[field] is not None else None
                        )
                    key = json.dumps(record, sort_keys=True, default=str)
                    if key in seen:
                        raise ValueError(
                            "Pedido LAF idéntico duplicado. Revisá las filas."
                        )
                    seen.add(key)
                normalized.append(record)
            except (ValueError, TypeError) as exc:
                error(sheet, row_number, "datos", str(exc))
        if sheet in QUANTITIES:
            expected = {
                str(p["codigo"]).strip().upper()
                for p in products
                if (p["tipo_producto"] == "PT") == (sheet != "Stock_MP")
            }
            missing = expected - seen
            if missing:
                error(
                    sheet,
                    2,
                    "cobertura",
                    f"Faltan {len(missing)} códigos activos. Conservá el listado completo y escribí cero cuando corresponda.",
                )
            if not normalized:
                error(sheet, 2, "listado", "El listado no puede estar vacío.")
        batch["listas"][sheet] = normalized
    if no_laf == "SI" and rows["LAF_Solicitado"]:
        error("LAF_Solicitado", 2, "sin_laf", "sin_laf=SI requiere la hoja LAF vacía.")
    if no_laf == "NO" and not rows["LAF_Solicitado"]:
        error(
            "LAF_Solicitado",
            2,
            "sin_laf",
            "Cargá los pedidos o confirmá sin_laf=SI en Parametros.",
        )
    report = {
        "valido": error_count == 0,
        "errores": errors,
        "total_errores": error_count,
        "anio": year,
        "mes": month,
        "anio_stock": stock_year,
        "mes_stock": stock_month,
        "filas": {sheet: len(items) for sheet, items in batch["listas"].items()},
    }
    return report, batch if error_count == 0 else None


def preview(db: Session, content: bytes, user_id: int) -> dict:
    products = catalog(db)
    report, batch = validate(content, products)
    if batch is None:
        return report
    snapshot = _snapshot(db, batch["anio"], batch["mes"])
    report["existentes"] = {sheet: len(items) for sheet, items in snapshot.items()}
    report["token"] = jwt.encode(
        {
            "purpose": "wizard_excel",
            "user": user_id,
            "file": hashlib.sha256(content).hexdigest(),
            "state": _fingerprint(snapshot, products),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        get_settings().auth_secret_key,
        algorithm="HS256",
    )
    return report


def import_and_calculate(db: Session, content: bytes, token: str, user_id: int) -> dict:
    try:
        claims = jwt.decode(token, get_settings().auth_secret_key, algorithms=["HS256"])
        if (
            claims.get("purpose") != "wizard_excel"
            or claims.get("user") != user_id
            or claims.get("file") != hashlib.sha256(content).hexdigest()
        ):
            raise PreviewExpired(
                "La confirmación no corresponde al archivo o usuario. Validá nuevamente."
            )
    except jwt.PyJWTError:
        raise PreviewExpired(
            "La validación venció o no es válida. Validá nuevamente el archivo."
        ) from None
    try:
        products = catalog(db)
        report, batch = validate(content, products)
        if batch is None:
            raise WorkbookError(
                "El archivo ya no es válido. Validalo nuevamente para ver los errores."
            )
        year, month = batch["anio"], batch["mes"]
        snapshot = _snapshot(db, year, month, lock=True)
        if claims.get("state") != _fingerprint(snapshot, products):
            raise PreviewExpired(
                "Los datos del período o catálogo cambiaron. Descargá o validá nuevamente antes de guardar."
            )
        for sheet, quantity in QUANTITIES.items():
            y, m = (
                previous_period(year, month) if sheet == "Stock_MP" else (year, month)
            )
            columns = ["anio", "mes", "producto_id", quantity]
            extra = {}
            if sheet != "Plan_PT":
                field = {
                    "Stock_MP": "fecha_corte_mp",
                    "Stock_PT": "fecha_corte_pt",
                    "Deuda_Clientes": "fecha_corte_deuda",
                }[sheet]
                columns += ["fecha_corte", "origen"]
                extra = {
                    "fecha_corte": batch["fechas"][field],
                    "origen": "ERP_FLEXXUS" if sheet == "Stock_MP" else "IMPORT_CSV",
                }
            sql = (
                f"INSERT INTO {TABLES[sheet]} ({','.join(columns)}) "
                f"VALUES ({','.join(':'+c for c in columns)}) ON DUPLICATE KEY UPDATE "
                + ",".join(
                    f"{c}=VALUES({c})"
                    for c in columns
                    if c not in {"anio", "mes", "producto_id"}
                )
            )
            items = [
                {"anio": y, "mes": m, **item, **extra}
                for item in batch["listas"][sheet]
            ]
            db.execute(text(sql), items)
        # LAF es una lista completa: reemplazar solo el período evita duplicar pedidos al reimportar.
        db.execute(
            text(
                "DELETE FROM asistente_oc_laf_solicitado WHERE anio=:anio AND mes=:mes"
            ),
            {"anio": year, "mes": month},
        )
        laf = batch["listas"]["LAF_Solicitado"]
        if laf:
            columns = ["anio", "mes", *laf[0].keys()]
            sql = f"INSERT INTO asistente_oc_laf_solicitado ({','.join(columns)}) VALUES ({','.join(':'+c for c in columns)})"
            db.execute(
                text(sql), [{"anio": year, "mes": month, **item} for item in laf]
            )
        calculation = calcular_asistente_oc(
            db, month, year, persistir_sugerencias=False
        )
        db.commit()
        return {"importacion": report, "calculo": calculation}
    except Exception:
        db.rollback()
        raise
