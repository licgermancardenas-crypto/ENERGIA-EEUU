"""Capa Silver: tipado, validación, MERGE insert-only y auditoría de revisiones.

Reglas:
- Lee TODO Bronze en cada corrida (es idempotente gracias al MERGE insert-only).
- Descarta filas sin fecha, sin valor, sin clave completa, de series no configuradas
  y con valor <= 0 donde no tiene sentido (`solo_positivos`).
- Series diarias: solo acepta datos con al menos N días de antigüedad (días incompletos).
- Clave natural: (dataset, serie, periodo). Si la clave ya existe no se pisa; si llega
  un valor distinto se registra en la auditoría de revisiones (una sola vez por valor).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eia_pulso.config import DatasetConfig, Settings
from eia_pulso.periodos import ahora_utc_iso, hoy_utc, nuevo_run_id, parsear_periodos
from eia_pulso.silver.storage import (
    CLAVE,
    ESQUEMA_SILVER,
    escribir_particiones,
    escribir_revisiones,
    leer_revisiones,
    leer_silver,
)

log = logging.getLogger(__name__)

MAPEO_COLUMNAS = {
    "series": "serie",
    "period": "periodo_raw",
    "value": "valor_raw",
    "units": "unidad",
    "series-description": "descripcion",
    "duoarea": "duoarea",
    "area-name": "area_nombre",
    "product": "producto",
    "product-name": "producto_nombre",
    "process": "proceso",
    "process-name": "proceso_nombre",
}

MOTIVOS = (
    "sin_fecha",
    "sin_valor",
    "clave_incompleta",
    "serie_no_configurada",
    "valor_no_positivo",
    "dia_incompleto",
)


@dataclass
class ResultadoSilver:
    leidas: dict[str, int] = field(default_factory=dict)
    validas: dict[str, int] = field(default_factory=dict)
    insertadas: dict[str, int] = field(default_factory=dict)
    descartes: dict[str, dict[str, int]] = field(default_factory=dict)
    revisiones_nuevas: int = 0
    archivos_bronze: int = 0
    total_silver: dict[str, int] = field(default_factory=dict)


def leer_bronze(bronze_dir: Path, ds: DatasetConfig) -> pd.DataFrame:
    """Concatena todos los JSON Bronze de un dataset, con archivo y timestamp de extracción."""
    marcos = []
    for archivo in sorted((bronze_dir / ds.nombre).glob("*.json")):
        doc = json.loads(archivo.read_text(encoding="utf-8"))
        filas = doc.get("data", [])
        if not filas:
            continue
        df = pd.DataFrame(filas)
        df["archivo_bronze"] = archivo.name
        df["extraido_utc"] = doc.get("metadata", {}).get("extraido_utc", "")
        marcos.append(df)
    if not marcos:
        return pd.DataFrame(columns=[*MAPEO_COLUMNAS, "archivo_bronze", "extraido_utc"])
    return pd.concat(marcos, ignore_index=True)


def validar(
    crudo: pd.DataFrame, ds: DatasetConfig, hoy: date, dias_minimos: int
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Tipa y valida. Devuelve (filas válidas con esquema Silver, conteo de descartes)."""
    df = crudo.rename(columns=MAPEO_COLUMNAS).copy()
    for col in [*MAPEO_COLUMNAS.values(), "archivo_bronze", "extraido_utc"]:
        if col not in df.columns:
            df[col] = None
    descartes = dict.fromkeys(MOTIVOS, 0)

    df["periodo"] = parsear_periodos(df["periodo_raw"], ds.frecuencia)
    df["valor"] = pd.to_numeric(df["valor_raw"], errors="coerce").astype("float64")
    df["serie"] = df["serie"].astype("string").str.strip()

    def filtrar(mascara: pd.Series, motivo: str) -> None:
        nonlocal df
        descartes[motivo] += int(mascara.sum())
        df = df[~mascara]

    filtrar(df["periodo"].isna(), "sin_fecha")
    filtrar(df["valor"].isna() | ~np.isfinite(df["valor"]), "sin_valor")
    filtrar(df["serie"].isna() | (df["serie"] == ""), "clave_incompleta")
    filtrar(~df["serie"].isin(list(ds.series)), "serie_no_configurada")
    if ds.solo_positivos:
        filtrar(df["valor"] <= 0, "valor_no_positivo")
    if ds.frecuencia == "daily":
        limite = pd.Timestamp(hoy - timedelta(days=dias_minimos))
        filtrar(df["periodo"] > limite, "dia_incompleto")

    df["dataset"] = ds.nombre
    df["frecuencia"] = ds.frecuencia
    df["cargado_utc"] = ""
    cols_texto = [c for c in ESQUEMA_SILVER.names if c not in ("periodo", "valor")]
    for c in cols_texto:
        df[c] = df[c].astype("string")
    return df[ESQUEMA_SILVER.names].reset_index(drop=True), descartes


