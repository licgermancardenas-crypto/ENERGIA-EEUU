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


def _refinerias_web(gold_geo: Path) -> dict[str, Any]:
    """Refinerías (capacidad en barriles/día calendario) y totales por estado de la API."""
    p, e = gold_geo / "geo_refinerias.parquet", gold_geo / "geo_estado_refinacion.parquet"
    ref = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    est = pd.read_parquet(e) if e.exists() else pd.DataFrame()
    return {
        "anio": int(est["anio"].max()) if len(est) else None,
        "refinerias": [{"id": r.refineria_id, "empresa": r.empresa, "sitio": r.sitio,
                        "estado": r.estado_key, "bcd": _num(r.capacidad_operable_bcd, 0),
                        "operando": _num(r.capacidad_operando_bcd, 0),
                        "lon": _num(r.lon, 4), "lat": _num(r.lat, 4)} for r in ref.itertuples()],
        "estados": {r.estado_key: {"n": int(r.refinerias_operables),
                                   "operando": int(r.refinerias_operando),
                                   "bcd": _num(r.capacidad_operable_bcd, 0)}
                    for r in est.itertuples()},
    }


def _fuentes_mapa() -> dict[str, str]:
    """Citas que muestra el mapa animado, leídas de config/pipeline.yaml (no se escriben a mano)."""
    from eia_pulso.geo.config import load_geo

    cfg = load_geo()
    return {"conexiones_henry_hub": cfg.fuente_conexiones_hh,
            "flujos": cfg.capas["flujos"].origen if "flujos" in cfg.capas else
            "EIA API v2 natural-gas/move/ist"}


def _centros_estados(gold_geo: Path) -> dict[str, list[float]]:
    """Punto interior de cada estado (extremo de los arcos de flujo), en lon/lat."""
    import geopandas as gpd

    silver = gold_geo.parent.parent / "silver_geo" / "estados.parquet"
    if not silver.exists():
        return {}
    g = gpd.read_parquet(silver).to_crs(5070)
    pts = g.geometry.representative_point().to_crs(4326)
    return {k: [round(p.x, 3), round(p.y, 3)] for k, p in zip(g["estado_key"], pts, strict=True)}


def _centrales(c: pd.DataFrame) -> list[dict[str, Any]]:
    """Centrales a gas (EIA-860M): solo lo que dibuja el mapa, coordenadas a ~100 m."""
    return [{"nombre": r.planta, "estado": r.estado_key, "mw": _num(r.capacidad_mw, 0),
             "lon": _num(r.lon, 3), "lat": _num(r.lat, 3), "km": _num(r.distancia_red_km, 1),
             "cerca": bool(r.dentro_umbral)} for r in c.itertuples()]


