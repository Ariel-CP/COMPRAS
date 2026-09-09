"""Servicios para sincronizar tipos de cambio con fuentes oficiales."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Optional

from app.core.config import get_settings
from app.schemas.tipo_cambio import TipoCambioCreate
from app.services.fx_provider import BcraFxProvider, FxProviderError, FxRate
from app.services.tipo_cambio_service import SQLConn, upsert_tipo_cambio
from sqlalchemy import text

_SETTINGS = get_settings()
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncResumen:
    insertados: int
    actualizados: int
    procesados: int
    desde: date
    hasta: date


@dataclass(slots=True)
class SyncResumenHistorico:
    """Resumen detallado de sincronización histórica."""
    fecha_desde: date
    fecha_hasta: date
    recibidos: int
    insertados: int
    actualizados: int
    sin_cambios: int
    errores: int


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

    created_provider = False
    if not provider:
        provider = BcraFxProvider(
            base_url=_SETTINGS.bcra_api_base_url,
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
        origen=tasa.origen,
        notas=tasa.notas,
    )
    creado, _ = upsert_tipo_cambio(db, payload)  # type: ignore[arg-type]
    return creado


def _iterar_periodos_mensuales(desde: date, hasta: date) -> Iterator[tuple[date, date]]:
    """Itera sobre períodos mensuales completos dentro del rango.

    Yield: tupla (fecha_inicio_mes, fecha_fin_mes)
    """
    current = desde.replace(day=1)  # Primer día del mes
    while current <= hasta:
        # Calcular el último día del mes actual
        if current.month == 12:
            fin_mes = (
                current.replace(year=current.year + 1, month=1, day=1)
                - timedelta(days=1)
            )
        else:
            fin_mes = current.replace(month=current.month + 1, day=1) - timedelta(
                days=1
            )

        # Limitar al rango solicitado
        fin_periodo = min(fin_mes, hasta)

        yield current, fin_periodo

        # Pasar al mes siguiente
        if fin_mes.month == 12:
            current = fin_mes.replace(year=fin_mes.year + 1, month=1, day=1)
        else:
            current = fin_mes.replace(month=fin_mes.month + 1, day=1)


def sync_bcra_historico(
    db: SQLConn,
    *,
    desde: date,
    hasta: date,
    provider: Optional[BcraFxProvider] = None,
) -> SyncResumenHistorico:
    """Sincroniza histórico completo de cotizaciones USD de BCRA por períodos mensuales.

    Utiliza la API pública oficial del BCRA (https://api.bcra.gob.ar)
    que publica diariamente las cotizaciones del dólar minorista (USD).
    No requiere autenticación.

    Nota importante: El dólar mayorista (USD_MAY) NO está disponible en la API
    pública del BCRA. Para sincronizar ambas tasas, considera alternativas como:
    - Banco Nación (BNA) API pública
    - Import manual vía CSV
    - Sistema ERP (Flexxus) si está disponible

    Args:
        db: sesión SQLAlchemy.
        desde: fecha inicial del histórico (incluida).
        hasta: fecha final del histórico (incluida).
        provider: instancia BcraFxProvider reutilizada (opcional).

    Returns:
        SyncResumenHistorico con detalles de la sincronización.

    Raises:
        TipoCambioSyncError: si hay error irrecuperable en la sincronización.
    """
    if desde > hasta:
        raise TipoCambioSyncError("La fecha 'desde' no puede superar 'hasta'")

    created_provider = False
    if not provider:
        provider = BcraFxProvider(
            base_url=_SETTINGS.bcra_api_base_url,
        )
        created_provider = True

    try:
        recibidos_total = 0
        insertados_total = 0
        actualizados_total = 0
        errores_total = 0

        logger.info(
            f"Sincronizando BCRA histórico USD: "
            f"{desde.isoformat()} a {hasta.isoformat()}"
        )

        for periodo_desde, periodo_hasta in _iterar_periodos_mensuales(desde, hasta):
            try:
                logger.info(
                    f"  Período: {periodo_desde.isoformat()} a {periodo_hasta.isoformat()}"
                )

                try:
                    tasas = provider.fetch_range(periodo_desde, periodo_hasta)
                except FxProviderError as exc:
                    logger.warning(
                        f"Error al consultar BCRA período {periodo_desde} a {periodo_hasta}: {exc}"
                    )
                    errores_total += 1
                    continue

                if not tasas:
                    logger.debug("  No hay datos en este período")
                    continue

                for tasa in tasas:
                    recibidos_total += 1
                    try:
                        insertado = _persistir_tasa(db, tasa)
                        if insertado:
                            insertados_total += 1
                        else:
                            actualizados_total += 1
                    except Exception as exc:
                        logger.warning(
                            f"Error al guardar tasa {tasa.fecha} {tasa.tipo}: {exc}"
                        )
                        errores_total += 1

                logger.info(
                    f"  Período {periodo_desde.isoformat()} a "
                    f"{periodo_hasta.isoformat()}: {len(tasas)} cotizaciones"
                )
            except Exception as exc:
                logger.warning(
                    f"Error inesperado en período {periodo_desde}: {exc}"
                )
                errores_total += 1

        sin_cambios = recibidos_total - insertados_total - actualizados_total - errores_total

        logger.info(
            f"BCRA histórico USD completo: "
            f"Recibidos {recibidos_total}, "
            f"Insertados {insertados_total}, "
            f"Actualizados {actualizados_total}, "
            f"Sin cambios {sin_cambios}, "
            f"Errores {errores_total}"
        )

        return SyncResumenHistorico(
            fecha_desde=desde,
            fecha_hasta=hasta,
            recibidos=recibidos_total,
            insertados=insertados_total,
            actualizados=actualizados_total,
            sin_cambios=sin_cambios,
            errores=errores_total,
        )
    finally:
        if created_provider and provider:
            provider.close()


def obtener_ultima_fecha_bcra(db: SQLConn) -> Optional[date]:
    """Obtiene la última fecha de cotización BCRA USD (origen='OTRO') guardada.

    Returns:
        date: La fecha más reciente, o None si no existe histórico.
    """
    query = text("""
        SELECT MAX(fecha) as max_fecha
        FROM tipo_cambio_hist
        WHERE moneda = 'USD' AND origen = 'OTRO' AND tipo = 'VENTA'
    """)
    result = db.execute(query).fetchone()
    if result and result.max_fecha:
        return result.max_fecha
    return None


def sync_bcra_desde_ultima_fecha(
    db: SQLConn,
    provider: Optional[BcraFxProvider] = None,
) -> SyncResumenHistorico:
    """Sincroniza USD del BCRA desde la última fecha guardada hasta hoy.

    Utiliza la API pública oficial del BCRA (https://api.bcra.gob.ar).
    No requiere autenticación.

    Si no hay histórico previo, utiliza bcra_historico_desde de la configuración.
    Esto permite cargar datos históricos en la primera sincronización.

    Nota: Solo sincroniza dólar minorista (USD). El mayorista (USD_MAY) no está
    disponible en la API pública BCRA.

    Args:
        db: sesión SQLAlchemy.
        provider: instancia BcraFxProvider reutilizada (opcional).

    Returns:
        SyncResumenHistorico con detalles de la sincronización.

    Raises:
        TipoCambioSyncError: si hay error en la sincronización o no existe fecha inicial.
    """
    ultima_fecha = obtener_ultima_fecha_bcra(db)

    if ultima_fecha is None:
        # Usar fecha inicial desde configuración
        historico_desde_str = getattr(_SETTINGS, "bcra_historico_desde", None)
        if historico_desde_str:
            try:
                desde = date.fromisoformat(historico_desde_str)
            except (ValueError, TypeError) as exc:
                raise TipoCambioSyncError(
                    f"Configuración bcra_historico_desde inválida: {historico_desde_str}"
                ) from exc
        else:
            raise TipoCambioSyncError(
                "No hay histórico BCRA guardado y no se configuró bcra_historico_desde"
            )
        logger.info(f"Primera sincronización BCRA USD desde {desde.isoformat()}")
    else:
        # Comenzar el día siguiente a la última fecha
        desde = ultima_fecha + timedelta(days=1)
        logger.info(f"Sincronización incremental BCRA USD desde {desde.isoformat()}")

    hasta = date.today()

    if desde > hasta:
        logger.info(
            f"Ya hay datos hasta {ultima_fecha.isoformat()}, nada que sincronizar"
        )
        return SyncResumenHistorico(
            fecha_desde=desde,
            fecha_hasta=hasta,
            recibidos=0,
            insertados=0,
            actualizados=0,
            sin_cambios=0,
            errores=0,
        )

    return sync_bcra_historico(db, desde=desde, hasta=hasta, provider=provider)

