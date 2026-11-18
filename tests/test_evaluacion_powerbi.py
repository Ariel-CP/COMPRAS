from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps_auth import get_current_user
from app.api.evaluacion_api import router
from app.services import evaluacion_powerbi_service as service


def maestro(codigo="12", nombre="Acero SA", evaluar=True):
    return {
        "CODIGO": codigo,
        "PROVEEDOR": nombre,
        "RAZON SOCIAL": nombre,
        "DEMORA_ENTREGA": 21,
        "APLICA CERTIFICADO_CALIDAD": True,
        "EVALUAR": evaluar,
        "INSUMO SERVICIO": "INSUMO",
        "CLASIFICACION": "CRITICO",
    }


def control(
    id=1,
    codigo="12",
    nombre="Acero SA",
    fecha=datetime(2026, 1, 20),
    plan="Simplificada",
):
    return {
        "ID_INT": id,
        "Codigo Proveedor": codigo,
        "PROVEEDOR": nombre,
        "Fecha de Entrega": fecha,
        "FECHA EMISION OC": datetime(2026, 1, 1),
        "Fecha Control": fecha,
        "PLAN MUESTREO": plan,
        "TieneCertificado": False,
        "Estado": "ACEPTADO",
    }


@pytest.fixture(autouse=True)
def cache_limpia():
    service._cache.clear()
    yield
    service._cache.clear()


def test_promedia_recepciones_en_lugar_del_ultimo_puntaje_y_no_suma_certificado():
    datos = service.analizar_fuentes(
        [control(), control(id=2, plan="Normal")], [maestro()]
    )
    r = datos["proveedores"][0]
    assert r["total"] == Decimal("82.575")
    assert r["certificado"] == 0
    assert r["recepciones"] == 2


def test_puntaje_general_promedia_recepciones_como_medidor_pbix_no_proveedores():
    datos = service.analizar_fuentes(
        [
            control(),
            control(id=2),
            control(id=3, codigo="13", nombre="Otro SA", plan="Normal"),
            control(id=4, codigo="99", nombre="Excluido"),
        ],
        [maestro(), maestro("13", "Otro SA"), maestro("99", "Excluido", evaluar=False)],
    )
    assert datos["resumen"]["puntaje_general"] == Decimal("85.05")
    assert datos["resumen"]["resultado_general"] == "APROBADO"
    assert datos["resumen"]["controles_evaluados"] == 3
    assert (
        datos["resumen"]["puntaje_general"]
        != sum(p["total"] for p in datos["proveedores"]) / 2
    )


@pytest.mark.parametrize(
    "nota",
    [
        "Se recibió el certificado de calidad.",
        "SE RECIBIERON LOS CERTIFICADOS.",
        "Recibimos el certificado.",
        "Se ha recibido el certificado de calidad.",
        "El proveedor entregó los respectivos certificados de calidad.",
        "CERTIFICADOS ENTREGADOS EL 10 DE SEPTIEMBRE.",
        "Presenta certificado de calidad.",
        "Se adjunta el certificado de calidad del lote.",
        "Se entregaron los certificados de calidad.",
        "Mercadería recibida con certificado de calidad.",
        "Vino con certificado de calidad.",
        "Dureza informada por Ternium mediante el certificado de calidad del material entregado.",
    ],
)
def test_nota_expresa_recepcion_o_uso_del_certificado(nota):
    fila = {**control(), "NOTA": nota}
    resultado = service.analizar_fuentes([fila], [maestro()])
    assert resultado["detalle"][0]["fuentes_certificado"] == ["NOTA"]
    assert resultado["proveedores"][0]["certificado"] == 10
    assert resultado["resumen"]["certificado_por_nota"] == 1


@pytest.mark.parametrize(
    "nota",
    [
        None,
        "Cumple con los requisitos del certificado de calidad y especificaciones técnicas.",
        "Cumple requisitos según certificado y especificaciones.",
        "No presenta el certificado correspondiente. Cumple con los requisitos del certificado de calidad.",
        "No se recibió el certificado de calidad.",
        "No se ha recibido el certificado de calidad.",
        "No recibimos el certificado.",
        "No vino con certificado de calidad.",
        "Se acepta sin certificado de calidad por falta de stock.",
        "Previo a tener el certificado por falta de stock.",
        "Certificado de calidad pendiente.",
        "Certificado no recibido.",
        "Pendiente el certificado.",
        "Solicitar certificado de calidad al proveedor.",
        "Se recibirá el certificado.",
        "Calibre tapón certificado. Se adjuntan fotos de la pieza.",
        "Manómetro enviado a certificar.",
    ],
)
def test_leyendas_ausencias_e_instrumentos_no_prueban_recepcion(nota):
    resultado = service.analizar_fuentes([{**control(), "NOTA": nota}], [maestro()])
    assert resultado["detalle"][0]["fuentes_certificado"] == []
    assert resultado["proveedores"][0]["certificado"] == 0