def merge_insert_only(
    nuevos: pd.DataFrame,
    existentes: pd.DataFrame,
    revisiones_existentes: pd.DataFrame,
    detectado_utc: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """MERGE insert-only. Devuelve (filas a insertar, revisiones nuevas a auditar)."""
    if nuevos.empty:
        return nuevos.iloc[0:0], pd.DataFrame(columns=list(revisiones_existentes.columns))

    nuevos = nuevos.sort_values(["extraido_utc", "archivo_bronze"], kind="stable")
    primeros = nuevos.drop_duplicates(CLAVE, keep="first")

    claves_exist = existentes[CLAVE].drop_duplicates()
    m = primeros.merge(claves_exist, on=CLAVE, how="left", indicator=True)
    insertar = m[m["_merge"] == "left_only"].drop(columns="_merge")

    # Valor de referencia = el ya cargado en Silver (o el que se inserta ahora)
    referencia = pd.concat(
        [existentes[[*CLAVE, "valor"]], insertar[[*CLAVE, "valor"]]], ignore_index=True
    ).rename(columns={"valor": "valor_cargado"})
    candidatos = nuevos.drop_duplicates([*CLAVE, "valor"], keep="first").merge(
        referencia, on=CLAVE, how="inner"
    )
    distintos = ~np.isclose(candidatos["valor"], candidatos["valor_cargado"], rtol=1e-9, atol=1e-12)
    rev = candidatos.loc[distintos, [*CLAVE, "valor_cargado", "valor", "archivo_bronze",
                                     "extraido_utc"]].rename(columns={"valor": "valor_nuevo"})
    if not rev.empty and not revisiones_existentes.empty:
        ya = revisiones_existentes[[*CLAVE, "valor_nuevo"]].drop_duplicates()
        rev = rev.merge(ya, on=[*CLAVE, "valor_nuevo"], how="left", indicator=True)
        rev = rev[rev["_merge"] == "left_only"].drop(columns="_merge")
    rev = rev.assign(detectado_utc=detectado_utc).reset_index(drop=True)
    insertar = insertar.assign(cargado_utc=detectado_utc).reset_index(drop=True)
    return insertar, rev


def run_silver(
    settings: Settings,
    hoy: date | None = None,
    run_id: str | None = None,
    datasets: list[str] | None = None,
) -> ResultadoSilver:
    hoy = hoy or hoy_utc()
    run_id = run_id or nuevo_run_id()
    ahora = ahora_utc_iso()
    res = ResultadoSilver()

    existentes_todo = leer_silver(settings.silver_dir)
    revisiones = leer_revisiones(settings.silver_dir)
    revisiones_nuevas = []

    for nombre, ds in settings.datasets.items():
        if datasets and nombre not in datasets:
            continue
        crudo = leer_bronze(settings.bronze_dir, ds)
        res.archivos_bronze += crudo["archivo_bronze"].nunique() if not crudo.empty else 0
        validas, desc = validar(crudo, ds, hoy, settings.dias_minimos_diarios)
        existentes = existentes_todo[existentes_todo["dataset"] == nombre]
        insertar, rev = merge_insert_only(validas, existentes, revisiones, ahora)
        escribir_particiones(insertar, settings.silver_dir, run_id)

        res.leidas[nombre] = len(crudo)
        res.validas[nombre] = len(validas)
        res.insertadas[nombre] = len(insertar)
        res.descartes[nombre] = {k: v for k, v in desc.items() if v}
        res.total_silver[nombre] = len(existentes) + len(insertar)
        if not rev.empty:
            revisiones_nuevas.append(rev)
        log.info(
            "Silver %s: leídas=%d válidas=%d insertadas=%d revisiones=%d descartes=%s",
            nombre, len(crudo), len(validas), len(insertar), len(rev), res.descartes[nombre],
        )

    if revisiones_nuevas:
        todas = pd.concat(revisiones_nuevas, ignore_index=True)
        escribir_revisiones(todas, settings.silver_dir, run_id)
        res.revisiones_nuevas = len(todas)
    return res
