"""Servicios para sincronizar tipos de cambio con fuentes oficiales."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.core.config import get_settings
from app.schemas.tipo_cambio import TipoCambioCreate
from app.services.fx_provider import BcraFxProvider, FxProviderError, FxRate
from app.services.tipo_cambio_service import SQLConn, upsert_tipo_cambio

_SETTINGS = get_settings()


@dataclass(slots=True)
class SyncResumen:
    insertados: int
    actualizados: int
    procesados: int
    desde: date
    hasta: date


class TipoCambioSyncError(RuntimeError):
    """Errores de sincronización de tipos de cambio."""


def _default_rango() -> tuple[date, date]:
    hasta = date.today()
    dias = max(1, _SETTINGS.bcra_sync_days)
    desde = hasta - timedelta(days=dias)
    return desde, hasta


def sync_bcra_tipos_cambio(
    db: SQLConn,
    *,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    provider: Optional[BcraFxProvider] = None,
) -> SyncResumen:
    """Descarga tasas oficiales del BCRA y las inserta/actualiza.

    Args:
        db: sesión SQLAlchemy.
        desde: fecha inicial (incluida). Si no se indica se usa ventana
            configurable ``bcra_sync_days``.
        hasta: fecha final (incluida). Por defecto hoy.
        provider: instancia reutilizada para pruebas.
    """

    if hasta is None or desde is None:
        default_desde, default_hasta = _default_rango()
        desde = desde or default_desde
        hasta = hasta or default_hasta
    if desde > hasta:
        raise TipoCambioSyncError("La fecha 'desde' no puede superar 'hasta'")
    rango_desde = desde
    rango_hasta = hasta

    token = _SETTINGS.bcra_api_token
    created_provider = False
    if not provider:
        if not token:
            raise TipoCambioSyncError(
                "Configura BCRA_API_TOKEN para sincronizar tipos de cambio"
            )
        provider = BcraFxProvider(
            base_url=_SETTINGS.bcra_api_base_url,
            token=token,
        )
        created_provider = True

    try:
        tasas = provider.fetch_range(desde, hasta)
    except FxProviderError as exc:
        raise TipoCambioSyncError(str(exc)) from exc
    finally:
        if created_provider and provider:
            provider.close()

    insertados = 0
    actualizados = 0
    for tasa in tasas:
        insertado = _persistir_tasa(db, tasa)
        if insertado:
            insertados += 1
        else:
            actualizados += 1
    return SyncResumen(
        insertados=insertados,
        actualizados=actualizados,
        procesados=len(tasas),
        desde=rango_desde,
        hasta=rango_hasta,
    )


def _persistir_tasa(db: SQLConn, tasa: FxRate) -> bool:
    payload = TipoCambioCreate(
        fecha=tasa.fecha,
        moneda=tasa.moneda,
        tipo=tasa.tipo,
        tasa=tasa.tasa,
        origen="OTRO",
        notas=tasa.notas,
    )
    creado, _ = upsert_tipo_cambio(db, payload)  # type: ignore[arg-type]
    return creado
