"""Prepara la geometría real de una lista curada de refinerías desde OpenStreetMap (Overpass API).

Se corre a mano, en la máquina del autor, NO desde el navegador de los visitantes:

    python scripts/preparar_refinerias_osm.py            # usa la caché si existe
    python scripts/preparar_refinerias_osm.py --refrescar  # vuelve a consultar Overpass

Respeta la política de uso de Overpass (wiki.openstreetmap.org/wiki/Overpass_API):
- User-Agent que identifica al proyecto, una consulta por vez, PAUSA_S segundos entre consultas
  y espera de 30 s si el servidor responde 429/504.
- Las respuestas crudas se guardan en data/osm/crudo/ (fuera del repo) y no se vuelven a pedir.

Salida (en el repo, servida por la web): web/public/data/refinerias-osm/<id>.json y indice.json.
Datos © colaboradores de OpenStreetMap, licencia ODbL (https://www.openstreetmap.org/copyright).
Ver docs/refineria-real.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

RAIZ = Path(__file__).resolve().parents[1]
CRUDO = RAIZ / "data" / "osm" / "crudo"
SALIDA = RAIZ / "web" / "public" / "data" / "refinerias-osm"
REFINERIAS_WEB = RAIZ / "web" / "public" / "data" / "geo" / "refinerias.json"

# ------------------------------------------------------------------ parámetros
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = ("PulsoEnergeticoEEUU-preparacion/1.0 "
              "(+https://github.com/licgermancardenas-crypto/ENERGIA-EEUU)")
PAUSA_S = 5            # entre consultas
ESPERA_429_S = 30      # si Overpass pide bajar el ritmo
RADIO_PREDIO_M = 3000  # búsqueda del predio industrial=refinery alrededor del punto de la EIA
RADIO_SIN_PREDIO_M = 3000  # si no hay predio mapeado, se toma este radio
MARGEN_M = 60          # tolerancia alrededor del contorno del predio
GENERICA_MAX_DIST_M = 500  # un área industrial genérica vale si está a menos de esto del punto
# Con radio (sin predio), estos edificios no son de la refinería: se descartan
EDIFICIOS_AJENOS = {"house", "residential", "apartments", "detached", "semidetached_house",
                    "terrace", "garage", "garages", "commercial", "retail", "church", "school",
                    "hotel", "shed", "carport", "hut", "bungalow", "dormitory"}
# Con radio, además, solo edificios industriales o grandes (en EE. UU. casi todas las casas
# están mapeadas como building=yes)
EDIFICIOS_INDUSTRIALES = {"industrial", "warehouse", "storage_tank", "manufacture", "service"}
EDIFICIO_GRANDE_M2 = 2000
PREDIO_MIN_M2 = 200_000      # más chico es un edificio mal etiquetado: se ignora
PREDIO_MAX_M2 = 20_000_000   # más grande es un polo industrial entero (p. ej. canal de Houston)
TOL_EDIFICIO_M = 2.0   # simplificación de contornos de edificios
TOL_TUBERIA_M = 4.0    # simplificación de tuberías
MAX_EDIFICIOS = 1500   # tope por archivo (se priorizan los más grandes)
MAX_TUBERIAS = 600

# Lista curada (aprobada): las 15 de mayor capacidad + 3 chicas para mostrar cobertura pobre.
# Se identifican con (estado, sitio, inicio del nombre de la empresa) de refinerias.json (EIA).
LISTA = [
    ("TX", "Port Arthur", "MOTIVA"), ("TX", "Galveston Bay", "MARATHON"),
    ("LA", "Garyville", "MARATHON"), ("TX", "Beaumont", "EXXONMOBIL"),
    ("TX", "Baytown", "EXXONMOBIL"), ("LA", "Baton Rouge", "EXXONMOBIL"),
    ("LA", "Lake Charles", "CITGO"), ("IN", "Whiting", "BP"),
    ("TX", "Port Arthur", "PREMCOR"), ("CA", "Carson", "TESORO"),
    ("MS", "Pascagoula", "CHEVRON"), ("IL", "Wood River", "WRB"),
    ("MN", "Saint Paul", "FLINT HILLS"), ("TX", "Deer Park", "DEER PARK"),
    ("KY", "Catlettsburg", "MARATHON"), ("WY", "Evanston", "SILVER EAGLE"),
    ("NV", "Ely", "FORELAND"), ("CA", "Kern", "TALLEY"),
]

# Alturas estimadas cuando OSM no trae `height` (se marcan como estimación en el JSON y en la web)
ALTURA_EST = {"chimenea": 45.0, "antorcha": 60.0, "torre": 15.0, "edificio": 8.0}
ALTURA_POR_PISO = 3.5
TANQUE_ALTO_SOBRE_DIAMETRO, TANQUE_ALTO_MAX = 0.6, 20.0
TANQUE_RADIO_NODO = 10.0  # tanque mapeado como punto: radio desconocido, se estima


# ------------------------------------------------------------------ Overpass
def consultar(q: str, cache: Path, refrescar: bool) -> dict[str, Any]:
    if cache.exists() and not refrescar:
        return json.loads(cache.read_text(encoding="utf-8"))
    for intento in range(4):
        r = requests.post(OVERPASS, data={"data": q}, headers={"User-Agent": USER_AGENT},
                          timeout=200)
        if r.status_code in (429, 502, 503, 504):
            print(f"  Overpass respondió {r.status_code}: espero {ESPERA_429_S} s", flush=True)
            time.sleep(ESPERA_429_S * (intento + 1))
            continue
        r.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text, encoding="utf-8")
        time.sleep(PAUSA_S)
        return r.json()
    raise RuntimeError("Overpass no respondió después de 4 intentos")


def q_predio(lat: float, lon: float) -> str:
    return (f"[out:json][timeout:90];"
            f'(way["industrial"="refinery"](around:{RADIO_PREDIO_M},{lat},{lon});'
            f'relation["industrial"="refinery"](around:{RADIO_PREDIO_M},{lat},{lon});'
            # respaldo: área industrial genérica (algunas refinerías no tienen industrial=refinery)
            f'way["landuse"="industrial"](around:{RADIO_PREDIO_M},{lat},{lon});'
            f'relation["landuse"="industrial"](around:{RADIO_PREDIO_M},{lat},{lon}););'
            f"out tags geom;")


def q_elementos(sur: float, oeste: float, norte: float, este: float) -> str:
    b = f"{sur},{oeste},{norte},{este}"
    return (f"[out:json][timeout:180];("
            f'nwr["man_made"="storage_tank"]({b});'
            f'nwr["man_made"="chimney"]({b});'
            f'node["man_made"="flare"]({b});'
            f'nwr["man_made"="tower"]["tower:type"~"^(cooling|flare)$"]({b});'
            f'way["man_made"="pipeline"]({b});'
            f'way["building"]({b});'
            f");out tags geom;")


# ------------------------------------------------------------------ geometría
class Local:
    """Proyección local en metros alrededor del centro (equirectangular: error < 0,1 % a 5 km)."""

    def __init__(self, lon0: float, lat0: float):
        self.lon0, self.lat0 = lon0, lat0
        self.kx = 111_320 * math.cos(math.radians(lat0))
        self.ky = 110_540

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def lonlat(self, x: float, y: float) -> tuple[float, float]:
        return (self.lon0 + x / self.kx, self.lat0 + y / self.ky)


def _anillo(geom: list[dict[str, float]], loc: Local) -> list[tuple[float, float]]:
    return [loc.xy(p["lon"], p["lat"]) for p in geom if p]


def poligono_elemento(e: dict[str, Any], loc: Local) -> Polygon | None:
    if e["type"] == "way" and e.get("geometry"):
        pts = _anillo(e["geometry"], loc)
        if len(pts) >= 4 and pts[0] == pts[-1]:
            p = Polygon(pts)
            return p if p.is_valid else p.buffer(0)
    if e["type"] == "relation":
        externos = [Polygon(_anillo(m["geometry"], loc)) for m in e.get("members", [])
                    if m.get("role") == "outer" and m.get("geometry")
                    and len(m["geometry"]) >= 4]
        externos = [p if p.is_valid else p.buffer(0) for p in externos]
        if externos:
            return unary_union(externos)
    return None


def centro_elemento(e: dict[str, Any], loc: Local) -> tuple[float, float] | None:
    if e["type"] == "node":
        return loc.xy(e["lon"], e["lat"])
    p = poligono_elemento(e, loc)
    if p is not None and not p.is_empty:
        c = p.centroid
        return (c.x, c.y)
    if e.get("geometry"):
        pts = _anillo(e["geometry"], loc)
        return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    return None


def altura_osm(tags: dict[str, str]) -> float | None:
    """`height` en metros (OSM: metros por defecto; acepta 'ft' y comillas de pies)."""
    h = tags.get("height")
    if not h:
        return None
    m = re.match(r"^\s*([\d.]+)\s*(m|ft|')?\s*$", h)
    if not m:
        return None
    v = float(m.group(1))
    return v * 0.3048 if m.group(2) in ("ft", "'") else v


def r1(v: float) -> float:
    return round(v, 1)


# ------------------------------------------------------------------ armado por refinería
def procesar(ref: dict[str, Any], refrescar: bool) -> dict[str, Any]:
    lon0, lat0 = ref["lon"], ref["lat"]
    loc = Local(lon0, lat0)
    base = CRUDO / ref["id"]
    qp = q_predio(lat0, lon0)
    pred = consultar(qp, base / f"predio_{hashlib.sha1(qp.encode()).hexdigest()[:10]}.json",
                     refrescar)

    # predio: el que contiene el punto de la EIA o, si ninguno, el más cercano
    candidatos = []
    for e in pred.get("elements", []):
        p = poligono_elemento(e, loc)
        if p is not None and not p.is_empty and PREDIO_MIN_M2 <= p.area <= PREDIO_MAX_M2:
            es_ref = e.get("tags", {}).get("industrial") == "refinery"
            candidatos.append((not es_ref, p.distance(Point(0, 0)), -p.area, e, p))
    # primero las etiquetadas como refinería; dentro de cada grupo, la que contiene el punto
    # (distancia 0) y, si ninguna, la más cercana; una industrial genérica solo si la contiene
    candidatos = [c for c in candidatos if not c[0] or c[1] <= GENERICA_MAX_DIST_M]
    candidatos.sort(key=lambda c: (c[0], c[1] > 0, c[1], c[2]))
    predio = candidatos[0][4] if candidatos else None
    predio_osm = (f"{candidatos[0][3]['type']}/{candidatos[0][3]['id']}" if candidatos else None)
    zona = (predio.buffer(MARGEN_M) if predio is not None
            else Point(0, 0).buffer(RADIO_SIN_PREDIO_M))
    minx, miny, maxx, maxy = zona.bounds
    oeste, sur = loc.lonlat(minx, miny)
    este, norte = loc.lonlat(maxx, maxy)
    q = q_elementos(sur, oeste, norte, este)
    huella = hashlib.sha1(q.encode()).hexdigest()[:10]  # la caché cambia si cambia el área
    elems = consultar(q, base / f"elementos_{huella}.json", refrescar)

    tanques, chimeneas, antorchas, torres, edificios, tuberias = [], [], [], [], [], []
    vistos: set[str] = set()
    for e in elems.get("elements", []):
        t = e.get("tags", {})
        clave = f"{e['type']}/{e['id']}"
        if clave in vistos:
            continue
        vistos.add(clave)
        mm = t.get("man_made")
        if mm == "pipeline":
            pts = _anillo(e.get("geometry", []), loc)
            if len(pts) < 2:
                continue
            ln = LineString(pts).intersection(zona)
            if ln.is_empty:
                continue
            for parte in getattr(ln, "geoms", [ln]):
                s = parte.simplify(TOL_TUBERIA_M)
                if s.length > 15:
                    tuberias.append([[r1(x), r1(y)] for x, y in s.coords])
            continue
        c = centro_elemento(e, loc)
        if c is None or not zona.contains(Point(c)):
            continue
        h = altura_osm(t)
        if mm == "storage_tank" or t.get("building") == "storage_tank":
            p = poligono_elemento(e, loc)
            if p is not None and p.area > 4:
                radio, radio_est = math.sqrt(p.area / math.pi), False
            else:
                radio, radio_est = TANQUE_RADIO_NODO, True
            alto = h if h else min(TANQUE_ALTO_MAX, TANQUE_ALTO_SOBRE_DIAMETRO * 2 * radio)
            tanques.append([r1(c[0]), r1(c[1]), r1(radio), r1(alto), int(h is None),
                            int(radio_est), t.get("content", "")])
        elif mm == "chimney":
            chimeneas.append([r1(c[0]), r1(c[1]), r1(h or ALTURA_EST["chimenea"]),
                              int(h is None)])
        elif mm == "flare" or (mm == "tower" and t.get("tower:type") == "flare"):
            antorchas.append([r1(c[0]), r1(c[1]), r1(h or ALTURA_EST["antorcha"]), int(h is None)])
        elif mm == "tower":
            torres.append([r1(c[0]), r1(c[1]), r1(h or ALTURA_EST["torre"]), int(h is None),
                           t.get("tower:type", "")])
        elif "building" in t:
            if predio is None and t["building"] in EDIFICIOS_AJENOS:
                continue
            p = poligono_elemento(e, loc)
            if p is None or p.is_empty or p.area < 15:
                continue
            if (predio is None and t["building"] not in EDIFICIOS_INDUSTRIALES
                    and p.area < EDIFICIO_GRANDE_M2):
                continue
            niveles = t.get("building:levels")
            if h:
                alto, est = h, 0
            elif niveles and niveles.isdigit():
                alto, est = int(niveles) * ALTURA_POR_PISO, 1
            else:
                alto, est = ALTURA_EST["edificio"], 1
            s = p.simplify(TOL_EDIFICIO_M)
            geoms = getattr(s, "geoms", [s])
            for g in geoms:
                if g.area >= 15:
                    anillo = list(g.exterior.coords)[:-1]
                    edificios.append({"p": [[r1(x), r1(y)] for x, y in anillo],
                                      "h": r1(alto), "e": est, "a": g.area})
    edificios.sort(key=lambda b: -b["a"])
    edificios = edificios[:MAX_EDIFICIOS]
    for b in edificios:
        b.pop("a")
    tuberias = sorted(tuberias, key=lambda t: -len(t))[:MAX_TUBERIAS]

    cobertura = {"tanques": len(tanques), "chimeneas": len(chimeneas),
                 "antorchas": len(antorchas), "torres": len(torres),
                 "edificios": len(edificios), "tuberias": len(tuberias)}
    estructuras = len(tanques) + len(chimeneas) + len(antorchas) + len(torres)
    nivel = "buena" if estructuras >= 40 else "parcial" if estructuras >= 8 else "pobre"
    predio_local = None
    if predio is not None:
        mayor = max(getattr(predio, "geoms", [predio]), key=lambda g: g.area)
        predio_local = [[r1(x), r1(y)] for x, y in mayor.simplify(5).exterior.coords]
    return {
        "id": ref["id"], "empresa": ref["empresa"], "sitio": ref["sitio"], "estado": ref["estado"],
        "bcd": ref["bcd"], "centro": [lon0, lat0],
        "extraido": date.today().isoformat(),
        "fuente_geometria": "OpenStreetMap vía Overpass API (overpass-api.de)",
        "licencia": ("ODbL 1.0 · © colaboradores de OpenStreetMap · "
                     "https://www.openstreetmap.org/copyright"),
        "predio_osm": predio_osm,
        "radio_busqueda_m": None if predio is not None else RADIO_SIN_PREDIO_M,
        "predio": predio_local, "cobertura": cobertura, "nivel_cobertura": nivel,
        "tanques": tanques, "chimeneas": chimeneas, "antorchas": antorchas, "torres": torres,
        "edificios": edificios, "tuberias": tuberias,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refrescar", action="store_true", help="Volver a consultar Overpass")
    args = ap.parse_args()
    eia = json.loads(REFINERIAS_WEB.read_text(encoding="utf-8"))
    anio = eia["anio"]
    SALIDA.mkdir(parents=True, exist_ok=True)
    indice = []
    for estado, sitio, empresa in LISTA:
        ref = next((r for r in eia["refinerias"] if r["estado"] == estado
                    and r["sitio"].lower() == sitio.lower()
                    and r["empresa"].startswith(empresa)), None)
        if ref is None or ref["lon"] is None:
            print(f"  ! no está en refinerias.json: {estado} {sitio} {empresa}")
            continue
        print(f"- {estado} {sitio} ({ref['empresa']})", flush=True)
        out = procesar(ref, args.refrescar)
        out["anio_capacidad"] = anio
        texto = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        (SALIDA / f"{ref['id']}.json").write_text(texto, encoding="utf-8")
        kb = len(texto) / 1024
        print(f"  {out['nivel_cobertura']}: {out['cobertura']} · {kb:.0f} KB", flush=True)
        indice.append({k: out[k] for k in ("id", "empresa", "sitio", "estado", "bcd", "cobertura",
                                            "nivel_cobertura", "extraido")})
    (SALIDA / "indice.json").write_text(json.dumps(
        {"anio_capacidad": anio, "licencia": "ODbL 1.0 · © colaboradores de OpenStreetMap",
         "refinerias": indice}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