def _flujos(gold_geo: Path) -> dict[str, Any]:
    """Flujos interestatales de la EIA: pares [origen, destino, año, MMcf] y neto por estado."""
    pares_p = gold_geo / "geo_flujos_pares.parquet"
    pares = pd.read_parquet(pares_p) if pares_p.exists() else pd.DataFrame()
    est = pd.read_parquet(gold_geo / "geo_flujos_estado.parquet")
    return {
        "anios": sorted(int(a) for a in est["anio"].unique()),
        "pares": [[r.origen, r.destino, int(r.anio), round(float(r.mmcf))]
                  for r in pares.itertuples()],
        "estados": [[r.estado_key, int(r.anio), _num(r.recibe_mmcf, 0), _num(r.entrega_mmcf, 0),
                     _num(r.neto_mmcf, 0)] for r in est.itertuples()],
    }


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
    centro = _centros_estados(gold_geo)
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
            "anio_balance": int(r["anio"]) if pd.notna(r.get("anio")) else None,
            "centro": centro.get(r["estado_key"])})

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
                   "centrales": _centrales(leer("geo_centrales"))},
        "henry_hub": _registros(leer("geo_henry_hub_conexiones")),
        "frescura_geo": _registros(leer("frescura_geo").drop(columns=["calculado_al"])),
        "flujos": _flujos(gold_geo),
        "fuentes_mapa": _fuentes_mapa(),
        "refinerias": _refinerias_web(gold_geo),
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
    red = red_detallada(gold_geo)
    if red is not None:
        texto = json.dumps(red, ensure_ascii=False, separators=(",", ":"))
        (dest / "mapa_red_detalle.geojson").write_text(texto, encoding="utf-8")
        conteo["mapa_red_detalle.geojson"] = len(texto)
    cond = condados_detallados(gold_geo)
    if cond is not None:
        texto = json.dumps(cond, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        (dest / "mapa_condados_detalle.geojson").write_text(texto, encoding="utf-8")
        conteo["mapa_condados_detalle.geojson"] = len(texto)
    pul = pulsos_desde_henry_hub(gold_geo)
    if pul is not None:
        texto = json.dumps(pul, separators=(",", ":"))
        (dest / "pulsos.json").write_text(texto, encoding="utf-8")
        conteo["pulsos.json"] = len(texto)
    log.info("JSON geo exportados a %s", dest)
    return conteo


TOLERANCIA_CONDADOS_M = 500


def condados_detallados(gold_geo: Path) -> dict[str, Any] | None:
    """Condados con la calefacción ACS en las propiedades, para el mapa con zoom.

    coverage_simplify simplifica los bordes compartidos una sola vez: al acercarse no
    aparecen huecos ni superposiciones entre condados vecinos.
    """
    import geopandas as gpd
    import shapely
    from shapely.geometry import mapping

    from eia_pulso.geo.gold import _redondear

    silver = gold_geo.parent.parent / "silver_geo" / "condados.parquet"
    cal = gold_geo / "geo_condado_calefaccion.parquet"
    if not (silver.exists() and cal.exists()):
        return None
    g = gpd.read_parquet(silver).to_crs(5070)
    g = g.set_geometry(shapely.coverage_simplify(g.geometry.values, TOLERANCIA_CONDADOS_M))
    g = g.to_crs(4326).merge(pd.read_parquet(cal), on="condado_key", how="left")
    feats = []
    for r in g.itertuples():
        feats.append({"type": "Feature", "properties": {
            "k": r.condado_key, "estado": r.estado_key, "nombre": r.nombre,
            "pct": _num(r.pct_gas_red, 4), "moe": _num(r.pct_gas_red_moe, 4),
            "km": _num(r.distancia_red_km, 1), "alerta": bool(r.alta_dependencia_lejos)
            if pd.notna(r.alta_dependencia_lejos) else False},
            "geometry": _redondear(mapping(r.geometry), DECIMALES_DETALLE)})
    return {"type": "FeatureCollection", "features": feats}


TOLERANCIA_DETALLE_M = 100  # el mapa interactivo hace zoom: 15 veces más fino que el de Power BI
DECIMALES_DETALLE = 4       # ~11 m


def red_detallada(gold_geo: Path) -> dict[str, Any] | None:
    """Red por operador para el mapa con zoom de la web, con los km de cada operador."""
    import geopandas as gpd
    from shapely.geometry import mapping

    from eia_pulso.geo.gold import _redondear, red_disuelta

    silver = gold_geo.parent.parent / "silver_geo" / "gasoductos.parquet"
    if not silver.exists():
        return None
    hh = pd.read_parquet(gold_geo / "geo_henry_hub_conexiones.parquet")
    hh_ops = set(hh["operador_en_capa"].dropna())
    red = red_disuelta(gpd.read_parquet(silver), hh_ops).to_crs(5070)
    red["km"] = red.length / 1000
    red = red.set_geometry(red.geometry.simplify(TOLERANCIA_DETALLE_M)).to_crs(4326)
    feats = [{"type": "Feature",
              "properties": {"tipo": r.tipo, "operador": r.operador, "hh": bool(r.hh),
                             "km": round(float(r.km))},
              "geometry": _redondear(mapping(r.geometry), DECIMALES_DETALLE)}
             for r in red.itertuples() if not r.geometry.is_empty]
    return {"type": "FeatureCollection", "features": feats}


# ------------------------------------------------------------------ pulsos (mapa animado)
TOLERANCIA_PULSOS_M = 3000   # la onda se ve a escala país: no necesita más detalle
REDONDEO_NODO = 2            # ~1 km: une tramos de distintos operadores que se tocan


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def pulsos_desde_henry_hub(gold_geo: Path) -> dict[str, Any] | None:
    """Trayectos con 'tiempo' = km recorridos por la red desde el Henry Hub (Dijkstra).

    Sirve SOLO para animar una onda ilustrativa que sale del hub: no es caudal ni velocidad
    real del gas (la EIA no publica volúmenes por gasoducto). Cada tramo se corta en piezas
    donde la distancia crece de forma monótona, como pide la capa de trayectos de deck.gl.
    """
    import heapq

    import geopandas as gpd

    silver = gold_geo.parent.parent / "silver_geo" / "gasoductos.parquet"
    if not silver.exists():
        return None
    hubs = pd.read_parquet(gold_geo / "geo_hubs.parquet")
    hh = hubs[hubs["nombre"] == "Henry Hub"]
    if hh.empty:
        return None
    origen = (float(hh.iloc[0]["lon"]), float(hh.iloc[0]["lat"]))
    g = gpd.read_parquet(silver).to_crs(5070)
    g = g.set_geometry(g.geometry.simplify(TOLERANCIA_PULSOS_M)).to_crs(4326)

    partes: list[list[tuple[float, float]]] = []
    for geom in g.geometry:
        if geom is None or geom.is_empty:
            continue
        for linea in getattr(geom, "geoms", [geom]):
            cs = [(round(x, 3), round(y, 3)) for x, y in linea.coords]
            if len(cs) >= 2:
                partes.append(cs)

    def nodo(c: tuple[float, float]) -> tuple[float, float]:
        return (round(c[0], REDONDEO_NODO), round(c[1], REDONDEO_NODO))

    vecinos: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {}
    for cs in partes:
        for a, b in zip(cs, cs[1:], strict=False):
            na, nb, d = nodo(a), nodo(b), _km(a, b)
            vecinos.setdefault(na, []).append((nb, d))
            vecinos.setdefault(nb, []).append((na, d))
    inicio = min(vecinos, key=lambda n: _km(n, origen))
    dist = {inicio: 0.0}
    cola = [(0.0, inicio)]
    while cola:
        d, n = heapq.heappop(cola)
        if d > dist.get(n, float("inf")):
            continue
        for m, w in vecinos[n]:
            nd = d + w
            if nd < dist.get(m, float("inf")):
                dist[m] = nd
                heapq.heappush(cola, (nd, m))

    trayectos: list[list[list[float]]] = []
    for cs in partes:
        ds = [dist.get(nodo(c)) for c in cs]
        if any(x is None for x in ds):
            continue  # tramo no conectado al Henry Hub
        piezas, actual = [], [0]
        for i in range(1, len(cs)):
            if len(actual) >= 2 and (ds[i] >= ds[i - 1]) != (ds[actual[-1]] >= ds[actual[-2]]):
                piezas.append(actual)   # cambia el sentido: se corta en el vértice anterior
                actual = [i - 1]
            actual.append(i)
        piezas.append(actual)
        for ids in piezas:
            pts = [[cs[j][0], cs[j][1], round(ds[j], 1)] for j in ids]
            if pts[0][2] > pts[-1][2]:
                pts.reverse()
            if len(pts) >= 2:
                trayectos.append(pts)
    return {"origen": list(origen), "max_km": round(max(t[-1][2] for t in trayectos)),
            "trayectos": trayectos}
