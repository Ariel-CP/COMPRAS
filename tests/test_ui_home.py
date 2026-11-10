from html.parser import HTMLParser
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.api.deps_auth import UI_PERMISSION_ROUTES


def _navigation_forms(current_user):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = set()

        def handle_starttag(self, tag, attrs):
            url = dict(attrs).get("href", "").split("#", 1)[0]
            if tag == "a" and url in UI_PERMISSION_ROUTES:
                self.urls.add(url)

    env = Environment(
        loader=FileSystemLoader("app/templates"), autoescape=select_autoescape(["html"])
    )
    html = env.get_template("home/index.html").render(
        current_user=current_user,
        request=SimpleNamespace(state=SimpleNamespace(current_user=current_user)),
        app_version="prueba",
    )
    links = Links()
    links.feed(html)
    return [{"url": url} for url in sorted(links.urls)]


def test_inicio_muestra_solo_formularios_habilitados():
    current_user = {
        "permissions": {
            "ui_recepcion": (True, True),
            "ui_plan": (False, False),
        }
    }

    forms = _navigation_forms(current_user)

    assert {form["url"] for form in forms} == {
        "/ui/recepcion",
    }


def test_tipo_cambio_solo_aparece_con_permiso_dedicado():
    forms = _navigation_forms({"permissions": {"ui_recepcion": (True, True)}})
    assert "/ui/tipo-cambio" not in {form["url"] for form in forms}

    forms_with_permission = _navigation_forms(
        {"permissions": {"ui_tipo_cambio": (True, False)}}
    )
    assert "/ui/tipo-cambio" in {form["url"] for form in forms_with_permission}


def test_inicio_permite_elegir_cualquiera_de_sus_modulos():
    current_user = {
        "permissions": {
            "ui_recepcion": (True, True),
            "ui_plan": (True, False),
        }
    }

    forms = _navigation_forms(current_user)
    assert "/ui/plan" in {form["url"] for form in forms}
    assert "/ui/recepcion" in {form["url"] for form in forms}


def test_evaluaciones_tiene_permiso_independiente_de_proveedores():
    providers_only = _navigation_forms(
        {"permissions": {"ui_proveedores": (True, True)}}
    )
    assert "/ui/evaluaciones" not in {form["url"] for form in providers_only}

    evaluations_only = _navigation_forms(
        {"permissions": {"ui_evaluaciones": (True, False)}}
    )
    assert "/ui/evaluaciones" in {form["url"] for form in evaluations_only}
    assert "/ui/proveedores" not in {form["url"] for form in evaluations_only}


def test_inicio_muestra_formulario_admin_sin_modulos_operativos():
    current_user = {"permissions": {"ui_admin_usuarios": (True, True)}}

    forms = _navigation_forms(current_user)
    assert {form["url"] for form in forms} == {"/ui/admin/usuarios"}


def test_rol_admin_tiene_acceso_total_a_formularios():
    forms = _navigation_forms({"roles": ["admin"], "permissions": {}})
    assert "/ui/evaluaciones" in {form["url"] for form in forms}
    assert "/ui/admin/permisos" in {form["url"] for form in forms}


def test_inicio_no_muestra_modulos_protegidos_si_no_hay_permisos():
    forms = _navigation_forms({"permissions": {}})
    assert forms == []
