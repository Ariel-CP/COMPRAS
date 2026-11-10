from app.api.deps_auth import (
    resolve_api_permissions,
    resolve_ui_permission,
    user_has_permission,
)
from app.main import app


def test_ui_route_resolves_to_independent_screen_permission():
    assert resolve_ui_permission("/ui/evaluaciones/ranking", "GET") == (
        "ui_evaluaciones_ranking",
        False,
    )
    assert resolve_ui_permission("/ui/evaluaciones", "GET") == (
        "ui_evaluaciones",
        False,
    )


def test_rubro_mutations_are_scoped_to_their_screen():
    assert resolve_ui_permission("/ui/rubros/editar/18", "POST") == (
        "ui_rubros_editar",
        True,
    )
    assert resolve_ui_permission("/ui/rubros/eliminar/18", "GET") == (
        "ui_rubros_eliminar",
        False,
    )
    assert resolve_ui_permission("/ui/rubros/eliminar/18", "POST") == (
        "ui_rubros_eliminar",
        True,
    )


def test_api_roles_permission_changes_are_not_role_management():
    assert resolve_api_permissions("/api/roles/", "GET") == (
        ("ui_admin_roles", "ui_admin_permisos"),
        False,
    )
    assert resolve_api_permissions("/api/roles/4/perms", "PUT") == (
        ("ui_admin_permisos",),
        True,
    )


def test_shared_ranking_read_allows_print_screen_and_write_query_requires_edit():
    assert resolve_api_permissions(
        "/api/evaluaciones/ranking-periodo",
        "GET",
    ) == (
        ("ui_evaluaciones_ranking", "ui_evaluaciones_ranking_print"),
        False,
    )
    assert resolve_api_permissions(
        "/api/evaluaciones/ranking-operativo",
        "GET",
    ) == (("ui_evaluaciones_ranking",), False)
    assert resolve_api_permissions(
        "/api/plan-produccion-mensual/requerimientos-valuados",
        "GET",
        {"persistir": "true"},
    ) == (("ui_plan_requerimientos",), True)
    assert resolve_api_permissions(
        "/api/plan-produccion-mensual/faltantes-capacidad",
        "GET",
    ) == (("ui_plan_mensual", "ui_plan_requerimientos"), False)
    assert resolve_api_permissions("/api/roles/4", "DELETE") == (
        ("ui_admin_roles",),
        True,
    )


def test_quality_screen_can_load_and_save_inspection_independently():
    assert resolve_api_permissions(
        "/api/recepcion/operativas/lineas-pendientes",
        "GET",
    ) == (("ui_recepcion_calidad",), False)
    assert resolve_api_permissions(
        "/api/recepcion/operativas/42",
        "GET",
    ) == (
        ("ui_recepcion", "ui_recepcion_calidad", "ui_recepcion_controles"),
        False,
    )
    assert resolve_api_permissions(
        "/api/recepcion/operativas/lineas/91/intentos-inspeccion",
        "POST",
    ) == (("ui_recepcion_calidad",), True)


def test_write_grant_implies_read_and_admin_bypasses_checks():
    assert user_has_permission(
        {"permissions": {"ui_evaluaciones": (False, True)}},
        "ui_evaluaciones",
    )
    assert user_has_permission(
        {"roles": ["admin"], "permissions": {}},
        "ui_admin_permisos",
        requires_write=True,
    )


def test_every_non_public_api_route_has_a_permission_policy():
    unprotected = []
    for route in app.routes:
        path = getattr(route, "path_format", getattr(route, "path", ""))
        if not path.startswith("/api/"):
            continue
        if path.startswith(("/api/auth/", "/api/health", "/api/tipo-cambio/sync-")):
            continue
        sample_path = path.replace("{filename:path}", "sample.csv")
        sample_path = sample_path.replace("{", "").replace("}", "")
        methods = getattr(route, "methods", None) or {"GET"}
        if any(resolve_api_permissions(sample_path, method) is None for method in methods):
            unprotected.append(path)

    assert unprotected == []
