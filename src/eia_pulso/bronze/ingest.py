"""Capa Bronze: un JSON nuevo por dataset y corrida, con metadatos. Nunca se sobrescribe."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from eia_pulso.api.client import ResultadoConsulta
from eia_pulso.config import DatasetConfig, Settings
from eia_pulso.periodos import a_fecha_inicio, formato_api, nuevo_run_id
from eia_pulso.silver.storage import max_periodo

log = logging.getLogger(__name__)


class ClienteEIA(Protocol):
    def fetch_data(
        self,
        ruta: str,
        frecuencia: str,
        inicio: str | None = None,
        facetas: dict[str, list[str]] | None = None,
        fin: str | None = None,
    ) -> ResultadoConsulta: ...


@dataclass
class ResultadoBronze:
    dataset: str
    archivo: Path
    filas: int
    inicio: str


def calcular_inicio(ds: DatasetConfig, settings: Settings, completo: bool = False) -> str:
    """Primera corrida (o --completo): desde `inicio`. Si no: último período Silver - ventana."""
    inicio_cfg = a_fecha_inicio(ds.inicio)
    ultimo = None if completo else max_periodo(settings.silver_dir, ds.nombre)
    if ultimo is None:
        desde = inicio_cfg
    else:
        ventana = settings.ventana_relectura_dias[ds.frecuencia]
        desde = max(inicio_cfg, ultimo.date() - timedelta(days=ventana))
    return formato_api(desde, ds.frecuencia)


def escribir_bronze(
    bronze_dir: Path, ds: DatasetConfig, resultado: ResultadoConsulta, run_id: str
) -> Path:
    carpeta = bronze_dir / ds.nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{ds.nombre}__{run_id}.json"
    documento = {
        "metadata": {
            "dataset": ds.nombre,
            "ruta": ds.ruta,
            "endpoint": resultado.endpoint,
            "parametros": resultado.parametros,
            "frecuencia": ds.frecuencia,
            "filas": len(resultado.filas),
            "total_api": resultado.total_api,
            "paginas": resultado.paginas,
            "advertencias": resultado.advertencias,
            "run_id": run_id,
            "extraido_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        },
        "data": resultado.filas,
    }
    # modo 'x': falla si el archivo existe -> Bronze jamás se sobrescribe
    with archivo.open("x", encoding="utf-8") as fh:
        json.dump(documento, fh, ensure_ascii=False)
    return archivo


def run_bronze(
    settings: Settings,
    cliente: ClienteEIA,
    datasets: list[str] | None = None,
    completo: bool = False,
    run_id: str | None = None,
) -> list[ResultadoBronze]:
    run_id = run_id or nuevo_run_id()
    resultados: list[ResultadoBronze] = []
    for nombre, ds in settings.datasets.items():
        if datasets and nombre not in datasets:
            continue
        inicio = calcular_inicio(ds, settings, completo)
        log.info("Bronze %s: %s desde %s", nombre, ds.ruta, inicio)
        res = cliente.fetch_data(ds.ruta, ds.frecuencia, inicio=inicio, facetas=ds.facetas)
        archivo = escribir_bronze(settings.bronze_dir, ds, res, run_id)
        resultados.append(ResultadoBronze(nombre, archivo, len(res.filas), inicio))
    return resultados
