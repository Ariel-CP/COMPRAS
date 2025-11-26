from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.schemas.tipo_cambio import (
    TipoCambioCreate,
    TipoCambioUpdate,
    TipoCambioFiltro,
)


def listar_tipos_cambio(
    conn: Connection, filtro: TipoCambioFiltro
) -> List[dict]:
    """Lista tipos de cambio con filtros opcionales."""
    clauses = []
    params = {}
    if filtro.moneda:
        clauses.append("moneda = :moneda")
        params["moneda"] = filtro.moneda
    if filtro.tipo:
        clauses.append("tipo = :tipo")
        params["tipo"] = filtro.tipo
    if filtro.desde:
        clauses.append("fecha >= :desde")
        params["desde"] = filtro.desde
    if filtro.hasta:
        clauses.append("fecha <= :hasta")
        params["hasta"] = filtro.hasta

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
    SELECT id, fecha, moneda, tipo, tasa, origen, notas, fecha_creacion
    FROM tipo_cambio_hist
    {where_sql}
    ORDER BY fecha DESC, moneda, tipo
    """.strip()
    result = conn.execute(text(sql), params)
    rows = []
    for r in result:
        row_dict = dict(r._mapping)
        # Convertir tipos no serializables a JSON
        if row_dict.get("fecha"):
            row_dict["fecha"] = row_dict["fecha"].isoformat()
        if row_dict.get("fecha_creacion"):
            row_dict["fecha_creacion"] = row_dict["fecha_creacion"].isoformat()
        if row_dict.get("tasa"):
            row_dict["tasa"] = float(row_dict["tasa"])
        rows.append(row_dict)
    return rows


def upsert_tipo_cambio(
    conn: Connection, data: TipoCambioCreate
) -> Tuple[bool, int]:
    """Inserta o actualiza (si existe por PK única) un tipo de cambio.
    Devuelve (insertado, id).
    """
    # Intentar obtener existente
    sel = text("""
        SELECT id FROM tipo_cambio_hist
        WHERE moneda=:moneda AND fecha=:fecha AND tipo=:tipo
    """)
    existing = conn.execute(
        sel,
        {"moneda": data.moneda, "fecha": data.fecha, "tipo": data.tipo},
    ).fetchone()
    if existing:
        upd = text("""
            UPDATE tipo_cambio_hist
            SET tasa=:tasa, origen=:origen, notas=:notas
            WHERE id=:id
        """)
        conn.execute(
            upd,
            {
                "tasa": data.tasa,
                "origen": data.origen,
                "notas": data.notas,
                "id": existing.id,
            },
        )
        return False, existing.id
    ins = text("""
        INSERT INTO tipo_cambio_hist (fecha, moneda, tipo, tasa, origen, notas)
        VALUES (:fecha, :moneda, :tipo, :tasa, :origen, :notas)
    """)
    res = conn.execute(ins, {
        "fecha": data.fecha,
        "moneda": data.moneda,
        "tipo": data.tipo,
        "tasa": data.tasa,
        "origen": data.origen,
        "notas": data.notas,
    })
    return True, res.lastrowid  # type: ignore[attr-defined]


def actualizar_tipo_cambio(
    conn: Connection, id_: int, data: TipoCambioUpdate
) -> bool:
    set_parts = []
    params = {"id": id_}
    if data.tasa is not None:
        set_parts.append("tasa=:tasa")
        params["tasa"] = data.tasa
    if data.origen is not None:
        set_parts.append("origen=:origen")
        params["origen"] = data.origen
    if data.notas is not None:
        set_parts.append("notas=:notas")
        params["notas"] = data.notas
    if not set_parts:
        return False
    sql = text(
        f"UPDATE tipo_cambio_hist SET {', '.join(set_parts)} WHERE id=:id"
    )
    res = conn.execute(sql, params)
    return res.rowcount > 0


def obtener_por_id(conn: Connection, id_: int) -> Optional[dict]:
    sql = text("""
        SELECT id, fecha, moneda, tipo, tasa, origen, notas, fecha_creacion
        FROM tipo_cambio_hist WHERE id=:id
    """)
    row = conn.execute(sql, {"id": id_}).fetchone()
    if not row:
        return None
    row_dict = dict(row._mapping)
    # Convertir tipos no serializables a JSON
    if row_dict.get("fecha"):
        row_dict["fecha"] = row_dict["fecha"].isoformat()
    if row_dict.get("fecha_creacion"):
        row_dict["fecha_creacion"] = row_dict["fecha_creacion"].isoformat()
    if row_dict.get("tasa"):
        row_dict["tasa"] = float(row_dict["tasa"])
    return row_dict


def bulk_import_csv(
    conn: Connection,
    contenido_csv: str,
    moneda: str = "USD",
    tipo: str = "VENTA",
    origen: str = "MANUAL",
) -> Tuple[int, int, List[str]]:
    """Importa CSV en memoria.
    Formato esperado (sin encabezado o con encabezado reconocible):
    fecha,tasa
    2025-01-02,1234.56
    Se ignoran líneas vacías. Se aceptan separadores "," o ";".
    """
    import csv
    from io import StringIO

    insertados = 0
    actualizados = 0
    errores: List[str] = []

    # Normalizar separadores ; a ,
    normalized = contenido_csv.replace(";", ",")
    f = StringIO(normalized)
    reader = csv.reader(f)

    # Detectar encabezado
    first_row_peek: List[str] = []
    try:
        first_row_peek = next(reader)
    except StopIteration:
        return 0, 0, ["Archivo vacío"]

    has_header = False
    if first_row_peek and any(
        h.lower() in ("fecha", "tasa") for h in first_row_peek
    ):
        has_header = True
    else:
        # procesar como datos, retroceder
        f.seek(0)
        reader = csv.reader(f)

    if has_header:
        # Re-crear reader para después del encabezado
        f.seek(0)
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            try:
                fecha_str = row.get("fecha") or row.get("Fecha")
                tasa_str = row.get("tasa") or row.get("Tasa")
                if not fecha_str or not tasa_str:
                    errores.append(f"Línea {idx}: faltan campos")
                    continue
                fecha_dt = date.fromisoformat(fecha_str.strip())
                tasa_val = float(tasa_str.strip())
                creado, _ = upsert_tipo_cambio(
                    conn,
                    TipoCambioCreate(
                        fecha=fecha_dt,
                        moneda=moneda,
                        tipo=tipo,
                        tasa=tasa_val,
                        origen=origen,
                        notas=None,
                    ),
                )
                if creado:
                    insertados += 1
                else:
                    actualizados += 1
            except Exception as e:  # noqa: BLE001
                errores.append(f"Línea {idx}: {e}")
    else:
        # Sin encabezado: columnas esperadas fecha,tasa
        for idx, cols in enumerate(reader, start=1):
            if not cols or len(cols) < 2:
                continue
            try:
                fecha_dt = date.fromisoformat(cols[0].strip())
                tasa_val = float(cols[1].strip())
                creado, _ = upsert_tipo_cambio(
                    conn,
                    TipoCambioCreate(
                        fecha=fecha_dt,
                        moneda=moneda,
                        tipo=tipo,
                        tasa=tasa_val,
                        origen=origen,
                        notas=None,
                    ),
                )
                if creado:
                    insertados += 1
                else:
                    actualizados += 1
            except Exception as e:  # noqa: BLE001
                errores.append(f"Línea {idx}: {e}")

    return insertados, actualizados, errores


def bulk_import_xlsx(
    conn: Connection,
    file_bytes: bytes,
    moneda: str = "USD",
    tipo: str = "VENTA",
    origen: str = "MANUAL",
    sheet_name: str | None = None,
) -> Tuple[int, int, List[str]]:
    """Importa datos desde un archivo XLSX en bytes.
    Se espera columnas con encabezados 'fecha' y 'tasa' (case-insensitive).
    Si no se encuentra sheet_name se usa la primera hoja.
    """
    from openpyxl import load_workbook  # lazy import

    insertados = 0
    actualizados = 0
    errores: List[str] = []

    from io import BytesIO
    try:
        wb = load_workbook(filename=BytesIO(file_bytes))
    except Exception as e:  # noqa: BLE001
        return 0, 0, [f"Error leyendo XLSX: {e}"]

    ws = (
        wb[sheet_name]
        if sheet_name and sheet_name in wb.sheetnames
        else wb.active
    )

    # Detectar encabezados
    header_row = None
    for row in ws.iter_rows(min_row=1, max_row=5):  # primeras filas
        values = [
            str(c.value).strip().lower() if c.value is not None else ""
            for c in row
        ]
        if "fecha" in values and "tasa" in values:
            header_row = row[0].row
            break
    if header_row is None:
        return 0, 0, [
            "No se encontró encabezado con columnas 'fecha' y 'tasa'"
        ]

    # Mapear índices
    headers = [
        str(c.value).strip().lower() if c.value is not None else ""
        for c in ws[header_row]
    ]
    try:
        idx_fecha = headers.index("fecha")
        idx_tasa = headers.index("tasa")
    except ValueError:
        return 0, 0, ["Encabezados inválidos"]

    for row in ws.iter_rows(min_row=header_row + 1):
        fecha_cell = row[idx_fecha].value
        tasa_cell = row[idx_tasa].value
        if fecha_cell in (None, "") or tasa_cell in (None, ""):
            continue
        try:
            # Convertir fecha si es datetime/date
            if hasattr(fecha_cell, "date"):
                fecha_dt = (
                    fecha_cell.date()
                    if hasattr(fecha_cell, "date")
                    else fecha_cell
                )
            else:
                fecha_dt = date.fromisoformat(str(fecha_cell).strip())
            tasa_val = float(str(tasa_cell).strip())
            creado, _ = upsert_tipo_cambio(
                conn,
                TipoCambioCreate(
                    fecha=fecha_dt,
                    moneda=moneda,
                    tipo=tipo,
                    tasa=tasa_val,
                    origen=origen,
                    notas=None,
                ),
            )
            if creado:
                insertados += 1
            else:
                actualizados += 1
        except Exception as e:  # noqa: BLE001
            errores.append(f"Fila {row[0].row}: {e}")

    return insertados, actualizados, errores
