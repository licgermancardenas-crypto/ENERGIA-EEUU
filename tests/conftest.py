"""Fixtures compartidas: settings sobre una carpeta temporal y un cliente EIA falso."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from eia_pulso.api.client import ResultadoConsulta
from eia_pulso.config import load_settings
from eia_pulso.periodos import a_fecha_inicio

HOY = date(2026, 11, 25)


@pytest.fixture
def settings(tmp_path):
    return load_settings(data_dir=tmp_path / "data")


def fila_api(serie: str, periodo: str, valor, duoarea: str = "NUS") -> dict:
    """Fila con la forma exacta que devuelve la API v2 de la EIA."""
    return {
        "period": periodo,
        "duoarea": duoarea,
        "area-name": "NA",
        "product": "X",
        "product-name": "Producto",
        "process": "P",
        "process-name": "Proceso",
        "series": serie,
        "series-description": f"Descripción {serie}",
        "value": None if valor is None else str(valor),
        "units": "$/BBL",
    }


def periodos(frecuencia: str, desde: date, hasta: date) -> list[str]:
    if frecuencia == "monthly":
        return [p.strftime("%Y-%m") for p in pd.period_range(desde, hasta, freq="M")]
    paso = "B" if frecuencia == "daily" else "W-FRI"
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(desde, hasta, freq=paso)]


class ClienteFalso:
    """Genera datos sintéticos para cada serie configurada, respetando el `inicio` pedido."""

    def __init__(self, settings, hasta: date = HOY, valor=lambda serie, i: 50.0 + i % 7,
                 ajustes: dict | None = None):
        self.settings = settings
        self.hasta = hasta
        self.valor = valor
        self.ajustes = ajustes or {}  # {(serie, periodo): valor} para simular revisiones
        self.llamadas: list[dict] = []

    def fetch_data(self, ruta, frecuencia, inicio=None, facetas=None, fin=None):
        self.llamadas.append({"ruta": ruta, "frecuencia": frecuencia, "inicio": inicio})
        series = (facetas or {}).get("series", [])
        filas = []
        for serie in series:
            for i, p in enumerate(periodos(frecuencia, a_fecha_inicio(inicio), self.hasta)):
                v = self.ajustes.get((serie, p), self.valor(serie, i))
                filas.append(fila_api(serie, p, v))
        return ResultadoConsulta(filas, len(filas), 1, f"https://fake/{ruta}/data/",
                                 {"frequency": frecuencia, "start": inicio, "facets": facetas})


@pytest.fixture
def cliente_falso(settings):
    return ClienteFalso(settings)


def dias_atras(n: int) -> str:
    return (HOY - timedelta(days=n)).isoformat()
