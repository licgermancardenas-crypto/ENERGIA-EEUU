"""Carga de configuración (YAML) y de la API key (variable de entorno / .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONFIG_DEFAULT = RAIZ_REPO / "config" / "pipeline.yaml"
FRECUENCIAS = ("daily", "weekly", "monthly")


class ConfigError(RuntimeError):
    """Error de configuración (archivo inválido o key ausente)."""


@dataclass(frozen=True)
class DatasetConfig:
    nombre: str
    ruta: str
    frecuencia: str
    inicio: str
    sector: str
    categoria: str
    tabla_gold: str
    series: dict[str, str]
    solo_positivos: bool = True

    @property
    def facetas(self) -> dict[str, list[str]]:
        return {"series": list(self.series)}


@dataclass(frozen=True)
class Settings:
    api_base: str
    tamanio_pagina: int
    max_reintentos: int
    backoff_base_s: float
    timeout_s: float
    data_dir: Path
    dias_minimos_diarios: int
    ventana_relectura_dias: dict[str, int]
    umbrales_frescura_dias: dict[str, int]
    rezago_max_meses: int
    rezago_min_obs: int
    rezago_precio: tuple[str, str]
    rezago_produccion: tuple[str, str]
    rezago_escenarios: list[dict[str, Any]]
    regiones: dict[str, dict[str, str]]
    datasets: dict[str, DatasetConfig]

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold"


def _requerido(d: dict[str, Any], clave: str, contexto: str) -> Any:
    if clave not in d:
        raise ConfigError(f"Falta la clave '{clave}' en {contexto}")
    return d[clave]


def load_settings(
    config_path: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> Settings:
    path = Path(config_path) if config_path else CONFIG_DEFAULT
    if not path.exists():
        raise ConfigError(f"No existe el archivo de configuración: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    datasets: dict[str, DatasetConfig] = {}
    for nombre, d in _requerido(raw, "datasets", "la raíz").items():
        frec = _requerido(d, "frecuencia", nombre)
        if frec not in FRECUENCIAS:
            raise ConfigError(f"Frecuencia inválida '{frec}' en {nombre}")
        series = _requerido(d, "series", nombre)
        if not series:
            raise ConfigError(f"El dataset {nombre} no tiene series configuradas")
        datasets[nombre] = DatasetConfig(
            nombre=nombre,
            ruta=_requerido(d, "ruta", nombre).strip("/"),
            frecuencia=frec,
            inicio=str(_requerido(d, "inicio", nombre)),
            sector=_requerido(d, "sector", nombre),
            categoria=_requerido(d, "categoria", nombre),
            tabla_gold=_requerido(d, "tabla_gold", nombre),
            series={str(k): str(v) for k, v in series.items()},
            solo_positivos=bool(d.get("solo_positivos", True)),
        )

    api = _requerido(raw, "api", "la raíz")
    rez = _requerido(raw, "rezago", "la raíz")
    if data_dir is None:
        data_dir = RAIZ_REPO / raw.get("rutas", {}).get("data_dir", "data")

    settings = Settings(
        api_base=str(api["base_url"]).rstrip("/"),
        tamanio_pagina=int(api.get("tamanio_pagina", 5000)),
        max_reintentos=int(api.get("max_reintentos", 5)),
        backoff_base_s=float(api.get("backoff_base_s", 1.0)),
        timeout_s=float(api.get("timeout_s", 60)),
        data_dir=Path(data_dir),
        dias_minimos_diarios=int(raw.get("silver", {}).get("dias_minimos_diarios", 2)),
        ventana_relectura_dias={k: int(v) for k, v in raw["ventana_relectura_dias"].items()},
        umbrales_frescura_dias={k: int(v) for k, v in raw["umbrales_frescura_dias"].items()},
        rezago_max_meses=int(rez.get("max_meses", 12)),
        rezago_min_obs=int(rez.get("min_observaciones", 24)),
        rezago_precio=(rez["precio"]["dataset"], rez["precio"]["serie"]),
        rezago_produccion=(rez["produccion"]["dataset"], rez["produccion"]["serie"]),
        rezago_escenarios=rez.get("escenarios") or [{"id": "completo",
                                                     "etiqueta": "Historia completa"}],
        regiones=raw.get("regiones", {}),
        datasets=datasets,
    )
    for ds, _ in (settings.rezago_precio, settings.rezago_produccion):
        if ds not in datasets:
            raise ConfigError(f"El análisis de rezago referencia un dataset inexistente: {ds}")
    return settings


def get_api_key() -> str:
    """Lee EIA_API_KEY del entorno (cargando .env de la raíz si existe). Nunca la imprime."""
    load_dotenv(RAIZ_REPO / ".env", override=False)
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        raise ConfigError(
            "Falta la variable de entorno EIA_API_KEY. Copiá .env.example como .env y "
            "completá tu key (https://www.eia.gov/opendata/register.php)."
        )
    return key
