"""Verificación y documentos de certificado de las recepciones locales."""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

from sqlalchemy import text
from sqlalchemy.orm import Session

MAX_ARCHIVO_BYTES = 10 * 1024 * 1024


def proteger_recepcion_con_certificados(db: Session, recepcion_id: int) -> None:
    lock = " FOR UPDATE" if db.get_bind().dialect.name != "sqlite" else ""
    db.execute(
        text("SELECT id FROM recepcion_cabecera WHERE id = :id" + lock),
        {"id": recepcion_id},
    ).first()
    evidencia = db.execute(
        text(
            "SELECT rl.id FROM recepcion_linea rl WHERE rl.recepcion_cabecera_id = :id "
            "AND (EXISTS (SELECT 1 FROM recepcion_certificado_calidad c "
            "WHERE c.recepcion_linea_id = rl.id AND c.recibido = 1) "
            "OR EXISTS (SELECT 1 FROM recepcion_certificado_documento d "
            "WHERE d.recepcion_linea_id = rl.id)) LIMIT 1"
        ),
        {"id": recepcion_id},
    ).first()
    if evidencia:
        raise ValueError(
            "No se puede editar ni borrar una recepción con certificados registrados"
        )


def _linea_local(db: Session, linea_id: int, *, bloquear: bool = False) -> dict:
    lock = " FOR UPDATE" if bloquear and db.get_bind().dialect.name != "sqlite" else ""
    fila = (
        db.execute(
            text(
                "SELECT rl.id, rl.recepcion_cabecera_id AS recepcion_id, rc.recepcion_staging_id "
                "FROM recepcion_linea rl JOIN recepcion_cabecera rc "
                "ON rc.id = rl.recepcion_cabecera_id WHERE rl.id = :id" + lock
            ),
            {"id": linea_id},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise LookupError("Línea de recepción no encontrada")
    if fila["recepcion_staging_id"] is not None:
        raise ValueError("Las recepciones históricas importadas son de solo lectura")
    return dict(fila)


def validar_documento(nombre: str, contenido: bytes) -> tuple[str, str]:
    if not contenido:
        raise ValueError("El documento está vacío")
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise ValueError("El documento no puede superar 10 MB")
    nombre = re.split(r"[/\\]", nombre)[-1]
    nombre = "".join(c for c in nombre if ord(c) >= 32).strip()
    extension = PurePosixPath(nombre).suffix.lower()
    tipos = {
        ".pdf": ("application/pdf", b"%PDF-"),
        ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
        ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
        ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    }
    if extension not in tipos:
        raise ValueError("Adjuntá un documento PDF, JPG o PNG")
    mime, firma = tipos[extension]
    if not contenido.startswith(firma):
        raise ValueError("El contenido del documento no coincide con su formato")
    nombre = nombre[: 255 - len(extension)] + extension if len(nombre) > 255 else nombre
    return nombre, mime


def obtener_certificado(db: Session, linea_id: int) -> dict:
    linea = _linea_local(db, linea_id)
    estado = (
        db.execute(
            text(
                "SELECT c.recibido, c.fecha_actualizacion, u.nombre AS usuario_nombre "
                "FROM recepcion_certificado_calidad c LEFT JOIN usuario u ON u.id = c.usuario_id "
                "WHERE c.recepcion_linea_id = :id"
            ),
            {"id": linea_id},
        )
        .mappings()
        .first()
    )
    documentos = (
        db.execute(
            text(
                "SELECT d.id, d.nombre, d.tipo_mime, d.tamano, d.sha256, d.fecha_creacion, "
                "u.nombre AS usuario_nombre FROM recepcion_certificado_documento d "
                "LEFT JOIN usuario u ON u.id = d.usuario_id "
                "WHERE d.recepcion_linea_id = :id ORDER BY d.id"
            ),
            {"id": linea_id},
        )
        .mappings()
        .all()
    )
    return {
        "linea_id": linea_id,
        "recepcion_id": linea["recepcion_id"],
        "recibido": bool(estado and estado["recibido"]) or bool(documentos),
        "fecha_actualizacion": estado["fecha_actualizacion"] if estado else None,
        "usuario_nombre": estado["usuario_nombre"] if estado else None,
        "documentos": [dict(f) for f in documentos],
    }


def guardar_certificado(
    db: Session,
    linea_id: int,
    *,
    recibido: bool,
    usuario_id: int,
    nombre: str | None = None,
    contenido: bytes | None = None,
) -> dict:
    documento = (
        validar_documento(nombre or "", contenido) if contenido is not None else None
    )
    _linea_local(db, linea_id, bloquear=True)
    anterior = obtener_certificado(db, linea_id)
    if not recibido and not documento and anterior["documentos"]:
        raise ValueError(
            "El certificado tiene documentos adjuntos y debe figurar recibido"
        )
    recibido = recibido or documento is not None
    if documento:
        nombre_limpio, mime = documento
        digest = hashlib.sha256(contenido).hexdigest()
        existe = db.execute(
            text(
                "SELECT id FROM recepcion_certificado_documento "
                "WHERE recepcion_linea_id = :id AND sha256 = :sha"
            ),
            {"id": linea_id, "sha": digest},
        ).first()
        if not existe:
            db.execute(
                text(
                    "INSERT INTO recepcion_certificado_documento "
                    "(recepcion_linea_id, nombre, tipo_mime, tamano, sha256, contenido, usuario_id) "
                    "VALUES (:id, :nombre, :mime, :tamano, :sha, :contenido, :usuario)"
                ),
                {
                    "id": linea_id,
                    "nombre": nombre_limpio,
                    "mime": mime,
                    "tamano": len(contenido),
                    "sha": digest,
                    "contenido": contenido,
                    "usuario": usuario_id,
                },
            )
    existe_estado = db.execute(
        text(
            "SELECT recepcion_linea_id FROM recepcion_certificado_calidad WHERE recepcion_linea_id = :id"
        ),
        {"id": linea_id},
    ).first()
    params = {"id": linea_id, "recibido": recibido, "usuario": usuario_id}
    if existe_estado:
        db.execute(
            text(
                "UPDATE recepcion_certificado_calidad SET recibido = :recibido, "
                "usuario_id = :usuario, fecha_actualizacion = CURRENT_TIMESTAMP "
                "WHERE recepcion_linea_id = :id"
            ),
            params,
        )
    else:
        db.execute(
            text(
                "INSERT INTO recepcion_certificado_calidad (recepcion_linea_id, recibido, usuario_id) "
                "VALUES (:id, :recibido, :usuario)"
            ),
            params,
        )
    return obtener_certificado(db, linea_id)


def obtener_documento(db: Session, linea_id: int, documento_id: int) -> dict:
    _linea_local(db, linea_id)
    fila = (
        db.execute(
            text(
                "SELECT nombre, tipo_mime, contenido FROM recepcion_certificado_documento "
                "WHERE id = :documento AND recepcion_linea_id = :linea"
            ),
            {"documento": documento_id, "linea": linea_id},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise LookupError("Documento no encontrado para esta línea")
    return dict(fila)
