"""Utilidades de fechas/períodos según la frecuencia de la EIA."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd

FORMATO_API = {"daily": "%Y-%m-%d", "weekly": "%Y-%m-%d", "monthly": "%Y-%m"}


def hoy_utc() -> date:
    return datetime.now(UTC).date()


def nuevo_run_id() -> str:
    """Timestamp UTC con microsegundos: único y ordenable (se usa en nombres de archivo)."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def ahora_utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parsear_periodos(valores: pd.Series, frecuencia: str) -> pd.Series:
    """Convierte la columna 'period' de la EIA a datetime64 (mensual = día 1). Inválidos -> NaT."""
    fmt = FORMATO_API[frecuencia]
    return pd.to_datetime(valores.astype("string"), format=fmt, errors="coerce").astype(
        "datetime64[ns]"
    )


def fin_de_periodo(periodo: date, frecuencia: str) -> date:
    """Fecha en que termina el período: último día del mes en mensuales; el propio día si no.

    En las series semanales de la EIA el período ya es la fecha de cierre/relevamiento.
    """
    if frecuencia == "monthly":
        siguiente = date(periodo.year + (periodo.month == 12), periodo.month % 12 + 1, 1)
        return siguiente - timedelta(days=1)
    return periodo


def formato_api(d: date, frecuencia: str) -> str:
    return d.strftime(FORMATO_API[frecuencia])


def a_fecha_inicio(texto: str) -> date:
    """'2010-01' o '2023-01-01' -> date."""
    partes = [int(p) for p in str(texto).split("-")]
    return date(partes[0], partes[1] if len(partes) > 1 else 1, partes[2] if len(partes) > 2 else 1)
