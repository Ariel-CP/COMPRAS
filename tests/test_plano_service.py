import pytest

from app.api import recepcion_api
from app.services.plano_service import obtener_plano_pdf


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
