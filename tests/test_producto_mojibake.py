from app.services.producto_service import (
    _fix_mojibake_text,
    _to_mojibake_variant,
)


def test_fix_mojibake_decodes_windows_1252_tilde_character():
    assert _fix_mojibake_text("A\u00c3\u02dcO") == "A\u00d8O"


def test_fix_mojibake_keeps_latin1_fallback():
    assert _fix_mojibake_text("M\u00c3\u00a1quina") == "M\u00e1quina"


def test_search_variant_uses_windows_1252_for_tilde_character():
    assert _to_mojibake_variant("A\u00d8O") == "A\u00c3\u02dcO"


def test_fix_mixed_mojibake_sequences_with_windows_control_bytes():
    damaged = "GARANT\u00c3\u008dA 1 A\u00c3\u2018O"
    assert _fix_mojibake_text(damaged) == "GARANT\u00cdA 1 A\u00d1O"
