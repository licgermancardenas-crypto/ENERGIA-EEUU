"""Exporta la capa geoespacial (Gold geo) a JSON compactos para la web: web/public/data/geo/.

La geometría ya viene simplificada desde Gold (mapa_*.geojson). Las tablas se reducen a lo
que dibujan las páginas Red y Análisis. Si no existe Gold geo (por ejemplo, en la Action
diaria), no se toca nada: los archivos ya publicados quedan como están.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def _num(v: Any, dec: int = 2) -> float | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), dec)


def _registros(df: pd.DataFrame, dec: int = 4) -> list[dict[str, Any]]:
    out = []
    for fila in df.to_dict(orient="records"):
        out.append({k: (_num(v, dec) if isinstance(v, float) else
                        (bool(v) if isinstance(v, bool) else v)) for k, v in fila.items()})
    return out


def exportar_geo(gold_geo: Path, destino: Path) -> dict[str, int] | None:
    if not (gold_geo / "geo_dim_estado.parquet").exists():
        log.info("No hay Gold geo en %s: se conservan los JSON geo publicados", gold_geo)
        return None
    leer = lambda n: pd.read_parquet(gold_geo / f"{n}.parquet")  # noqa: E731
    dest = destino / "geo"
    dest.mkdir(parents=True, exist_ok=True)

    est = leer("geo_dim_estado").merge(leer("geo_estado_metricas"), on="estado_key", how="left")
    cal_path = gold_geo / "geo_estado_calefaccion.parquet"
    if cal_path.exists():
        est = est.merge(leer("geo_estado_calefaccion"), on="estado_key", how="left")
    flujos = leer("geo_flujos_estado")
    if len(flujos):
        ult = flujos[flujos["anio"] == flujos["anio"].max()][["estado_key", "neto_mmcf", "anio"]]
        est = est.merge(ult, on="estado_key", how="left")
    estados = []
    for r in est.to_dict(orient="records"):
        estados.append({
            "k": r["estado_key"], "fips": r["fips"], "nombre": r["nombre"],
            "region": r["region_key"] if isinstance(r.get("region_key"), str) else None,
            "area_km2": _num(r["area_km2"], 0),
            "km": _num(r.get("km_total"), 0), "km_inter": _num(r.get("km_interestatal"), 0),
            "km_intra": _num(r.get("km_intraestatal"), 0),
            "densidad": _num(r.get("densidad_km_1000km2"), 1),
            "operadores": int(r["operadores_n"]) if pd.notna(r.get("operadores_n")) else None,
            "km_hh": _num(r.get("km_red_henry_hub"), 0),
            "hh": bool(r.get("conectado_henry_hub")),
            "hogares": _num(r.get("hogares"), 0), "pct_gas_red": _num(r.get("pct_gas_red"), 4),
            "pct_propano": _num(r.get("pct_propano"), 4),
            "condados_alerta": int(r["condados_alta_dependencia_lejos"])
            if pd.notna(r.get("condados_alta_dependencia_lejos")) else None,
            "balance": _num(r.get("neto_mmcf"), 0),
            "anio_balance": int(r["anio"]) if pd.notna(r.get("anio")) else None})

    condados = {}
    cpath = gold_geo / "geo_condado_calefaccion.parquet"
    if cpath.exists():
        c = leer("geo_condado_calefaccion").merge(leer("geo_dim_condado"), on="condado_key")
        for r in c.to_dict(orient="records"):
            condados[r["condado_key"]] = [r["nombre"], _num(r["pct_gas_red"], 3),
                                          _num(r["pct_gas_red_moe"], 3),
                                          _num(r["distancia_red_km"], 1),
                                          int(bool(r["alta_dependencia_lejos"]))]

    archivos = {
        "estados": estados,
        "condados": condados,
        "puntos": {"hubs": _registros(leer("geo_hubs")), "gnl": _registros(leer("geo_gnl")),
                   "reserva": _registros(leer("geo_reserva_estrategica")),
                   "centrales": _registros(leer("geo_centrales"))},
        "henry_hub": _registros(leer("geo_henry_hub_conexiones")),
        "frescura_geo": _registros(leer("frescura_geo").drop(columns=["calculado_al"])),
        "validacion": json.loads((gold_geo / "validacion.json").read_text(encoding="utf-8")),
    }
    conteo: dict[str, int] = {}
    for nombre, obj in archivos.items():
        texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        (dest / f"{nombre}.json").write_text(texto + "\n", encoding="utf-8")
        conteo[f"{nombre}.json"] = len(texto)
    for capa in ("estados", "red", "condados", "regiones"):
        src = gold_geo / f"mapa_{capa}.geojson"
        if src.exists():
            shutil.copy(src, dest / f"mapa_{capa}.geojson")
            conteo[f"mapa_{capa}.geojson"] = src.stat().st_size
    log.info("JSON geo exportados a %s", dest)
    return conteo
