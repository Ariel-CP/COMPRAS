from app.api.ui_home import get_available_forms


def test_inicio_muestra_solo_formularios_habilitados():
    current_user = {
        "permissions": {
            "recepcion": (True, True),
            "plan": (False, False),
        }
    }

    forms = get_available_forms(current_user)

    assert {form["url"] for form in forms} == {
        "/ui/recepcion",
    }


def test_tipo_cambio_solo_aparece_con_permiso_dedicado():
    forms = get_available_forms(
        {"permissions": {"recepcion": (True, True)}}
    )
    assert "/ui/tipo-cambio" not in {form["url"] for form in forms}

    forms_with_permission = get_available_forms(
        {"permissions": {"tipo_cambio": (True, False)}}
    )
    assert "/ui/tipo-cambio" in {form["url"] for form in forms_with_permission}


def test_inicio_permite_elegir_cualquiera_de_sus_modulos():
    current_user = {
        "permissions": {
            "recepcion": (True, True),
            "plan": (True, False),
        }
    }

    forms = get_available_forms(current_user)
    assert "/ui/plan" in {form["url"] for form in forms}
    assert "/ui/recepcion" in {form["url"] for form in forms}


def test_inicio_muestra_formulario_admin_sin_modulos_operativos():
    current_user = {
        "permissions": {"admin_usuarios": (True, True)}
    }

    forms = get_available_forms(current_user)
    assert {form["url"] for form in forms} == {"/ui/admin/usuarios"}


def test_inicio_no_muestra_modulos_protegidos_si_no_hay_permisos():
    forms = get_available_forms({"permissions": {}})
    assert forms == []
