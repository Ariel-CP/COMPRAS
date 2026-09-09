from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services import mbom_costos
from app.services.tipo_cambio_service import obtener_tasa_cercana


def _build_session(rows):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tipo_cambio_hist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha DATE NOT NULL,
                    moneda TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    tasa DECIMAL(18,6) NOT NULL,
                    origen TEXT NOT NULL DEFAULT 'MANUAL',
                    notas TEXT NULL,
                    fecha_creacion TIMESTAMP NULL
                )
                """
            )
        )
        if rows:
            conn.execute(
                text(
                    """
                    INSERT INTO tipo_cambio_hist
                    (fecha, moneda, tipo, tasa, origen)
                    VALUES (:fecha, :moneda, :tipo, :tasa, :origen)
                    """
                ),
                [
                    {
                        "fecha": row[0],
                        "moneda": row[1],
                        "tipo": row[2],
                        "tasa": row[3],
                        "origen": row[4],
                    }
                    for row in rows
                ],
            )
    return Session(engine)


def test_obtener_tasa_cercana_usa_ultima_anterior_no_futura():
    with _build_session(
        [
            (date(2025, 5, 15), "USD", "PROMEDIO", 1400.0, "MANUAL"),
            (date(2025, 5, 18), "USD", "PROMEDIO", 1430.0, "MANUAL"),
        ]
    ) as session:
        tasa = obtener_tasa_cercana(session, "USD", date(2025, 5, 17), "PROMEDIO")

    assert tasa is not None
    assert tasa["tasa"] == 1400.0
    assert tasa["origen_busqueda"] == "anterior"


def test_obtener_tasa_cercana_sin_anterior_no_usa_futura():
    with _build_session(
        [
            (date(2025, 5, 18), "USD", "PROMEDIO", 1430.0, "MANUAL"),
        ]
    ) as session:
        tasa = obtener_tasa_cercana(session, "USD", date(2025, 5, 17), "PROMEDIO")

    assert tasa is None


def test_convertir_ars_a_usd_usa_tasa_historia_anterior():
    with _build_session(
        [
            (date(2025, 5, 15), "USD", "PROMEDIO", 1400.0, "MANUAL"),
            (date(2025, 5, 18), "USD", "PROMEDIO", 1430.0, "MANUAL"),
        ]
    ) as session:
        resultado = mbom_costos._convertir_ars_a_usd(session, 4595.04, date(2025, 5, 17))

    assert abs(resultado["valor_base"] - (4595.04 / 1400.0)) < 1e-9
    assert resultado["detalle_fx"]["origen_busqueda"] == "anterior"


def test_resolver_tasa_hist_usa_prioridad_venta_para_usd_may():
    with _build_session(
        [
            (date(2025, 5, 11), "USD_MAY", "PROMEDIO", 1010.0, "MANUAL"),
            (date(2025, 5, 11), "USD_MAY", "VENTA", 1035.0, "MANUAL"),
            (date(2025, 5, 20), "USD_MAY", "PROMEDIO", 1100.0, "MANUAL"),
            (date(2025, 5, 20), "USD_MAY", "VENTA", 1120.0, "MANUAL"),
        ]
    ) as session:
        tasa = mbom_costos._resolver_tasa_hist(session, "USD_MAY", date(2025, 5, 17))

    assert tasa is not None
    assert tasa["tipo_sugerido"] == "VENTA"
    assert tasa["tasa"] == 1035.0


def test_convertir_base_a_ars_usa_tipo_sugerido_para_usd_may():
    with _build_session(
        [
            (date(2025, 5, 11), "USD_MAY", "PROMEDIO", 1010.0, "MANUAL"),
            (date(2025, 5, 11), "USD_MAY", "VENTA", 1035.0, "MANUAL"),
            (date(2025, 5, 20), "USD_MAY", "PROMEDIO", 1100.0, "MANUAL"),
            (date(2025, 5, 20), "USD_MAY", "VENTA", 1120.0, "MANUAL"),
            (date(2025, 5, 17), "USD", "PROMEDIO", 1400.0, "MANUAL"),
        ]
    ) as session:
        resultado = mbom_costos._convertir_base_a_ars(session, 10.0, "USD_MAY", date(2025, 5, 17))

    assert abs(resultado["valor_ars"] - (10.0 * 1035.0)) < 1e-9
    assert resultado["detalle"]["origen_busqueda"] == "anterior"


def test_calcular_costos_internal_aplica_merma_3_por_ciento():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tipo_cambio_hist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha DATE NOT NULL,
                    moneda TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    tasa DECIMAL(18,6) NOT NULL,
                    origen TEXT NOT NULL DEFAULT 'MANUAL',
                    notas TEXT NULL,
                    fecha_creacion TIMESTAMP NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE producto (
                    id INTEGER PRIMARY KEY,
                    codigo TEXT,
                    nombre TEXT,
                    rubro TEXT,
                    tipo_producto TEXT,
                    activo INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE unidad_medida (
                    id INTEGER PRIMARY KEY,
                    codigo TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE costo_producto (
                    id INTEGER PRIMARY KEY,
                    producto_id INTEGER,
                    costo_unitario DECIMAL(18,6),
                    moneda TEXT,
                    vigencia_desde DATE,
                    vigencia_hasta DATE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE mbom_detalle (
                    id INTEGER PRIMARY KEY,
                    mbom_id INTEGER,
                    componente_producto_id INTEGER,
                    cantidad DECIMAL(18,6),
                    unidad_medida_id INTEGER,
                    factor_merma DECIMAL(18,6),
                    renglon INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO producto (id, codigo, nombre, rubro, tipo_producto, activo) VALUES (:id, :codigo, :nombre, :rubro, :tipo_producto, :activo)"
            ),
            {"id": 1, "codigo": "M1", "nombre": "Material", "rubro": "R1", "tipo_producto": "MP", "activo": 1},
        )
        conn.execute(
            text(
                "INSERT INTO unidad_medida (id, codigo) VALUES (:id, :codigo)"
            ),
            {"id": 1, "codigo": "KG"},
        )
        conn.execute(
            text(
                "INSERT INTO costo_producto (producto_id, costo_unitario, moneda, vigencia_desde, vigencia_hasta) VALUES (:producto_id, :costo_unitario, :moneda, :vigencia_desde, :vigencia_hasta)"
            ),
            {"producto_id": 1, "costo_unitario": 2.0, "moneda": "USD", "vigencia_desde": date(2025, 5, 15), "vigencia_hasta": None},
        )
        conn.execute(
            text(
                "INSERT INTO mbom_detalle (mbom_id, componente_producto_id, cantidad, unidad_medida_id, factor_merma, renglon) VALUES (:mbom_id, :componente_producto_id, :cantidad, :unidad_medida_id, :factor_merma, :renglon)"
            ),
            {"mbom_id": 10, "componente_producto_id": 1, "cantidad": 3.0, "unidad_medida_id": 1, "factor_merma": 0.03, "renglon": 1},
        )
        conn.execute(
            text(
                "INSERT INTO tipo_cambio_hist (fecha, moneda, tipo, tasa, origen) VALUES (:fecha, :moneda, :tipo, :tasa, :origen)"
            ),
            {"fecha": date(2025, 5, 15), "moneda": "USD", "tipo": "PROMEDIO", "tasa": 1000.0, "origen": "MANUAL"},
        )
    with Session(engine) as session:
        resultado = mbom_costos._calcular_costos_internal(session, 10, {}, set())

    assert resultado["total"] == 6180.0
    assert resultado["componentes"][0]["factor_merma"] == 0.03
