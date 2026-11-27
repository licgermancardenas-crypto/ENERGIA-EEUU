"""Gold geoespacial: métricas por estado, alcance del Henry Hub, proximidad y geometría liviana.

Todas las longitudes y áreas se calculan en EPSG:5070 (Albers de área equivalente); la
geometría que se exporta para el informe vuelve a WGS84, simplificada y con coordenadas
redondeadas. Ninguna cifra se completa a mano: lo que falta se marca como no disponible.
"""

from __future__ import annotations

import json
import logging
import os
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
            piv[t] = float("nan") if t == "recoleccion" else 0.0
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


def region_de_estado(estados: gpd.GeoDataFrame, regiones: gpd.GeoDataFrame,
                     crs: int) -> pd.Series:
    """Región de almacenamiento de la EIA de cada estado (por su punto interior)."""
    pts = estados.to_crs(crs).copy()
    pts["geometry"] = pts.representative_point()
    j = gpd.sjoin(pts[["estado_key", "geometry"]], regiones[["region_key", "geometry"]]
                  .to_crs(crs), how="left", predicate="within")
    faltan = j.loc[j["region_key"].isna(), "estado_key"]
    if len(faltan):  # puntos sobre un borde: se asigna la región más cercana
        # solo si el punto quedó sobre un borde (< 50 km); Alaska y Hawái no tienen región EIA
        cerca = gpd.sjoin_nearest(pts[pts["estado_key"].isin(faltan)][["estado_key", "geometry"]],
                                  regiones[["region_key", "geometry"]].to_crs(crs),
                                  max_distance=50_000)
        j = pd.concat([j.dropna(subset=["region_key"]), cerca])
    return j.drop_duplicates("estado_key").set_index("estado_key")["region_key"]


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
NOMBRES_CAPA = {"gasoductos": "Gasoductos", "hubs": "Hubs de gas",
                "gnl": "Terminales de GNL", "reserva_estrategica": "Reserva estratégica",
                "regiones_almacenamiento": "Regiones de almacenamiento",
                "estados": "Estados (Census)", "condados": "Condados (Census)"}


def frescura_geo(cfg: GeoConfig, hoy: date, extra: list[dict[str, Any]]) -> pd.DataFrame:
    filas = []
    for nombre, capa in cfg.capas.items():
        try:
            _, man = ultimo(cfg, nombre)
            estado, registros = "disponible", man.get("registros")
        except Exception:  # noqa: BLE001 - se informa como no disponible
            estado, registros = "no disponible", None
        filas.append({"capa": NOMBRES_CAPA.get(nombre, nombre), "tipo": "estática",
                      "origen": capa.origen,
                      "vintage": capa.vintage, "registros": registros, "estado": estado,
                      "calculado_al": hoy.isoformat()})
    for e in extra:
        filas.append({"calculado_al": hoy.isoformat(), **e})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ orquestación
def leer_conexiones() -> pd.DataFrame:
    ruta = Path(os.environ.get("EIA_PULSO_CONEXIONES_HH", CONEXIONES_HH))  # Fabric: otra ruta
    return pd.read_csv(ruta, dtype=str, keep_default_na=False).replace({"": None})


def moe_proporcion(num, moe_num, den, moe_den):
    """MOE de una proporción (fórmula del Census; si el radicando es negativo, se suma)."""
    import numpy as np
    p = num / den
    rad = moe_num ** 2 - p ** 2 * moe_den ** 2
    rad = np.where(rad < 0, moe_num ** 2 + p ** 2 * moe_den ** 2, rad)
    return np.sqrt(rad) / den


