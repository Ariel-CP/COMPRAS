from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.mbom import MBOMCabecera, MBOMEstructura
from ..services import mbom_service
from ..services.mbom_costos import calcular_costos
from ..services.mbom_import_service import importar_mbom_desde_flexxus
from ..services.mbom_operacion_service import (
    listar_operaciones_mbom,
    agregar_operacion_mbom,
    actualizar_operacion_mbom,
    eliminar_operacion_mbom,
    obtener_siguiente_secuencia,
)
from ..services.ruta_operacion_base_service import (
    listar_rutas_base,
    obtener_ruta_base,
    crear_ruta_base_desde_mbom,
    aplicar_ruta_base_a_mbom,
)
from ..services.producto_service import listar_productos, crear_producto
from ..services.unidad_service import listar_unidades


router = APIRouter()


@router.get("/mbom/cabecera", response_model=Optional[MBOMCabecera])
def api_get_cabecera(
    producto_padre_id: int = Query(..., description="ID de producto padre"),
    preferir: str = Query("ACTIVO", description="ACTIVO|BORRADOR|ARCHIVADO"),
    db: Session = Depends(get_db),
):
    cab = mbom_service.get_cabecera_preferida(db, producto_padre_id, preferir)
    return cab


@router.get("/mbom/{producto_padre_id}", response_model=MBOMEstructura)
def api_get_estructura(
    producto_padre_id: int,
    estado: str = Query("ACTIVO", description="ACTIVO|BORRADOR (preferido)"),
    db: Session = Depends(get_db),
):
    cab = mbom_service.get_cabecera_preferida(db, producto_padre_id, estado)
    if not cab:
        # Si no hay ACTIVO y piden BORRADOR, crear uno si corresponde
        if estado == "BORRADOR":
            cab = mbom_service.obtener_o_crear_borrador(db, producto_padre_id)
        else:
            raise HTTPException(status_code=404, detail="MBOM no encontrada")
    lineas = mbom_service.listar_lineas(db, int(cab["id"]))
    return {"cabecera": cab, "lineas": lineas}


@router.get("/mbom/{producto_padre_id}/arbol-completo")
def api_get_estructura_completa(
    producto_padre_id: int,
    estado: str = Query("BORRADOR", description="ACTIVO|BORRADOR (preferido)"),
    db: Session = Depends(get_db),
):
    """
    Devuelve estructura MBOM completa con todos los niveles anidados.
    Cada línea incluye campo 'nivel' para indentación visual.
    """
    lineas_arbol = mbom_service.obtener_estructura_completa_recursiva(
        db, producto_padre_id, estado
    )
    return {"lineas": lineas_arbol, "total": len(lineas_arbol)}


class MBOMGuardarPayload(MBOMEstructura):
    pass


class UsarRutaBasePayload(BaseModel):
    ruta_id: int = Field(..., gt=0)
    modo: str = Field(
        "append",
        pattern=r"^(append|replace)$",
        description="append: agrega; replace: limpia y copia",
    )
    mantener_secuencia: bool = Field(
        default=False,
        description="Mantiene la secuencia original si no hay conflictos",
    )


class GuardarRutaBasePayload(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=128)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    esta_activo: bool = Field(default=True)
    creado_por: Optional[str] = Field(default=None, max_length=64)


@router.post("/mbom/{producto_padre_id}", response_model=MBOMEstructura)
def api_post_estructura(
    producto_padre_id: int,
    payload: MBOMGuardarPayload,
    db: Session = Depends(get_db),
):
    cab = mbom_service.obtener_o_crear_borrador(db, producto_padre_id)
    mbom_id = int(cab["id"])  # type: ignore[index]
    # Upsert de cada línea recibida
    for ln in payload.lineas:
        mbom_service.upsert_linea(
            db=db,
            mbom_id=mbom_id,
            renglon=ln.renglon,
            componente_producto_id=ln.componente_producto_id,
            cantidad=ln.cantidad,
            unidad_medida_id=ln.unidad_medida_id,
            factor_merma=ln.factor_merma,
            operacion_secuencia=ln.operacion_secuencia,
            grupo_alternativa=ln.grupo_alternativa,
            designador_referencia=ln.designador_referencia,
            notas=ln.notas,
            detalle_id=ln.id,
        )
    lineas = mbom_service.listar_lineas(db, mbom_id)
    return {"cabecera": cab, "lineas": lineas}


