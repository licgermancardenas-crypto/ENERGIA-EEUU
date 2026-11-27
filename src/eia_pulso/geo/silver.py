"""Silver geoespacial: normaliza cada capa Bronze a GeoParquet (WGS84) con campos en español.

Valida lo mínimo para seguir: geometrías no vacías, tipos esperados y claves sin duplicados.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd

from eia_pulso.geo.bronze import ultimo
from eia_pulso.geo.config import GeoConfig

log = logging.getLogger(__name__)

TIPOS_GASODUCTO = {"Interstate": "interestatal", "Intrastate": "intraestatal",
                   "Gathering": "recoleccion"}
REGIONES = {"East": "R31", "Midwest": "R32", "South Central": "R33", "Mountain": "R34",
            "Pacific": "R35"}


class GeoSilverError(RuntimeError):
    """Una capa no cumple lo esperado (tipos, claves o geometrías)."""


def _leer(cfg: GeoConfig, capa: str) -> gpd.GeoDataFrame:
    ruta, _ = ultimo(cfg, capa)
    src = f"zip://{ruta}" if ruta.suffix == ".zip" else ruta
    g = gpd.read_file(src)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g.to_crs(cfg.crs_visual)


def silver_estados(g: gpd.GeoDataFrame, excluidos: tuple[str, ...], crs_calculo: int
                   ) -> gpd.GeoDataFrame:
    g = g[~g["STUSPS"].isin(excluidos)].copy()
    out = gpd.GeoDataFrame({
        "estado_key": g["STUSPS"].astype(str), "fips": g["STATEFP"].astype(str).str.zfill(2),
        "nombre": g["NAME"].astype(str)}, geometry=g.geometry.values, crs=g.crs)
    out["area_km2"] = out.to_crs(crs_calculo).area / 1e6
    if out["estado_key"].duplicated().any():
        raise GeoSilverError("estados: abreviaturas duplicadas")
    return out.sort_values("estado_key").reset_index(drop=True)


def silver_gasoductos(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    desconocidos = set(g["TYPEPIPE"].dropna()) - set(TIPOS_GASODUCTO)
    if desconocidos:
        raise GeoSilverError(f"gasoductos: TYPEPIPE inesperado {desconocidos}")
    g = g.explode(index_parts=False)
    g = g[g.geom_type == "LineString"]
    return gpd.GeoDataFrame({
        "tipo": g["TYPEPIPE"].map(TIPOS_GASODUCTO).fillna("sin_dato"),
        "operador": g["Operator"].fillna("Sin dato").str.strip(),
        "estado_operativo": g["Status"].fillna("Sin dato")},
        geometry=g.geometry.values, crs=g.crs).reset_index(drop=True)


def silver_regiones(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    faltan = set(g["Region"]) - set(REGIONES)
    if faltan:
        raise GeoSilverError(f"regiones: nombres inesperados {faltan}")
    return gpd.GeoDataFrame({"region_key": g["Region"].map(REGIONES), "nombre_eia": g["Region"]},
                            geometry=g.geometry.values, crs=g.crs)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.strip().replace({"-": None, ".": None}),
                         errors="coerce")


def silver_puntos(capa: str, g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if capa == "hubs":
        df = pd.DataFrame({"nombre": g["HubName"].str.strip(), "periodo": g["Period"].astype(str)})
    elif capa == "gnl":
        df = pd.DataFrame({
            "nombre": g["Facility"].str.strip(), "operador": g["Operator"].str.strip(),
            "ciudad": g["City"], "estado": g["State"], "funcion": g["Functions"],
            "licuefaccion_bcfd": _num(g["Liq_Bcfd"]), "regasificacion_bcfd": _num(g["Regas_Bcfd"]),
            "almacenamiento_bcf": _num(g["Stora_Bcf"]), "periodo": g["Period"]})
    elif capa == "reserva_estrategica":
        df = pd.DataFrame({"nombre": g["Site"].str.strip(), "estado": g["State"],
                           "capacidad_mmbbl": _num(g["Capacity"]), "periodo": g["Period"]})
    else:
        raise GeoSilverError(f"capa de puntos desconocida: {capa}")
    return gpd.GeoDataFrame(df.reset_index(drop=True), geometry=g.geometry.values, crs=g.crs)


def run_silver(cfg: GeoConfig) -> dict[str, gpd.GeoDataFrame]:
    capas = {
        "estados": silver_estados(_leer(cfg, "estados"), cfg.estados_excluidos, cfg.crs_calculo),
        "gasoductos": silver_gasoductos(_leer(cfg, "gasoductos")),
        "regiones_almacenamiento": silver_regiones(_leer(cfg, "regiones_almacenamiento")),
    }
    for p in ("hubs", "gnl", "reserva_estrategica"):
        capas[p] = silver_puntos(p, _leer(cfg, p))
    cfg.silver_dir.mkdir(parents=True, exist_ok=True)
    for nombre, g in capas.items():
        g.to_parquet(cfg.silver_dir / f"{nombre}.parquet", index=False)
        log.info("Silver geo %s: %d filas", nombre, len(g))
    return capas
