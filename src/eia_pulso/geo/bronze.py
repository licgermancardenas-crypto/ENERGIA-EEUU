"""Bronze geoespacial: descarga cruda de capas (ArcGIS REST, Census) y de la API de la EIA.

Cada descarga queda en data/bronze_geo/<capa>/<capa>__<AAAAMMDDTHHMMSS>.<ext> con un manifiesto
JSON al lado (URL, registros, SHA-256, vintage, fecha). Nunca se pisa una descarga anterior.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from eia_pulso.api.client import EIAClient
from eia_pulso.config import RAIZ_REPO, Settings
from eia_pulso.geo.config import Capa, GeoConfig

log = logging.getLogger(__name__)


SALTO, CR, LF = bytes([10]), chr(13), chr(10)  # separadores del Summary File


class GeoBronzeError(RuntimeError):
    """Una capa no se pudo descargar o vino incompleta."""


def _sello() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S")


def _guardar(dir_: Path, nombre: str, ext: str, contenido: bytes, meta: dict[str, Any]) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    sello = _sello()
    destino = dir_ / f"{nombre}__{sello}.{ext}"
    destino.write_bytes(contenido)
    meta = {**meta, "archivo": destino.name, "sha256": hashlib.sha256(contenido).hexdigest(),
            "bytes": len(contenido), "descargado_utc": sello}
    (dir_ / f"{nombre}__{sello}.manifest.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def descargar_arcgis(capa: Capa, sesion: requests.Session | None = None,
                     timeout: float = 90) -> tuple[bytes, int]:
    """Recorre la capa con resultOffset y devuelve un FeatureCollection GeoJSON (WGS84)."""
    s = sesion or requests.Session()
    url = capa.url.rstrip("/")
    total = s.get(f"{url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
                  timeout=timeout).json()
    if "error" in total:
        raise GeoBronzeError(f"{capa.nombre}: {total['error'].get('message')}")
    n_total = int(total["count"])
    meta = s.get(url, params={"f": "json"}, timeout=timeout).json()
    pagina = int(meta.get("maxRecordCount") or 1000)
    features: list[dict[str, Any]] = []
    while len(features) < n_total:
        r = s.get(f"{url}/query", params={
            "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
            "resultOffset": len(features), "resultRecordCount": pagina,
            "orderByFields": meta.get("objectIdField") or "OBJECTID"}, timeout=timeout)
        r.raise_for_status()
        lote = r.json().get("features", [])
        if not lote:
            break
        features.extend(lote)
    if len(features) != n_total:
        raise GeoBronzeError(f"{capa.nombre}: {len(features)} de {n_total} registros")
    fc = {"type": "FeatureCollection", "features": features}
    return json.dumps(fc, ensure_ascii=False).encode("utf-8"), n_total


def bronze_capas(cfg: GeoConfig, solo: list[str] | None = None) -> dict[str, Path]:
    salidas: dict[str, Path] = {}
    for nombre, capa in cfg.capas.items():
        if solo and nombre not in solo:
            continue
        base = {"capa": nombre, "tipo": capa.tipo, "origen": capa.origen,
                "vintage": capa.vintage, "url": capa.url}
        if capa.archivo:  # archivo descargado (Census); si no está en disco, se baja de `url`
            src = RAIZ_REPO / capa.archivo
            if src.exists():
                contenido = src.read_bytes()
            elif capa.url:
                r = requests.get(capa.url, timeout=120)
                r.raise_for_status()
                contenido = r.content
            else:
                raise GeoBronzeError(f"{nombre}: falta {capa.archivo}")
            salidas[nombre] = _guardar(cfg.bronze_dir / nombre, nombre, src.suffix.lstrip("."),
                                       contenido, {**base, "registros": None})
        else:
            contenido, n = descargar_arcgis(capa)
            salidas[nombre] = _guardar(cfg.bronze_dir / nombre, nombre, "geojson", contenido,
                                       {**base, "registros": n})
        log.info("Bronze geo %s -> %s", nombre, salidas[nombre].name)
    return salidas


def bronze_api(cfg: GeoConfig, settings: Settings, cliente: EIAClient) -> dict[str, Path]:
    """Flujos interestatales (anual) y centrales a gas (último mes publicado)."""
    salidas: dict[str, Path] = {}
    f = cfg.flujos
    res = cliente.fetch_data(f["ruta"], f["frecuencia"], inicio=str(f["inicio"]),
                             facetas={"process": list(f["procesos"])})
    salidas["flujos"] = _guardar(
        cfg.bronze_dir / "flujos", "flujos",
        "json", json.dumps(res.filas, ensure_ascii=False).encode("utf-8"),
        {"capa": "flujos", "origen": "EIA API v2 " + f["ruta"], "registros": len(res.filas),
         "parametros": res.parametros, "vintage": max((r["period"] for r in res.filas),
                                                      default=None)})
    c = cfg.centrales
    # último mes disponible: se consulta el metadato de la ruta
    meta = cliente._get(f"{settings.api_base}/{c['ruta']}", [])["response"]
    ultimo = meta["endPeriod"]
    res = cliente.fetch_data(
        c["ruta"], c["frecuencia"], inicio=ultimo, fin=ultimo,
        facetas={"energy_source_code": list(c["combustibles"])},
        columnas=("nameplate-capacity-mw", "latitude", "longitude", "county"),
        orden=("plantid", "generatorid"))
    salidas["centrales"] = _guardar(
        cfg.bronze_dir / "centrales", "centrales", "json",
        json.dumps(res.filas, ensure_ascii=False).encode("utf-8"),
        {"capa": "centrales", "origen": "EIA API v2 " + c["ruta"] + " (EIA-860M)",
         "registros": len(res.filas), "parametros": res.parametros, "vintage": ultimo})
    return salidas


def bronze_acs(cfg: GeoConfig, sesion: requests.Session | None = None) -> Path:
    """ACS House Heating Fuel: baja el Summary File por tabla en streaming y guarda solo los
    condados (GEO_ID 0500000US...). El SHA-256 del manifiesto es el del archivo completo."""
    acs = cfg.acs
    if not acs:
        raise GeoBronzeError("Falta la sección geo.acs en la configuración")
    cols = ["GEO_ID", *acs["columnas"]]
    h, filas, encabezado = hashlib.sha256(), [], None
    with (sesion or requests.Session()).get(acs["url"], stream=True, timeout=300) as r:
        r.raise_for_status()
        resto = b""
        for bloque in r.iter_content(chunk_size=1 << 20):
            h.update(bloque)
            partes = (resto + bloque).split(SALTO)
            resto = partes.pop()
            for linea in partes:
                texto = linea.decode("utf-8").rstrip(CR)
                if encabezado is None:
                    encabezado = texto.split("|")
                elif texto.startswith("0500000US"):
                    filas.append(texto)
        if resto.decode("utf-8").startswith("0500000US"):
            filas.append(resto.decode("utf-8").rstrip(CR))
    faltan = [c for c in cols if c not in (encabezado or [])]
    if faltan:
        raise GeoBronzeError(f"ACS: faltan columnas {faltan} en el Summary File")
    contenido = (LF.join(["|".join(encabezado), *filas]) + LF).encode("utf-8")
    destino = _guardar(cfg.bronze_dir / "acs", "acs", "dat", contenido, {
        "capa": "acs", "origen": f"U.S. Census Bureau, ACS 5 años {acs['anio']}, tabla "
        f"{acs['tabla']} (House Heating Fuel), Summary File", "url": acs["url"],
        "registros": len(filas), "vintage": acs["anio"]})
    man = destino.with_name(destino.name.replace(".dat", ".manifest.json"))
    m = json.loads(man.read_text(encoding="utf-8"))
    m["sha256_archivo_completo"] = h.hexdigest()
    man.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def ultimo(cfg: GeoConfig, capa: str) -> tuple[Path, dict[str, Any]]:
    """Última descarga Bronze de una capa y su manifiesto."""
    mans = sorted((cfg.bronze_dir / capa).glob(f"{capa}__*.manifest.json"))
    if not mans:
        raise GeoBronzeError(f"No hay Bronze para {capa}: corré `eia-pulso geo --bronze`")
    m = json.loads(mans[-1].read_text(encoding="utf-8"))
    return cfg.bronze_dir / capa / m["archivo"], m