@router.put("/mbom/{mbom_id}", response_model=MBOMEstructura)
def api_put_estructura(
    mbom_id: int,
    payload: MBOMGuardarPayload,
    db: Session = Depends(get_db),
):
    cab = mbom_service.get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise HTTPException(status_code=404, detail="MBOM no encontrada")
    # Actualizar cabecera si viene información
    pc = payload.cabecera
    mbom_service.actualizar_cabecera(
        db,
        mbom_id=mbom_id,
        estado=pc.estado,
        revision=pc.revision,
        vigencia_desde=pc.vigencia_desde,
        vigencia_hasta=pc.vigencia_hasta,
        notas=pc.notas,
    )
    # Upsert de líneas
    for ln in payload.lineas:
        mbom_service.upsert_linea(
            db=db,
            mbom_id=mbom_id,
            renglon=ln.renglon,
            componente_producto_id=ln.componente_producto_id,
            cantidad=ln.cantidad,
            unidad_medida_id=ln.unidad_medida_id,
            factor_merma=ln.factor_merma,
            operacion_secuencia=ln.operacion_secuencia,
            grupo_alternativa=ln.grupo_alternativa,
            designador_referencia=ln.designador_referencia,
            notas=ln.notas,
            detalle_id=ln.id,
        )
    lineas = mbom_service.listar_lineas(db, mbom_id)
    cab_actual = mbom_service.get_cabecera_por_id(db, mbom_id)
    return {"cabecera": cab_actual, "lineas": lineas}


@router.delete("/mbom/detalle/{detalle_id}")
def api_delete_detalle(detalle_id: int, db: Session = Depends(get_db)):
    mbom_service.borrar_linea(db, detalle_id)
    return {"ok": True}


@router.get("/mbom/{mbom_id}/costos")
def api_get_costos(mbom_id: int, db: Session = Depends(get_db)):
    cab = mbom_service.get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise HTTPException(status_code=404, detail="MBOM no encontrada")
    return calcular_costos(db, mbom_id)