def test_adjuntos_genericos_suman_una_vez_y_conservan_conflicto_con_nota():
    fila = {
        **control(),
        "ADJUNTO": "WhatsApp Image 2026.jpeg;Scan10002.JPG",
        "NOTA": "No presenta el certificado. Cumple con los requisitos del certificado.",
    }
    resultado = service.analizar_fuentes([fila], [maestro()])
    assert resultado["detalle"][0]["fuentes_certificado"] == ["ADJUNTO"]
    assert resultado["detalle"][0]["certificado_nota_ausencia"]
    assert resultado["resumen"]["certificado_conflictos"] == 1
    assert resultado["resumen"]["controles_certificado_conflicto"] == [
        {"id": 1, "fecha": date(2026, 1, 20), "proveedor": "Acero SA"}
    ]
    assert resultado["proveedores"][0]["certificado"] == 10


def test_fuentes_coincidentes_no_duplican_puntos_y_respetan_no_aplica():
    fila = {
        **control(),
        "TieneCertificado": True,
        "ADJUNTO": "certificado.pdf",
        "NOTA": "Se recibió el certificado.",
    }
    datos = service.analizar_fuentes([fila], [maestro()])
    assert datos["detalle"][0]["fuentes_certificado"] == [
        "TieneCertificado",
        "ADJUNTO",
        "NOTA",
    ]
    assert datos["resumen"]["con_certificado"] == 1
    assert datos["proveedores"][0]["certificado"] == 10
    m = maestro()
    m["APLICA CERTIFICADO_CALIDAD"] = False
    assert service.analizar_fuentes([fila], [m])["proveedores"][0]["certificado"] == 0


def test_rechazos_se_asocian_por_identidad_y_no_modifican_puntaje():
    rechazado = control(id=2, codigo="0")
    rechazado["Estado"] = " RECHAZADO "
    datos = service.analizar_fuentes([control(), rechazado], [maestro()])
    r = datos["proveedores"][0]
    assert r["rechazos"] == 1
    assert r["controles_rechazados"] == [{"id": 2, "fecha": date(2026, 1, 20)}]
    assert r["total"] == Decimal("90")
    assert datos["detalle"][1]["codigo_origen"] == "0"


def test_identidad_cero_y_ambiguos_conserva_exclusiones():
    m = maestro()
    datos = service.analizar_fuentes(
        [control(codigo="0"), control(id=2, nombre="Desconocido", codigo="0")],
        [m, maestro("0", "YPF GAS SA")],
    )
    assert len(datos["proveedores"]) == 1
    assert datos["proveedores"][0]["codigo"] == "12"
    assert datos["resumen"]["identidad_por_nombre"] == 1
    assert datos["resumen"]["controles_excluidos"] == 1


def test_listados_exactamente_20_y_desempate_estable(monkeypatch):
    proveedores = [maestro(str(i), f"Proveedor {i:02}") for i in range(45)]
    controles = [
        control(id=i, codigo=str(i), nombre=f"Proveedor {i:02}") for i in range(45)
    ]
    monkeypatch.setattr(service, "leer_fuentes", lambda *args: (controles, proveedores))
    r = service.ranking_periodo(date(2026, 1, 1), date(2026, 7, 31))
    assert len(r["mejores_20"]) == len(r["peores_20"]) == 20
    assert r["mejores_20"][0]["nombre"] == "Proveedor 00"
    assert len(r["proveedores"]) == 45


def test_cache_devuelve_copias_y_no_cambia_resultados_de_otra_consulta(monkeypatch):
    llamadas = []

    def leer(*args):
        llamadas.append(args)
        return [control()], [maestro()]

    monkeypatch.setattr(service, "leer_fuentes", leer)
    r = service.ranking_periodo(date(2026, 1, 1), date(2026, 7, 31))
    r["proveedores"][0]["nombre"] = "Alterado"
    otro = service.ranking_periodo(date(2026, 1, 1), date(2026, 7, 31))
    assert otro["proveedores"][0]["nombre"] == "Acero SA"
    assert len(llamadas) == 1


