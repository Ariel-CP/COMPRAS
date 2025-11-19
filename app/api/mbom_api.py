from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query

from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.mbom import MBOMCabecera, MBOMEstructura
from ..services import mbom_service
from ..services.mbom_costos import calcular_costos
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


class MBOMGuardarPayload(MBOMEstructura):
    pass


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


@router.post("/mbom/{producto_padre_id}/importar-flexxus")
def api_importar_flexxus(
    producto_padre_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Stub temporal; se implementará en mbom_import_flexxus.py
    # Devolver "501 Not Implemented" por ahora
    raise HTTPException(
        status_code=501, detail="Importación Flexxus pendiente"
    )


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