@router.post(
    "/mbom/{producto_padre_id}/importar-flexxus",
    response_model=MBOMEstructura,
)
def api_importar_flexxus(
    producto_padre_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return importar_mbom_desde_flexxus(db, producto_padre_id, archivo)


@router.post("/mbom/demo/{codigo}", response_model=MBOMEstructura)
def api_crear_demo_mbom(
    codigo: str,
    componentes: Optional[str] = Query(
        None,
        description=(
            "Códigos separados por coma; si falta se usan MP activos"
        ),
    ),
    db: Session = Depends(get_db),
):
    """Crear (si no existe) producto padre PT + MBOM BORRADOR demo."""
    codigo = codigo.strip().upper()
    if not codigo:
        raise HTTPException(status_code=400, detail="Código requerido")

    prod_existentes = listar_productos(
        db, q=codigo, tipo=None, activo=True, limit=5, offset=0
    )
    prod_padre = next(
        (p for p in prod_existentes if p["codigo"].upper() == codigo), None
    )
    if not prod_padre:
        unidades = listar_unidades(db)
        if not unidades:
            raise HTTPException(
                status_code=400,
                detail="No hay unidades de medida para crear producto",
            )
        um_id = unidades[0]["id"]
        try:
            prod_padre = crear_producto(
                db,
                codigo=codigo,
                nombre=f"Producto {codigo}",
                tipo_producto="PT",
                unidad_medida_id=um_id,
                activo=True,
            )
        except ValueError as ex:
            raise HTTPException(status_code=400, detail=str(ex)) from ex

    producto_padre_id = int(prod_padre["id"])
    cab = mbom_service.obtener_o_crear_borrador(db, producto_padre_id)
    mbom_id = int(cab["id"])

    if componentes:
        comp_cods = [
            c.strip().upper() for c in componentes.split(",") if c.strip()
        ]
    else:
        mp_list = listar_productos(
            db, q=None, tipo="MP", activo=True, limit=10, offset=0
        )
        comp_cods = [
            p["codigo"].upper()
            for p in mp_list
            if p["codigo"].upper() != codigo
        ][:3]

    existentes = mbom_service.listar_lineas(db, mbom_id)
    existen_ids = {d["componente_producto_id"] for d in existentes}
    max_renglon = max([d["renglon"] for d in existentes], default=0)
    renglon = (max_renglon // 10) * 10 + 10 if max_renglon else 10

    for cod in comp_cods:
        prod_list = listar_productos(
            db, q=cod, tipo=None, activo=True, limit=5, offset=0
        )
        comp = next(
            (p for p in prod_list if p["codigo"].upper() == cod), None
        )
        if not comp:
            continue
        comp_id = int(comp["id"])
        if comp_id == producto_padre_id or comp_id in existen_ids:
            continue
        try:
            mbom_service.upsert_linea(
                db,
                mbom_id=mbom_id,
                renglon=renglon,
                componente_producto_id=comp_id,
                cantidad=1.0,
                unidad_medida_id=int(comp["unidad_medida_id"]),
                factor_merma=0.0,
            )
            renglon += 10
        except ValueError:
            continue

    lineas_final = mbom_service.listar_lineas(db, mbom_id)
    return {"cabecera": cab, "lineas": lineas_final}


@router.post("/mbom/{mbom_id}/activar", response_model=MBOMEstructura)
def api_activar_revision(mbom_id: int, db: Session = Depends(get_db)):
    """Activar la revisión indicada y devolver estructura completa."""
    cab = mbom_service.get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise HTTPException(status_code=404, detail="MBOM no encontrada")
    try:
        cab_act = mbom_service.activar_revision(db, mbom_id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    lineas = mbom_service.listar_lineas(db, int(cab_act["id"]))
    return {"cabecera": cab_act, "lineas": lineas}


@router.post("/mbom/{mbom_id}/clonar", response_model=MBOMEstructura)
def api_clonar_revision(mbom_id: int, db: Session = Depends(get_db)):
    """Clonar revisión existente a nueva BORRADOR (incrementa revision)."""
    cab = mbom_service.get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise HTTPException(status_code=404, detail="MBOM no encontrada")
    try:
        cab_nueva = mbom_service.clonar_revision_a_borrador(db, mbom_id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    lineas = mbom_service.listar_lineas(db, int(cab_nueva["id"]))
    return {"cabecera": cab_nueva, "lineas": lineas}


@router.delete("/mbom/limpiar-todo")
def api_limpiar_mbom_test(db: Session = Depends(get_db)):
    """
    PELIGRO: Elimina TODAS las estructuras MBOM de la base de datos.
    Solo para desarrollo/testing. NO usar en producción.
    """
    try:
        # Eliminar todas las líneas primero (FK constraint)
        db.execute(text("DELETE FROM mbom_detalle"))
        # Eliminar todos los encabezados
        db.execute(text("DELETE FROM mbom_cabecera"))
        db.commit()
        
        count_det = db.execute(
            text("SELECT COUNT(*) as c FROM mbom_detalle")
        ).scalar()
        count_cab = db.execute(
            text("SELECT COUNT(*) as c FROM mbom_cabecera")
        ).scalar()
        
        return {
            "mensaje": "MBOMs eliminadas",
            "mbom_detalle": count_det,
            "mbom_cabecera": count_cab
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al limpiar: {str(e)}"
        ) from e


@router.post("/productos/corregir-tipos-30")
def api_corregir_tipos_productos_30(db: Session = Depends(get_db)):
    """
    Actualiza todos los productos que empiezan con '30' a tipo WIP.
    Útil para corregir productos creados antes de implementar
    detección automática de tipos.
    """
    try:
        result = db.execute(
            text(
                "UPDATE producto SET tipo_producto = 'WIP' "
                "WHERE codigo LIKE '30%'"
            )
        )
        db.commit()
        
        count = db.execute(
            text(
                "SELECT COUNT(*) as c FROM producto "
                "WHERE codigo LIKE '30%'"
            )
        ).scalar()
        rowcount = result.rowcount  # type: ignore[attr-defined]
        productos_actualizados = int(rowcount or 0)

        return {
            "mensaje": "Tipos actualizados",
            "productos_actualizados": productos_actualizados,
            "total_productos_30": count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar tipos: {str(e)}"
        ) from e


# ============================================================================
# ENDPOINTS DE RUTA DE OPERACIONES (MBOM)
# ============================================================================

@router.get("/operaciones/rutas-base")
def api_listar_rutas_base_endpoint(
    q: Optional[str] = Query(
        None,
        description="Filtrar por nombre o descripción",
    ),
    solo_activas: Optional[bool] = Query(
        None,
        description="true para solo plantillas activas",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return listar_rutas_base(
        db=db,
        q=q,
        solo_activas=solo_activas,
        limit=limit,
        offset=offset,
    )


@router.get("/operaciones/rutas-base/{ruta_id}")
def api_obtener_ruta_base_endpoint(
    ruta_id: int,
    db: Session = Depends(get_db),
):
    ruta = obtener_ruta_base(db, ruta_id)
    if not ruta:
        raise HTTPException(
            status_code=404,
            detail="Ruta de operaciones no encontrada",
        )
    return ruta


@router.post("/mbom/{mbom_id}/operaciones/usar-ruta")
def api_usar_ruta_base(
    mbom_id: int,
    payload: UsarRutaBasePayload,
    db: Session = Depends(get_db),
):
    cab = mbom_service.get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise HTTPException(status_code=404, detail="MBOM no encontrada")

    try:
        operaciones = aplicar_ruta_base_a_mbom(
            db=db,
            ruta_id=payload.ruta_id,
            mbom_id=mbom_id,
            reemplazar=payload.modo == "replace",
            mantener_secuencia=payload.mantener_secuencia,
        )
    except ValueError as ex:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except Exception as ex:  # pragma: no cover - fallback defensivo
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al aplicar ruta predeterminada: {str(ex)}",
        ) from ex

    return {"operaciones": operaciones}


@router.post("/mbom/{mbom_id}/operaciones/guardar-ruta", status_code=201)
def api_guardar_ruta_desde_mbom(
    mbom_id: int,
    payload: GuardarRutaBasePayload,
    db: Session = Depends(get_db),
):
    cab = mbom_service.get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise HTTPException(status_code=404, detail="MBOM no encontrada")

    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre de ruta requerido")
    descripcion = payload.descripcion.strip() if payload.descripcion else None

    try:
        ruta = crear_ruta_base_desde_mbom(
            db=db,
            mbom_id=mbom_id,
            nombre=nombre,
            descripcion=descripcion,
            esta_activo=payload.esta_activo,
            creado_por=payload.creado_por,
        )
    except ValueError as ex:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except Exception as ex:  # pragma: no cover - fallback defensivo
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al generar plantilla: {str(ex)}",
        ) from ex

    return ruta


@router.get("/mbom/{mbom_id}/operaciones")
def api_listar_operaciones_mbom(
    mbom_id: int,
    db: Session = Depends(get_db),
):
    """Lista las operaciones de la ruta de un MBOM."""
    return listar_operaciones_mbom(db, mbom_id)


@router.post("/mbom/{mbom_id}/operaciones", status_code=201)
def api_agregar_operacion_mbom(
    mbom_id: int,
    operacion_id: int = Query(...),
    secuencia: Optional[int] = Query(None),
    notas: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Agrega una operación a la ruta del MBOM."""
    if secuencia is None:
        secuencia = obtener_siguiente_secuencia(db, mbom_id)
    
    try:
        return agregar_operacion_mbom(
            db=db,
            mbom_id=mbom_id,
            operacion_id=operacion_id,
            secuencia=secuencia,
            notas=notas,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al agregar operación: {str(e)}"
        )


@router.put("/mbom/operaciones/{mbom_operacion_id}")
def api_actualizar_operacion_mbom(
    mbom_operacion_id: int,
    secuencia: Optional[int] = Query(None),
    notas: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Actualiza una operación en la ruta del MBOM."""
    try:
        actualizar_operacion_mbom(
            db=db,
            mbom_operacion_id=mbom_operacion_id,
            secuencia=secuencia,
            notas=notas,
        )
        return {"mensaje": "Operación actualizada"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al actualizar: {str(e)}"
        )


@router.delete("/mbom/operaciones/{mbom_operacion_id}", status_code=204)
def api_eliminar_operacion_mbom(
    mbom_operacion_id: int,
    db: Session = Depends(get_db),
):
    """Elimina una operación de la ruta del MBOM."""
    try:
        if not eliminar_operacion_mbom(db, mbom_operacion_id):
            raise HTTPException(
                status_code=404,
                detail="Operación no encontrada"
            )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al eliminar: {str(e)}"
        )