def calefaccion_condado(condados: gpd.GeoDataFrame, acs: pd.DataFrame, red: gpd.GeoDataFrame,
                        crs: int, umbral_km: float, umbral_dep: float
                        ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """% de hogares que calefaccionan con gas de red y distancia del condado a la red troncal.

    La distancia es del polígono del condado al gasoducto más cercano (0 si la red lo cruza).
    """
    c = condados.to_crs(crs)
    d = gpd.sjoin_nearest(c[["condado_key", "geometry"]], red[["geometry"]].to_crs(crs),
                          distance_col="d_m").drop_duplicates("condado_key")
    df = pd.DataFrame(condados.drop(columns="geometry")).merge(
        d[["condado_key", "d_m"]], on="condado_key", how="left").merge(
        acs, on="condado_key", how="left")
    df["distancia_red_km"] = df.pop("d_m") / 1000
    df["pct_gas_red"] = df["gas_red"] / df["hogares"]
    df["pct_gas_red_moe"] = moe_proporcion(df["gas_red"], df["gas_red_moe"], df["hogares"],
                                           df["hogares_moe"])
    df["pct_propano"] = df["propano"] / df["hogares"]
    df["alta_dependencia_lejos"] = ((df["pct_gas_red"] >= umbral_dep)
                                    & (df["distancia_red_km"] > umbral_km))
    val = {"condados": len(condados), "condados_acs": int(acs["condado_key"].nunique()),
           "condados_sin_acs": sorted(set(condados["condado_key"]) - set(acs["condado_key"])),
           "acs_sin_condado": sorted(set(acs["condado_key"]) - set(condados["condado_key"])),
           "condados_alta_dependencia_lejos": int(df["alta_dependencia_lejos"].sum())}
    return df, val


def calefaccion_estado(cond: pd.DataFrame) -> pd.DataFrame:
    g = cond.groupby("estado_key")
    out = pd.DataFrame({
        "hogares": g["hogares"].sum(), "hogares_gas_red": g["gas_red"].sum(),
        "hogares_propano": g["propano"].sum(),
        "condados_alta_dependencia_lejos": g["alta_dependencia_lejos"].sum().astype("int64"),
        "hogares_gas_red_lejos": cond[cond["alta_dependencia_lejos"]].groupby("estado_key")[
            "gas_red"].sum()}).reset_index()
    out["hogares_gas_red_lejos"] = out["hogares_gas_red_lejos"].fillna(0.0)
    out["pct_gas_red"] = out["hogares_gas_red"] / out["hogares"]
    out["pct_propano"] = out["hogares_propano"] / out["hogares"]
    return out


def run_gold(cfg: GeoConfig, hoy: date | None = None) -> dict[str, Any]:
    hoy = hoy or date.today()
    s = {p.stem: gpd.read_parquet(p) for p in cfg.silver_dir.glob("*.parquet")
         if p.stem != "acs"}
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

    claves = set(estados["estado_key"])
    acs_path = cfg.silver_dir / "acs.parquet"
    if acs_path.exists() and "condados" in s:
        cond, val_cond = calefaccion_condado(s["condados"], pd.read_parquet(acs_path), red,
                                             cfg.crs_calculo, cfg.umbral_proximidad_km,
                                             cfg.umbral_dependencia)
        val["calefaccion"] = val_cond
        cal_estado = calefaccion_estado(cond)
    else:
        cond, cal_estado = pd.DataFrame(), pd.DataFrame()
    filas_f, man_f = _bronze_api(cfg, "flujos")
    filas_c, man_c = _bronze_api(cfg, "centrales")
    flujos = flujos_estado(filas_f, claves)
    pares = flujos_pares(filas_f, claves)
    centrales = centrales_a_red(filas_c, red, cfg.crs_calculo, cfg.umbral_proximidad_km, claves)
    if len(flujos):
        val["flujos_cierre_ok"] = bool(flujos["cierre_ok"].all())
    extra = [{"capa": "Gasoductos de recolección", "tipo": "estática",
              "origen": "la capa de la EIA solo distingue interestatal e intraestatal",
              "vintage": None, "registros": None, "estado": "no disponible"}]
    try:
        _, man_acs = ultimo(cfg, "acs")
    except Exception:  # noqa: BLE001
        man_acs = None
    extra.append({"capa": "ACS calefacción (B25040)", "tipo": "encuesta",
                  "origen": "U.S. Census Bureau, ACS 5 años (Summary File)",
                  "vintage": man_acs.get("vintage") if man_acs else None,
                  "registros": man_acs.get("registros") if man_acs else None,
                  "estado": "disponible" if man_acs else "no disponible"})
    for nombre, man, tipo, origen in [
            ("Flujos interestatales", man_f, "anual", "EIA API v2 natural-gas/move/ist"),
            ("Centrales a gas (EIA-860M)", man_c, "mensual",
             "EIA API v2 electricity/operating-generator-capacity")]:
        extra.append({"capa": nombre, "tipo": tipo, "origen": origen,
                      "vintage": man.get("vintage") if man else None,
                      "registros": man.get("registros") if man else None,
                      "estado": "disponible" if man else "no disponible"})
    out = cfg.gold_dir
    out.mkdir(parents=True, exist_ok=True)
    dim_estado = pd.DataFrame(estados.drop(columns="geometry"))
    dim_estado["region_key"] = dim_estado["estado_key"].map(
        region_de_estado(estados, s["regiones_almacenamiento"], cfg.crs_calculo))
    metricas = metricas.drop(columns=["fips", "nombre", "area_km2"])
    metricas["km_recoleccion"] = pd.to_numeric(metricas["km_recoleccion"], errors="coerce")
    tablas = {"geo_dim_estado": dim_estado,
              "geo_estado_metricas": metricas, "geo_km_estado_operador": km,
              "geo_henry_hub_conexiones": alcance, "geo_gnl": gnl,
              "geo_hubs": _puntos(s["hubs"]), "geo_reserva_estrategica":
                  _puntos(s["reserva_estrategica"]),
              "geo_flujos_estado": flujos, "geo_flujos_pares": pares, "geo_centrales": centrales,
              "geo_capas_mapa": CAPAS_MAPA.copy(),
              "geo_dim_condado": pd.DataFrame(s["condados"].drop(columns="geometry"))
              if "condados" in s else pd.DataFrame(),
              "geo_condado_calefaccion": cond.drop(columns=["estado_key", "nombre", "area_km2"],
                                                   errors="ignore"),
              "geo_estado_calefaccion": cal_estado,
              "frescura_geo": frescura_geo(cfg, hoy, extra)}
    for nombre, df in tablas.items():
        df.to_parquet(out / f"{nombre}.parquet", index=False)

    mapa = {
        "estados": geojson_liviano(estados, ["estado_key", "nombre"], cfg),
        "condados": geojson_liviano(s["condados"], ["condado_key"], cfg,
                                    tolerancia_m=cfg.tolerancia_m * 2),
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


# Capas que el usuario puede prender y apagar en el mapa (segmentador). Las flechas de flujo
# no se ofrecen: la EIA publica totales por estado, no pares origen-destino.
CAPAS_MAPA = pd.DataFrame({
    "capa": ["Gasoductos", "Hubs", "Terminales de GNL", "Centrales a gas",
             "Regiones de almacenamiento", "Reserva estratégica"],
    "orden": [1, 2, 3, 4, 5, 6]})

COLS_FLUJOS = {"estado_key": "str", "anio": "int64", "recibe_mmcf": "float64",
               "entrega_mmcf": "float64", "neto_mmcf": "float64", "rol": "str",
               "cierre_ok": "bool"}
COLS_CENTRALES = {"planta_id": "str", "planta": "str", "estado_key": "str",
                  "capacidad_mw": "float64", "lon": "float64", "lat": "float64",
                  "distancia_red_km": "float64", "dentro_umbral": "bool"}


def _vacia(cols: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in cols.items()})


COLS_PARES = {"origen": "str", "destino": "str", "anio": "int64", "mmcf": "float64"}


def flujos_pares(filas: list[dict[str, Any]], estados: set[str]) -> pd.DataFrame:
    """Entregas entre pares de estados por año (MMcf), para los arcos del mapa.

    En la API v2 "SIN-SKY" con proceso MID se lee "Indiana entrega a Kentucky". Se usan solo
    las entregas (MID): la recepción del otro lado (MIR de "SKY-SIN") es el mismo volumen.
    Se descartan áreas que no son estados (offshore federal R3FM, Canadá, México, totales).
    """
    if not filas:
        return _vacia(COLS_PARES)
    df = pd.DataFrame(filas)
    m = df["duoarea"].str.extract(r"^S([A-Z]{2})-S([A-Z]{2})$")
    df = df.assign(origen=m[0], destino=m[1])
    df = df[(df["process"] == "MID") & df["origen"].isin(estados) & df["destino"].isin(estados)]
    df = df.assign(anio=df["period"].astype(int), mmcf=pd.to_numeric(df["value"], errors="coerce"))
    df = df[df["mmcf"] > 0]
    return df[list(COLS_PARES)].astype(COLS_PARES).reset_index(drop=True)


def flujos_estado(filas: list[dict[str, Any]], estados: set[str]) -> pd.DataFrame:
    """Recibe/entrega/neto interestatal por estado y año (MMcf). Valida MIN = MIR - MID."""
    if not filas:
        return _vacia(COLS_FLUJOS)
    df = pd.DataFrame(filas)
    # totales por estado: "SLA-Z0S" (API v2 actual) o "SLA" (formato corto)
    df = df[df["duoarea"].str.match(r"^S[A-Z]{2}(-Z0S)?$")].copy()
    df["estado_key"] = df["duoarea"].str[1:3]
    df = df[df["estado_key"].isin(estados)]
    df["valor"] = pd.to_numeric(df["value"], errors="coerce")
    p = df.pivot_table(index=["estado_key", "period"], columns="process", values="valor",
                       aggfunc="sum").reset_index()
    out = pd.DataFrame({"estado_key": p["estado_key"], "anio": p["period"].astype(int),
                        "recibe_mmcf": p.get("MIR"), "entrega_mmcf": p.get("MID"),
                        "neto_mmcf": p.get("MIN")})
    calc = out["recibe_mmcf"] - out["entrega_mmcf"]
    out["cierre_ok"] = (calc - out["neto_mmcf"]).abs() <= out["recibe_mmcf"].abs() * 1e-3 + 1
    out["rol"] = out["neto_mmcf"].map(
        lambda v: "importador neto" if v > 0 else ("exportador neto" if v < 0 else "neutro"))
    return out.astype({c: t for c, t in COLS_FLUJOS.items() if c in out})


def centrales_a_red(filas: list[dict[str, Any]], red: gpd.GeoDataFrame, crs: int,
                    umbral_km: float, estados: set[str]) -> pd.DataFrame:
    """Plantas a gas (suma de generadores) y su distancia al gasoducto más cercano."""
    if not filas:
        return _vacia(COLS_CENTRALES)
    df = pd.DataFrame(filas)
    df["mw"] = pd.to_numeric(df["nameplate-capacity-mw"], errors="coerce")
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lon"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df[df["stateid"].isin(estados) & df["lat"].notna() & df["lon"].notna()]
    pl = df.groupby("plantid").agg(planta=("plantName", "first"), estado_key=("stateid", "first"),
                                   capacidad_mw=("mw", "sum"), lon=("lon", "first"),
                                   lat=("lat", "first")).reset_index()
    g = gpd.GeoDataFrame(pl, geometry=gpd.points_from_xy(pl["lon"], pl["lat"]), crs=4326)
    j = gpd.sjoin_nearest(g.to_crs(crs), red[["geometry"]].to_crs(crs), distance_col="d_m")
    j = j.drop_duplicates("plantid")
    out = pd.DataFrame({"planta_id": j["plantid"].astype(str), "planta": j["planta"],
                        "estado_key": j["estado_key"], "capacidad_mw": j["capacidad_mw"],
                        "lon": j["lon"], "lat": j["lat"], "distancia_red_km": j["d_m"] / 1000})
    out["dentro_umbral"] = out["distancia_red_km"] <= umbral_km
    return out.reset_index(drop=True)


def _bronze_api(cfg: GeoConfig, capa: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        ruta, man = ultimo(cfg, capa)
    except Exception:  # noqa: BLE001 - la API no respondió: se informa como no disponible
        return [], None
    return json.loads(ruta.read_text(encoding="utf-8")), man


def _puntos(g: gpd.GeoDataFrame) -> pd.DataFrame:
    df = pd.DataFrame(g.drop(columns="geometry"))
    df["lon"], df["lat"] = g.geometry.x.values, g.geometry.y.values
    return df


def ruta_gold(cfg: GeoConfig, nombre: str) -> Path:
    return cfg.gold_dir / f"{nombre}.parquet"
