"""Configuración de la capa geoespacial (sección `geo` de config/pipeline.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from eia_pulso.config import CONFIG_DEFAULT, RAIZ_REPO, ConfigError

CONEXIONES_HH = RAIZ_REPO / "config" / "henry_hub_conexiones.csv"


@dataclass(frozen=True)
class Capa:
    nombre: str
    tipo: str            # lineas | puntos | poligonos
    origen: str
    vintage: str
    url: str | None = None
    archivo: str | None = None


@dataclass(frozen=True)
class GeoConfig:
    crs_calculo: int
    crs_visual: int
    tolerancia_m: float
    decimales: int
    umbral_proximidad_km: float
    estados_excluidos: tuple[str, ...]
    capas: dict[str, Capa]
    flujos: dict[str, Any]
    centrales: dict[str, Any]
    fuente_conexiones_hh: str
    data_dir: Path
    acs: dict[str, Any] | None = None
    umbral_dependencia: float = 0.5
    refinacion: dict[str, Any] | None = None

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze_geo"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver_geo"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold" / "geo"


def load_geo(config_path: str | Path | None = None,
             data_dir: str | Path | None = None) -> GeoConfig:
    raw = yaml.safe_load(Path(config_path or CONFIG_DEFAULT).read_text(encoding="utf-8"))
    g = raw.get("geo")
    if not g:
        raise ConfigError("Falta la sección 'geo' en config/pipeline.yaml")
    capas = {}
    for nombre, c in g["capas"].items():
        if not (c.get("url") or c.get("archivo")):
            raise ConfigError(f"La capa {nombre} necesita 'url' o 'archivo'")
        capas[nombre] = Capa(nombre, c["tipo"], c["origen"], str(c["vintage"]), c.get("url"),
                             c.get("archivo"))
    if data_dir is None:
        data_dir = RAIZ_REPO / raw.get("rutas", {}).get("data_dir", "data")
    return GeoConfig(
        crs_calculo=int(g["crs_calculo"]), crs_visual=int(g["crs_visual"]),
        tolerancia_m=float(g["tolerancia_simplificacion_m"]),
        decimales=int(g["decimales_coordenadas"]),
        umbral_proximidad_km=float(g["umbral_proximidad_km"]),
        estados_excluidos=tuple(g.get("estados_excluidos", [])),
        capas=capas, flujos=g["flujos"], centrales=g["centrales"],
        fuente_conexiones_hh=g["henry_hub"]["fuente_conexiones"], data_dir=Path(data_dir),
        acs=g.get("acs"), umbral_dependencia=float(g.get("umbral_dependencia_gas_red", 0.5)),
        refinacion=g.get("capacidad_refinacion"),
    )
