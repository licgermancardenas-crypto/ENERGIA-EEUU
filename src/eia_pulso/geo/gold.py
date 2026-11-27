"""Gold geoespacial: métricas por estado, alcance del Henry Hub, proximidad y geometría liviana.

Todas las longitudes y áreas se calculan en EPSG:5070 (Albers de área equivalente); la
geometría que se exporta para el informe vuelve a WGS84, simplificada y con coordenadas
redondeadas. Ninguna cifra se completa a mano: lo que falta se marca como no disponible.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from pyproj import Geod
from shapely.geometry import mapping
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, unary_union

from eia_pulso.geo.bronze import ultimo
from eia_pulso.geo.config import CONEXIONES_HH, GeoConfig

log = logging.getLogger(__name__)
GEOD = Geod(ellps="WGS84")
TIPOS = ("interestatal", "intraestatal", "recoleccion")


# ------------------------------------------------------------------ intersección y métricas
def km_por_estado(gasoductos: gpd.GeoDataFrame, estados: gpd.GeoDataFrame,
                  crs: int) -> pd.DataFrame:
    """km de cada (estado, tipo, operador): intersección de líneas con polígonos en `crs`."""
    lin = gasoductos.to_crs(crs)
    pol = estados[["estado_key", "geometry"]].to_crs(crs)
    inter = gpd.overlay(lin, pol, how="intersection", keep_geom_type=True)
    inter["km"] = inter.length / 1000
    return (inter.groupby(["estado_key", "tipo", "operador"], as_index=False)["km"].sum())


def metricas_estado(km: pd.DataFrame, estados: gpd.GeoDataFrame,
                    operadores_hh: set[str]) -> pd.DataFrame:
    base = pd.DataFrame(estados.drop(columns="geometry"))
    piv = km.pivot_table(index="estado_key", columns="tipo", values="km", aggfunc="sum")
    for t in TIPOS:
        if t not in piv:
            piv[t] = pd.NA if t == "recoleccion" else 0.0
    piv = piv.rename(columns={t: f"km_{t}" for t in TIPOS})
    ops = km.groupby("estado_key")["operador"].nunique().rename("operadores_n")
    hh = (km[km["operador"].isin(operadores_hh)].groupby("estado_key")["km"].sum()
          .rename("km_red_henry_hub"))
    m = base.merge(piv[[f"km_{t}" for t in TIPOS]], on="estado_key", how="left")
    m = m.merge(ops, on="estado_key", how="left").merge(hh, on="estado_key", how="left")
    for c in ("km_interestatal", "km_intraestatal", "km_red_henry_hub"):
        m[c] = m[c].fillna(0.0)
    m["operadores_n"] = m["operadores_n"].fillna(0).astype(int)
    m["km_total"] = m["km_interestatal"] + m["km_intraestatal"]
    m["densidad_km_1000km2"] = m["km_total"] / m["area_km2"] * 1000
    m["conectado_henry_hub"] = m["km_red_henry_hub"] > 0
    return m


def alcance_henry_hub(km: pd.DataFrame, conexiones: pd.DataFrame) -> pd.DataFrame:
    """Huella de red de cada operador conectado al hub (NO es flujo físico)."""
    filas = []
    for _, c in conexiones.iterrows():
        op = c["operador_en_capa"] if isinstance(c["operador_en_capa"], str) else ""
        sub = km[km["operador"] == op] if op else km.iloc[0:0]
        tipos = sub.groupby("tipo")["km"].sum()
        filas.append({
            "gasoducto": c["gasoducto"], "operador_en_capa": op or None,
            "en_capa": bool(op) and not sub.empty,
            "tipo_en_capa": (tipos.idxmax() if not tipos.empty else None),
            "km": float(sub["km"].sum()), "estados_n": int(sub["estado_key"].nunique()),
            "estados": ", ".join(sorted(sub["estado_key"].unique())),
            "nota": c.get("nota") if isinstance(c.get("nota"), str) else None})
    return pd.DataFrame(filas)


def distancia_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Distancia geodésica (elipsoide WGS84) en km."""
    return abs(GEOD.inv(lon1, lat1, lon2, lat2)[2]) / 1000


