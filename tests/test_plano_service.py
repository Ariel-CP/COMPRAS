import pytest

from app.api import recepcion_api
from app.services.plano_service import obtener_metadatos_plano, obtener_plano_pdf
from pypdf import PdfWriter


def test_obtener_plano_pdf_selecciona_la_revision_mas_alta(tmp_path):
    for revision in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        (tmp_path / f"1234-{revision}.pdf").write_bytes(revision.encode("ascii"))
    (tmp_path / "1234.pdf").write_bytes(b"sin revision")

    assert obtener_plano_pdf("1234", str(tmp_path)) == tmp_path / "1234-Z.pdf"
    assert obtener_plano_pdf("1234-B", str(tmp_path)) == tmp_path / "1234-B.pdf"


@pytest.mark.parametrize("numero_plano", ["123", "12345", "12A4", "../123"])
def test_obtener_plano_pdf_rechaza_codigo_invalido(tmp_path, numero_plano):
    with pytest.raises(ValueError):
        obtener_plano_pdf(numero_plano, str(tmp_path))


def test_obtener_plano_pdf_informa_si_no_existe(tmp_path):
    with pytest.raises(FileNotFoundError):
        obtener_plano_pdf("1234", str(tmp_path))


def test_obtener_metadatos_plano_lee_campos_pdf(tmp_path):
    path = tmp_path / "1234-A.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata(
        {
            "/Title": "Plano de prueba",
            "/Author": "Ingeniería",
            "/Subject": "Conjunto soporte",
            "/Keywords": "soporte, prueba",
        }
    )
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)

    metadata = obtener_metadatos_plano("1234-A", str(tmp_path))

    assert metadata == {
        "titulo": "Plano de prueba",
        "autor": "Ingeniería",
        "asunto": "Conjunto soporte",
        "palabras_clave": "soporte, prueba",
        "productor_pdf": "pypdf",
    }


def test_obtener_metadatos_plano_sin_metadatos_devuelve_vacio(tmp_path):
    path = tmp_path / "5678.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)

    assert obtener_metadatos_plano("5678", str(tmp_path)) == {
        "productor_pdf": "pypdf",
    }


def test_abrir_plano_pdf_responde_inline(monkeypatch, tmp_path):
    plano = tmp_path / "1234-C.pdf"
    plano.write_bytes(b"%PDF-test")
    monkeypatch.setattr(recepcion_api, "obtener_plano_pdf", lambda _codigo: plano)

    response = recepcion_api.abrir_plano_pdf("1234", _current_user={})

    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")


def test_obtener_ultima_version_devuelve_numero_con_revision(monkeypatch, tmp_path):
    plano = tmp_path / "1234-C.pdf"
    plano.write_bytes(b"%PDF-test")
    monkeypatch.setattr(recepcion_api, "obtener_plano_pdf", lambda _codigo: plano)

    result = recepcion_api.obtener_ultima_version_plano("1234", _current_user={})

    assert result == {"numero_plano": "1234-C", "archivo": "1234-C.pdf"}