def test_historia_ordena_periodos_y_respeta_limite_fuente(monkeypatch):
    controles = [
        control(id=1, fecha=datetime(2025, 12, 31)),
        control(id=2, fecha=datetime(2026, 1, 31)),
        control(id=3, fecha=datetime(2026, 7, 31)),
    ]
    llamadas = []

    def leer(desde, hasta):
        llamadas.append((desde, hasta))
        return controles, [maestro()]

    monkeypatch.setattr(service, "leer_fuentes", leer)
    r = service.historial_proveedor("012", date(2026, 7, 31), agrupacion="mensual")
    assert [p["periodo"] for p in r["serie"]] == ["2025-12", "2026-01", "2026-07"]
    assert llamadas == [(None, date(2026, 7, 31))]
    assert r["proveedor"]["recepciones"] == 3


def test_periodo_vacio_no_fabrica_evaluaciones(monkeypatch):
    monkeypatch.setattr(service, "leer_fuentes", lambda *args: ([], [maestro()]))
    r = service.ranking_periodo(date(2026, 1, 1), date(2026, 7, 31))
    assert r["proveedores"] == r["mejores_20"] == r["peores_20"] == []
    assert r["resumen"]["puntaje_general"] is None
    assert r["resumen"]["resultado_general"] is None


def test_no_revalua_no_marcados_y_no_oculta_duplicados():
    assert not service.analizar_fuentes([control()], [maestro(evaluar=False)])[
        "proveedores"
    ]
    with pytest.raises(service.AccessReadError, match="duplicados"):
        service.analizar_fuentes([control(), control()], [maestro()])


def test_lectura_parametrizada_incluye_hasta_y_cierra_conexion(monkeypatch):
    class Conexion:
        cerrada = False
        description = [("campo",)]
        llamadas = []

        def cursor(self):
            return self

        def execute(self, sql, params=None):
            self.llamadas.append((sql, params))

        def fetchall(self):
            return []

        def close(self):
            self.cerrada = True

    conn = Conexion()
    monkeypatch.setattr(service, "_access_read_connection", lambda: conn)
    service.leer_fuentes(date(2026, 1, 1), date(2026, 7, 31))
    assert conn.llamadas[0][1] == [date(2026, 8, 1), date(2026, 1, 1)]
    assert "[NOTA]" in conn.llamadas[0][0]
    assert "[ADJUNTO]" in conn.llamadas[0][0]
    assert all(sql.startswith("SELECT") for sql, _ in conn.llamadas)
    assert conn.cerrada


def test_periodo_invalido_no_abre_access(monkeypatch):
    monkeypatch.setattr(
        service, "leer_fuentes", lambda *args: pytest.fail("No debe leer")
    )
    with pytest.raises(ValueError):
        service.ranking_periodo(date(2026, 8, 1), date(2026, 7, 31))


def cliente(permisos):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "roles": [],
        "permissions": permisos,
    }
    return TestClient(app)


def test_permiso_ranking_puede_ver_historia_sin_permiso_general(monkeypatch):
    monkeypatch.setattr(
        service, "leer_fuentes", lambda *args: ([control()], [maestro()])
    )
    client = cliente({"ui_evaluaciones_ranking": (True, False)})
    r = client.get(
        "/api/evaluaciones/powerbi/ranking?desde=2026-01-01&hasta=2026-07-31"
    )
    assert r.status_code == 200
    assert r.json()["proveedores"][0]["total"] == "90.00"
    assert r.json()["resumen"]["con_certificado"] == 0
    assert Decimal(r.json()["resumen"]["puntaje_general"]) == Decimal("90")
    assert r.json()["resumen"]["resultado_general"] == "APROBADO"
    assert r.json()["metodologia"] == service.METODOLOGIA
    h = client.get("/api/evaluaciones/powerbi/proveedor/12/historial?hasta=2026-07-31")
    assert h.status_code == 200


def test_sin_permiso_no_consulta_datos(monkeypatch):
    monkeypatch.setattr(
        service, "leer_fuentes", lambda *args: pytest.fail("No debe leer")
    )
    r = cliente({}).get(
        "/api/evaluaciones/powerbi/ranking?desde=2026-01-01&hasta=2026-07-31"
    )
    assert r.status_code == 403


def test_access_caido_responde_503_sin_exponer_rutas(monkeypatch):
    def fallo(*args):
        raise FileNotFoundError("ruta privada")

    monkeypatch.setattr(service, "leer_fuentes", fallo)
    r = cliente({"ui_evaluaciones_ranking": (True, False)}).get(
        "/api/evaluaciones/powerbi/ranking?desde=2026-01-01&hasta=2026-07-31"
    )
    assert r.status_code == 503
    assert "privada" not in r.text