def gnl_a_henry_hub(gnl: gpd.GeoDataFrame, hh: tuple[float, float]) -> pd.DataFrame:
    df = pd.DataFrame(gnl.drop(columns="geometry"))
    df["lon"], df["lat"] = gnl.geometry.x.values, gnl.geometry.y.values
    df["distancia_henry_hub_km"] = [distancia_km(x, y, *hh) for x, y in zip(df.lon, df.lat,
                                                                              strict=True)]
    return df.sort_values("distancia_henry_hub_km").reset_index(drop=True)


def validar(km: pd.DataFrame, gasoductos: gpd.GeoDataFrame, metricas: pd.DataFrame,
            crs: int) -> dict[str, Any]:
    total_red = float(gasoductos.to_crs(crs).length.sum() / 1000)
    en_estados = float(km["km"].sum())
    suma_metricas = float(metricas["km_total"].sum())
    cero = metricas.loc[metricas["km_total"] == 0, "estado_key"].tolist()
    return {"km_red_total": total_red, "km_dentro_de_estados": en_estados,
            "km_fuera_de_estados": total_red - en_estados,
            "pct_fuera": (total_red - en_estados) / total_red * 100 if total_red else 0,
            "suma_metricas_igual_interseccion": abs(suma_metricas - en_estados) < 1e-6 * max(
                en_estados, 1),
            "estados_sin_km": cero}


# ------------------------------------------------------------------ geometría para el mapa
def _redondear(geom: dict[str, Any], dec: int) -> dict[str, Any]:
    def r(c):
        if isinstance(c[0], (float, int)):
            return [round(c[0], dec), round(c[1], dec)]
        return [r(x) for x in c]
    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


def _poligonos_d3(geom):
    """d3-geo (Vega) espera anillos exteriores en sentido horario: orient(sign=-1)."""
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    if geom.geom_type == "MultiPolygon":
        return type(geom)([orient(p, sign=-1.0) for p in geom.geoms])
    return geom


def geojson_liviano(g: gpd.GeoDataFrame, props: list[str], cfg: GeoConfig,
                    tolerancia_m: float | None = None) -> dict[str, Any]:
    tol = cfg.tolerancia_m if tolerancia_m is None else tolerancia_m
    s = g.to_crs(cfg.crs_calculo)
    s = s.set_geometry(s.geometry.simplify(tol, preserve_topology=True)).to_crs(cfg.crs_visual)
    s = s[~s.geometry.is_empty]
    feats = []
    for _, f in s.iterrows():
        geom = _poligonos_d3(f.geometry)
        feats.append({"type": "Feature", "properties": {k: f[k] for k in props},
                      "geometry": _redondear(mapping(geom), cfg.decimales)})
    return {"type": "FeatureCollection", "features": feats}


def red_disuelta(gasoductos: gpd.GeoDataFrame, hh_ops: set[str]) -> gpd.GeoDataFrame:
    """Une los tramos por (tipo, operador) para achicar el archivo sin perder trazado."""
    filas = []
    for (tipo, op), sub in gasoductos.groupby(["tipo", "operador"]):
        geom = unary_union(list(sub.geometry))
        if geom.geom_type == "MultiLineString":  # un solo tramo ya es LineString
            geom = linemerge(geom)
        filas.append({"tipo": tipo, "operador": op, "hh": op in hh_ops, "geometry": geom})
    return gpd.GeoDataFrame(filas, crs=gasoductos.crs)


