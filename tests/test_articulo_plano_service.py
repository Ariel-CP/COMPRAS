from app.services.articulo_plano_service import listar_articulos_con_planos
from app.services.plano_service import catalogar_planos_pdf, resolver_plano_catalogado


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeDatabase:
    def __init__(self, rows, mbom_rows=None):
        self.rows = rows
        self.mbom_rows = mbom_rows or []
        self.statement = None
        self.parameters = None

    def execute(self, statement, parameters):
        self.statement = str(statement)
        self.parameters = parameters
        rows = self.mbom_rows if "FROM mbom_cabecera cab" in self.statement else self.rows
        return FakeRows(rows)


def test_catalogar_planos_elige_revision_mas_alta_y_ignora_otros_nombres(tmp_path):
    (tmp_path / "1234-A.pdf").write_bytes(b"A")
    (tmp_path / "1234-C.pdf").write_bytes(b"C")
    (tmp_path / "5678.pdf").write_bytes(b"base")
    (tmp_path / "manual.pdf").write_bytes(b"otro")

    catalogo = catalogar_planos_pdf(str(tmp_path))

    assert resolver_plano_catalogado("1234", catalogo).name == "1234-C.pdf"
    assert resolver_plano_catalogado("1234-A", catalogo).name == "1234-A.pdf"
    assert resolver_plano_catalogado("5678", catalogo).name == "5678.pdf"
    assert resolver_plano_catalogado("9999", catalogo) is None


def test_listar_articulos_con_planos_relaciona_por_sufijo_de_codigo(tmp_path):
    (tmp_path / "1234-B.pdf").write_bytes(b"pdf")
    (tmp_path / "1234-C.pdf").write_bytes(b"ultima revision")
    (tmp_path / "2345.pdf").write_bytes(b"pdf sin asociacion")
    db = FakeDatabase(
        [
            {
                "producto_id": 4,
                "articulo_codigo": "ART-1234",
                "articulo_nombre": "Soporte lateral",
                "tipo_producto": "PT",
                "descripcion": "Plano general del soporte",
            },
            {
                "producto_id": 8,
                "articulo_codigo": "WIP-TAPA-1234",
                "articulo_nombre": "Tapa de soporte",
                "tipo_producto": "WIP",
                "descripcion": "Plano detallado de la tapa",
            },
            {
                "producto_id": 9,
                "articulo_codigo": "ART-2345",
                "articulo_nombre": "Soporte de motor",
                "tipo_producto": "WIP",
                "descripcion": None,
            },
            {
                "producto_id": 10,
                "articulo_codigo": "ART-12X4",
                "articulo_nombre": "Código sin sufijo numérico",
                "tipo_producto": "MP",
                "descripcion": None,
            },
        ],
        mbom_rows=[
            {
                "componente_producto_id": 8,
                "producto_padre_id": 20,
                "padre_codigo": "PT-0020",
                "padre_nombre": "Equipo armado",
            }
        ],
    )

    articulos = listar_articulos_con_planos(db, directorio=str(tmp_path))

    por_numero = {item["numero_plano"]: item for item in articulos}
    assert len(articulos) == 3
    assert por_numero["1234-B"]["archivo"] == "1234-B.pdf"
    assert por_numero["1234-B"]["pdf_url"].endswith("/1234-B/pdf")
    assert por_numero["1234-B"]["descripcion"] == "Plano detallado de la tapa; Plano general del soporte"
    assert por_numero["1234-B"]["articulos_texto"] == "ART-1234 · Soporte lateral, WIP-TAPA-1234 · Tapa de soporte"
    assert por_numero["1234-B"]["codigos_articulo"] == ["ART-1234", "WIP-TAPA-1234"]
    assert por_numero["1234-B"]["nombres_articulo"] == ["Soporte lateral", "Tapa de soporte"]
    assert por_numero["1234-B"]["producto_ids"] == [4, 8]
    assert por_numero["1234-B"]["asociado"] is True
    assert por_numero["1234-B"]["tiene_revision"] is True
    assert por_numero["1234-B"]["es_semielaborado"] is True
    assert por_numero["1234-B"]["usado_en_mbom"] is True
    assert por_numero["1234-B"]["mbom_padres_texto"] == "PT-0020 · Equipo armado"
    assert por_numero["1234-C"]["articulos_texto"] == por_numero["1234-B"]["articulos_texto"]
    assert por_numero["1234-C"]["producto_ids"] == [4, 8]
    assert por_numero["2345"]["articulos_texto"] == "ART-2345 · Soporte de motor"
    assert por_numero["2345"]["descripcion"] == "Sin descripción registrada."
    assert por_numero["2345"]["asociado"] is True
    assert por_numero["2345"]["tiene_revision"] is False
    assert por_numero["2345"]["producto_ids"] == [9]
    assert por_numero["2345"]["es_semielaborado"] is True
    assert por_numero["2345"]["usado_en_mbom"] is False
    assert por_numero["2345"]["mbom_padres"] == []
    assert db.parameters == {}


def test_listar_articulos_con_planos_filtra_catalogo_completo(tmp_path):
    (tmp_path / "1234-B.pdf").write_bytes(b"pdf")
    (tmp_path / "2345.pdf").write_bytes(b"pdf")
    db = FakeDatabase([])

    planos = listar_articulos_con_planos(db, "1234", str(tmp_path))

    assert [plano["numero_plano"] for plano in planos] == ["1234-B"]
