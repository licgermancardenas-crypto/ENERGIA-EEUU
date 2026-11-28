# ruff: noqa: E501  (URLs de servicios y rótulos largos)
"""Prepara los datos del mapa de petróleo (/petroleo-red) a partir de fuentes públicas verificadas.

    python scripts/preparar_mapa_petroleo.py

Descarga las capas (copias públicas en ArcGIS Online de capas oficiales de la EIA, BTS/USACE y
BOEM), las simplifica, calcula km de ducto en EPSG:5070 (igual que el mapa de gas), arma los
pulsos ILUSTRATIVOS desde Cushing con la misma función que el mapa de gas, baja las series de la
API v2 de la EIA y escribe todo en web/public/data/petroleo/ con la fecha de descarga.
Las respuestas crudas quedan en data/bronze_geo/petroleo/<fecha>/ (fuera del repo).

Verificación de fuentes (Fase 0): docs/mapa-petroleo.md.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
from shapely.geometry import Point, mapping

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from eia_pulso.geo.bronze import descargar_arcgis  # noqa: E402
from eia_pulso.geo.config import Capa  # noqa: E402
from eia_pulso.web.export_geo import pulsos_desde  # noqa: E402

SALIDA = RAIZ / "web" / "public" / "data" / "petroleo"
CRUDO = RAIZ / "data" / "bronze_geo" / "petroleo" / date.today().isoformat()
API = "https://api.eia.gov/v2/"
DOMINIO_PUBLICO = "Dominio público (datos del gobierno de EE. UU.)"

# ------------------------------------------------------------------ parámetros
TOL_LINEAS_M = 500        # simplificación de ductos (a escala país-región)
TOL_PLAYS_M = 1000        # simplificación de los polígonos de plays de shale
DECIMALES = 4             # ~11 m
ANIO_DESDE = 2015         # series anuales desde este año
# Unión de tramos para los pulsos: los oleoductos troncales de la EIA no comparten vértices
# exactos, así que se unen los extremos a ~10 km (1 decimal); el gas usa ~1 km.
REDONDEO_NODO_CRUDO = 1

CAPAS: dict[str, dict[str, Any]] = {
    "oleoductos": {
        "url": "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Crude_Oil_Trunk_Pipelines_1/FeatureServer/0",
        "origen": "EIA, Crude Oil Trunk Pipelines (copia pública en ArcGIS Online, Federal User Community)",
        "vintage": None, "licencia": DOMINIO_PUBLICO},
    "poliductos": {
        "url": "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Petroleum_Products_Pipelines_1/FeatureServer/0",
        "origen": "EIA, Petroleum Products Pipelines (copia pública en ArcGIS Online, Federal User Community)",
        "vintage": None, "licencia": DOMINIO_PUBLICO},
    "terminales": {
        "url": "https://services.arcgis.com/kbDdtKcFi2adamXa/arcgis/rest/services/Petroleum_Product_Terminals_US_EIA/FeatureServer/0",
        "origen": "EIA, Petroleum Product Terminals (formulario EIA-815; copia pública en ArcGIS Online)",
        "vintage": "2023-06", "licencia": DOMINIO_PUBLICO},
    "puertos": {
        "url": "https://services7.arcgis.com/n1YM8pTrFmm7L4hs/ArcGIS/rest/services/Principal_Ports/FeatureServer/0",
        "origen": "USACE / USDOT BTS, Principal Ports (NTAD). Toneladas de TODAS las cargas, no solo crudo",
        "vintage": "2023", "licencia": DOMINIO_PUBLICO},
    "plays": {
        "url": "https://services7.arcgis.com/FGr1D95XCGALKXqM/arcgis/rest/services/TightOil_ShaleGas_Plays_Lower48_EIA/FeatureServer/0",
        "origen": "EIA, Tight Oil and Shale Gas Plays, Lower 48 (cuenta EIA.gov en ArcGIS Online)",
        "vintage": None, "licencia": DOMINIO_PUBLICO},
    "plataformas": {
        "url": "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/OCS_Oil_And_Natural_Gas_Platforms_Gulf_2024Q4/FeatureServer/0",
        "origen": "BOEM, OCS Oil and Natural Gas Platforms, Golfo, 4.º trimestre 2024 (vía Esri US Federal Data)",
        "vintage": "2024-Q4", "licencia": DOMINIO_PUBLICO},
}

# Cushing, Oklahoma: punto de entrega del WTI (EIA, área YCUOK). No hay capa pública de "hub de
# crudo": se usa el punto interior de la ciudad en el Census (TIGERweb, Incorporated Places,
# GEOID 4018850). Los parques de tanques están en las afueras.
CUSHING = {"nombre": "Cushing, Oklahoma", "lon": -96.7617533, "lat": 35.9796807,
           "fuente": "U.S. Census TIGERweb (lugar 4018850) · EIA (área YCUOK, punto de entrega del WTI)"}

NO_DISPONIBLES = [
    {"capa": "Rigs activos (Baker Hughes)", "motivo": "sin licencia pública clara de redistribución; "
     "las series de rigs del STEO derivan de Baker Hughes"},
    {"capa": "Pozos y ductos offshore (BOEM)", "motivo": "no verificados en la Fase 0"},
    {"capa": "Comercio de crudo por puerto", "motivo": "la API v2 de la EIA publica importaciones y "
     "exportaciones por PADD, no por puerto"},
    {"capa": "Producción por cuenca de shale", "motivo": "el STEO mezcla historia y pronóstico sin "
     "marcar cada dato; se muestra la producción por estado"},
    {"capa": "Profundidad de agua de las plataformas", "motivo": "la capa de BOEM usada no trae ese campo"},
]


def _redondear(geom: dict[str, Any]) -> dict[str, Any]:
    def r(c: Any) -> Any:
        if isinstance(c[0], (int, float)):
            return [round(c[0], DECIMALES), round(c[1], DECIMALES)]
        return [r(x) for x in c]
    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


def bajar(nombre: str) -> gpd.GeoDataFrame:
    c = CAPAS[nombre]
    destino = CRUDO / f"{nombre}.geojson"
    if not destino.exists():
        contenido, n = descargar_arcgis(Capa(nombre, "", c["origen"], c["vintage"] or "", c["url"]))
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        print(f"  {nombre}: {n} elementos descargados", flush=True)
    return gpd.read_file(destino)


def fc(g: gpd.GeoDataFrame, props: list[str]) -> dict[str, Any]:
    feats = []
    for _, f in g.iterrows():
        if f.geometry is None or f.geometry.is_empty:
            continue
        feats.append({"type": "Feature", "properties": {k: f[k] for k in props},
                      "geometry": _redondear(mapping(f.geometry))})
    return {"type": "FeatureCollection", "features": feats}


def lineas(nombre: str) -> tuple[dict[str, Any], float, gpd.GeoDataFrame]:
    g = bajar(nombre)
    g = g.rename(columns={"Opername": "operador", "Pipename": "nombre"})
    m = g.to_crs(5070)
    g["km"] = (m.length / 1000).round(1)
    km_total = float(m.length.sum() / 1000)
    s = m.set_geometry(m.geometry.simplify(TOL_LINEAS_M)).to_crs(4326)
    s["operador"], s["nombre"], s["km"] = g["operador"], g["nombre"], g["km"]
    return fc(s, ["operador", "nombre", "km"]), km_total, g


# ------------------------------------------------------------------ API de la EIA
def api(ruta: str, facets: dict[str, list[str]], freq: str = "annual", inicio: str | None = None
        ) -> list[dict[str, Any]]:
    k = os.environ.get("EIA_API_KEY")
    if not k:
        raise SystemExit("Falta EIA_API_KEY (está en .env)")
    filas, off = [], 0
    while True:
        p: list[tuple[str, str]] = [("api_key", k), ("frequency", freq), ("data[0]", "value"),
                                     ("offset", str(off)), ("length", "5000")]
        if inicio:
            p.append(("start", inicio))
        for f, vs in facets.items():
            p += [(f"facets[{f}][]", v) for v in vs]
        r = requests.get(API + ruta + "/data/", params=p, timeout=180)
        r.raise_for_status()
        d = r.json()["response"]
        filas += d["data"]
        off += len(d["data"])
        if off >= int(d["total"]) or not d["data"]:
            return filas


def series() -> dict[str, Any]:
    desde = str(ANIO_DESDE)
    prod = api("petroleum/crd/crpdn", {"process": ["FPF"], "product": ["EPC0"]}, "annual", desde)
    prod = [f for f in prod if f["units"] == "MBBL/D" and f["value"] is not None]
    estados: dict[str, dict[str, float]] = {}
    padd: dict[str, dict[str, float]] = {}
    offshore: dict[str, float] = {}
    for f in prod:
        a, v, area = f["period"], float(f["value"]), f["duoarea"]
        if area.startswith("S") and len(area) == 3:
            estados.setdefault(area[1:], {})[a] = v
        elif area in ("R10", "R20", "R30", "R40", "R50"):
            padd.setdefault(area, {})[a] = v
        elif area == "R3FM":
            offshore[a] = v
    mens = api("petroleum/crd/crpdn", {"process": ["FPF"], "product": ["EPC0"],
                                        "duoarea": ["NUS", "R3FM"]}, "monthly", f"{ANIO_DESDE}-01")
    mens = sorted((f for f in mens if f["units"] == "MBBL/D" and f["value"] is not None),
                  key=lambda f: f["period"])
    nacional_mensual = [[f["period"], float(f["value"])] for f in mens if f["duoarea"] == "NUS"]
    comercio: dict[str, dict[str, dict[str, float]]] = {"importaciones": {}, "exportaciones": {}}
    for clave, ruta, proc in (("importaciones", "petroleum/move/imp", "IM0"),
                              ("exportaciones", "petroleum/move/exp", "EEX")):
        for f in api(ruta, {"product": ["EPC0"], "process": [proc]}, "annual", desde):
            if f["units"] == "MBBL/D" and f["value"] is not None and f["duoarea"].endswith("-Z00"):
                comercio[clave].setdefault(f["duoarea"][:3], {})[f["period"]] = float(f["value"])
    return {"unidad": "miles de barriles por día (promedio anual)",
            "produccion_estado": estados, "produccion_padd": padd, "offshore_golfo": offshore,
            "produccion_nacional_mensual": nacional_mensual, "comercio_crudo_padd": comercio,
            "rutas": {"produccion": "petroleum/crd/crpdn (process FPF, product EPC0)",
                      "importaciones": "petroleum/move/imp (product EPC0, process IM0)",
                      "exportaciones": "petroleum/move/exp (product EPC0, process EEX)",
                      "offshore": "petroleum/crd/crpdn, duoarea R3FM"}}


def main() -> int:
    hoy = date.today().isoformat()
    SALIDA.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {"fecha_descarga": hoy, "capas": {}, "no_disponibles": NO_DISPONIBLES,
                            "cushing": CUSHING}

    def escribir(nombre: str, obj: Any, n: int | None = None, extra: dict[str, Any] | None = None):
        texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        (SALIDA / f"{nombre}.json").write_text(texto, encoding="utf-8")
        c = CAPAS.get(nombre, {})
        meta["capas"][nombre] = {"origen": c.get("origen"), "url": c.get("url"),
                                 "vintage": c.get("vintage"), "licencia": c.get("licencia"),
                                 "elementos": n, "bytes": len(texto), **(extra or {})}
        print(f"  {nombre}.json: {len(texto) / 1024:.0f} KB", flush=True)

    ole, km_ole, g_ole = lineas("oleoductos")
    escribir("oleoductos", ole, len(ole["features"]), {"km_total": round(km_ole)})
    pol, km_pol, _ = lineas("poliductos")
    escribir("poliductos", pol, len(pol["features"]), {"km_total": round(km_pol)})

    pulsos = pulsos_desde(g_ole, (CUSHING["lon"], CUSHING["lat"]), redondeo=REDONDEO_NODO_CRUDO)
    if pulsos:
        escribir("pulsos", pulsos, len(pulsos["trayectos"]),
                 {"nota": "ILUSTRATIVO: km por la red desde Cushing; no es flujo medido"})

    t = bajar("terminales")
    t = t.rename(columns={"Company": "empresa", "Site": "sitio", "City": "ciudad",
                          "State": "estado", "PADD": "padd"})
    escribir("terminales", fc(t, ["empresa", "sitio", "ciudad", "estado", "padd"]), len(t))

    p = bajar("puertos").to_crs(5070)
    p = p.set_geometry(p.geometry.representative_point()).to_crs(4326)
    p = p.rename(columns={"PORTNAME": "puerto", "RANK": "ranking", "TOTAL": "toneladas_total",
                          "IMPORTS": "toneladas_importacion", "EXPORTS": "toneladas_exportacion"})
    escribir("puertos", fc(p, ["puerto", "ranking", "toneladas_total", "toneladas_importacion",
                               "toneladas_exportacion"]), len(p))

    s = bajar("plays").to_crs(5070)
    s = s.set_geometry(s.geometry.simplify(TOL_PLAYS_M)).to_crs(4326)
    s = s.rename(columns={"Shale_play": "play", "Basin": "cuenca", "Lithology": "litologia"})
    escribir("plays", fc(s, ["play", "cuenca", "litologia"]), len(s))

    pl = bajar("plataformas")
    # INSTALL_DATE viene en milisegundos desde 1970 (fecha de ArcGIS)
    pl["anio_instalacion"] = gpd.pd.to_datetime(pl["INSTALL_DATE"], unit="ms", errors="coerce").dt.year
    # 18 registros traen 1899: es el marcador de fecha vacía (la primera plataforma del Golfo es
    # de 1938). Antes de 1938 se toma como sin dato.
    pl.loc[pl["anio_instalacion"] < 1938, "anio_instalacion"] = None
    pl["anio_instalacion"] = pl["anio_instalacion"].astype("Int64").astype(object).where(
        pl["anio_instalacion"].notna(), None)
    pl["retirada"] = pl["REMOVAL_DATE"].notna()
    pl["id"] = pl["COMPLEX_ID_NUM"]
    escribir("plataformas", fc(pl, ["id", "anio_instalacion", "retirada"]), len(pl))

    escribir("cushing", {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"nombre": CUSHING["nombre"]},
        "geometry": mapping(Point(CUSHING["lon"], CUSHING["lat"]))}]}, 1)

    escribir("series", series())
    (SALIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("listo", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
