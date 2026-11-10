from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import plan_produccion_service as service


def material(unidad=1, codigo="KG", requerido=10, stock=4, faltante=6, **extra):
    return {
        "producto_id": 10,
        "codigo": "MP-FICTICIA",
        "unidad_medida_id": unidad,
        "um_codigo": codigo,
        "cantidad_requerida": requerido,
        "stock_disponible": stock,
        "faltante": faltante,
        **extra,
    }


@pytest.mark.parametrize("faltante", [0, 6, 20])
def test_recalculo_conserva_aprobada_sin_escrituras(faltante):
    db = Mock()
    db.execute.return_value.first.return_value = SimpleNamespace(
        id=1, estado="APROBADA"
    )
    alertas = []
    result = service._persistir_sugerencias_compra(
        db,
        2,
        2026,
        [material(faltante=faltante)],
        alertas,
    )
    assert result == {"upserts": 0, "eliminados": 0}
    assert db.execute.call_count == 1
    assert "FOR UPDATE" in str(db.execute.call_args.args[0])
    assert "sin cambios" in alertas[0]
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "estado, faltante, operacion, esperados",
    [
        ("PENDIENTE", 6, "UPDATE", {"upserts": 1, "eliminados": 0}),
        ("DESCARTADA", 6, "UPDATE", {"upserts": 1, "eliminados": 0}),
        ("PENDIENTE", 0, "DELETE", {"upserts": 0, "eliminados": 1}),
        (None, 6, "INSERT", {"upserts": 1, "eliminados": 0}),
    ],
)
def test_persistencia_de_no_aprobadas(estado, faltante, operacion, esperados):
    db = Mock()
    db.execute.return_value.first.return_value = (
        SimpleNamespace(id=1, estado=estado) if estado else None
    )
    result = service._persistir_sugerencias_compra(
        db, 2, 2026, [material(faltante=faltante)], []
    )
    assert result == esperados
    assert str(db.execute.call_args.args[0]).strip().startswith(operacion)


def test_unidades_distintas_no_generan_total_global():
    result = service._resumir_materiales_por_unidad(
        [
            material(),
            material(unidad=2, codigo="UN", requerido=100, stock=0, faltante=100),
        ]
    )
    assert result["unidades_mixtas"] is True
    assert result["total_faltante"] is None
    assert result["cobertura_global_pct"] is None
    assert [(g["um_codigo"], g["total_faltante"]) for g in result["por_unidad"]] == [
        ("KG", 6),
        ("UN", 100),
    ]


def test_excedente_no_cubre_otro_material_y_laf_no_supera_requerido():
    result = service._resumir_materiales_por_unidad(
        [
            material(stock=100, faltante=0),
            material(producto_id=11, stock=0, faltante=10),
        ]
    )
    assert result["total_requerido"] == 20
    assert result["total_faltante"] == 10
    assert result["cobertura_global_pct"] == 50
    laf = service._resumir_materiales_por_unidad(
        [
            material(stock=0, faltante=0, faltante_bruto=10, solicitado_previo_laf=100),
        ]
    )
    assert laf["total_faltante_bruto"] == 10
    assert laf["cobertura_global_pct"] == 100


def test_sin_materiales():
    result = service._resumir_materiales_por_unidad([])
    assert result["por_unidad"] == []
    assert result["unidades_mixtas"] is False
    assert result["total_faltante"] == 0
    assert result["cobertura_global_pct"] == 100


def test_wizard_usa_resumen_por_unidad_despues_de_laf(monkeypatch):
    db = Mock()
    monkeypatch.setattr(
        service,
        "_obtener_planes_pt_periodo",
        lambda *args: [
            {
                "producto_id": 1,
                "codigo": "PT-FICTICIO",
                "nombre": "Prueba",
                "cantidad_planificada": 10,
            },
        ],
    )
    monkeypatch.setattr(
        service,
        "_calcular_faltantes_priorizados_para_planes",
        lambda *args: {
            "faltantes_items": [
                material(stock_asignado=4),
                material(unidad=2, codigo="UN", stock_asignado=4),
            ],
            "total_requerido": 20,
            "total_stock_considerado": 8,
            "total_faltante": 12,
            "faltantes_sin_stock": 0,
            "detalle_prioridades": [],
            "stock_map": {},
        },
    )
    monkeypatch.setattr(
        service, "_obtener_solicitado_laf_por_producto_periodo", lambda *args: {10: 2}
    )
    monkeypatch.setattr(
        service, "_calcular_capacidad_por_stock_para_planes", lambda *args: []
    )
    result = service.calcular_asistente_oc(db, 2, 2026, ajustes_pt=[{"producto_id": 1}])
    assert result["resumen"]["total_faltante"] is None
    assert [g["total_faltante"] for g in result["resumen"]["por_unidad"]] == [4, 4]
    assert [g["cobertura_global_pct"] for g in result["resumen"]["por_unidad"]] == [
        60,
        60,
    ]
    assert result["sugerencias"]["persistir"] is False
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_wizard_sin_plan_entrega_resumen_vacio(monkeypatch):
    monkeypatch.setattr(service, "_obtener_planes_pt_periodo", lambda *args: [])
    result = service.calcular_asistente_oc(
        Mock(), 2, 2026, ajustes_pt=[{"producto_id": 1}]
    )
    assert result["resumen"]["por_unidad"] == []
    assert result["resumen"]["total_faltante"] == 0


def test_analisis_mensual_separa_unidades_sin_persistir(monkeypatch):
    db = Mock()
    monkeypatch.setattr(
        service,
        "_calcular_faltantes_priorizados",
        lambda *args: {
            "faltantes_items": [material(), material(unidad=2, codigo="UN")],
            "faltantes_sin_stock": 0,
            "detalle_prioridades": [],
            "stock_map": {},
        },
    )
    monkeypatch.setattr(service, "_calcular_capacidad_por_stock", lambda *args: [])
    result = service.calcular_faltantes_y_capacidad(
        db, 2, 2026, persistir_sugerencias=False
    )
    assert result["resumen"]["total_requerido"] is None
    assert len(result["resumen"]["por_unidad"]) == 2
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_api_wizard_serializa_unidades_mixtas_sin_base_productiva(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import plan_produccion as api

    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    route = next(
        r for r in api.router.routes if r.path.endswith("/asistente-oc/calcular")
    )
    db = Mock()
    app.dependency_overrides[api.get_db] = lambda: db
    permiso = next(
        d.call for d in route.dependant.dependencies if d.name == "_current_user"
    )
    app.dependency_overrides[permiso] = lambda: {"permissions": {"ui_plan_asistente_oc": (True, False)}}
    monkeypatch.setattr(
        api,
        "calcular_asistente_oc",
        lambda *args, **kwargs: {
            "resumen": service._resumir_materiales_por_unidad(
                [material(), material(unidad=2, codigo="UN")]
            ),
        },
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/plan-produccion-mensual/asistente-oc/calcular?mes=2&anio=2026",
            json={},
        )
        forbidden = client.post(
            "/api/plan-produccion-mensual/asistente-oc/calcular?mes=2&anio=2026&persistir_sugerencias=true",
            json={},
        )
    assert response.status_code == 200
    assert response.json()["resumen"]["total_faltante"] is None
    assert len(response.json()["resumen"]["por_unidad"]) == 2
    assert forbidden.status_code == 403
    db.execute.assert_not_called()