# ------------------------------------------------------------------ frescura de capas
def frescura_geo(cfg: GeoConfig, hoy: date, extra: list[dict[str, Any]]) -> pd.DataFrame:
    filas = []
    for nombre, capa in cfg.capas.items():
        try:
            _, man = ultimo(cfg, nombre)
            estado, registros = "disponible", man.get("registros")
        except Exception:  # noqa: BLE001 - se informa como no disponible
            estado, registros = "no disponible", None
        filas.append({"capa": nombre, "tipo": "estática", "origen": capa.origen,
                      "vintage": capa.vintage, "registros": registros, "estado": estado,
                      "calculado_al": hoy.isoformat()})
    for e in extra:
        filas.append({"calculado_al": hoy.isoformat(), **e})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ orquestación
def leer_conexiones() -> pd.DataFrame:
    return pd.read_csv(CONEXIONES_HH, dtype=str, keep_default_na=False).replace({"": None})


def run_gold(cfg: GeoConfig, hoy: date | None = None) -> dict[str, Any]:
    hoy = hoy or date.today()
    s = {p.stem: gpd.read_parquet(p) for p in cfg.silver_dir.glob("*.parquet")}
    estados, red = s["estados"], s["gasoductos"]
    conexiones = leer_conexiones()
    hh_ops = {o for o in conexiones["operador_en_capa"].dropna()}

    km = km_por_estado(red, estados, cfg.crs_calculo)
    metricas = metricas_estado(km, estados, hh_ops)
    alcance = alcance_henry_hub(km, conexiones)
    hh = s["hubs"].loc[s["hubs"]["nombre"] == "Henry Hub"].geometry
    if hh.empty:
        raise RuntimeError("No se encontró Henry Hub en la capa de hubs")
    hh_xy = (float(hh.iloc[0].x), float(hh.iloc[0].y))
    gnl = gnl_a_henry_hub(s["gnl"], hh_xy)
    val = validar(km, red, metricas, cfg.crs_calculo)

    extra = [{"capa": "gasoductos de recolección", "tipo": "estática",
              "origen": "la capa de la EIA solo distingue interestatal e intraestatal",
              "vintage": None, "registros": None, "estado": "no disponible"}]
    out = cfg.gold_dir
    out.mkdir(parents=True, exist_ok=True)
    tablas = {"geo_dim_estado": pd.DataFrame(estados.drop(columns="geometry")),
              "geo_estado_metricas": metricas, "geo_km_estado_operador": km,
              "geo_henry_hub_conexiones": alcance, "geo_gnl": gnl,
              "geo_hubs": _puntos(s["hubs"]), "geo_reserva_estrategica":
                  _puntos(s["reserva_estrategica"]),
              "frescura_geo": frescura_geo(cfg, hoy, extra)}
    for nombre, df in tablas.items():
        df.to_parquet(out / f"{nombre}.parquet", index=False)

    mapa = {
        "estados": geojson_liviano(estados, ["estado_key", "nombre"], cfg),
        "regiones": geojson_liviano(s["regiones_almacenamiento"], ["region_key"], cfg,
                                    tolerancia_m=cfg.tolerancia_m * 4),
        "red": geojson_liviano(red_disuelta(red, hh_ops), ["tipo", "operador", "hh"], cfg),
    }
    for nombre, fc in mapa.items():
        (out / f"mapa_{nombre}.geojson").write_text(
            json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / "validacion.json").write_text(json.dumps(val, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    log.info("Gold geo: %s", {k: len(v) for k, v in tablas.items()})
    return {"validacion": val, "tablas": tablas, "henry_hub": hh_xy,
            "bytes_mapa": {k: (out / f"mapa_{k}.geojson").stat().st_size for k in mapa}}


def _puntos(g: gpd.GeoDataFrame) -> pd.DataFrame:
    df = pd.DataFrame(g.drop(columns="geometry"))
    df["lon"], df["lat"] = g.geometry.x.values, g.geometry.y.values
    return df


def ruta_gold(cfg: GeoConfig, nombre: str) -> Path:
    return cfg.gold_dir / f"{nombre}.parquet"
