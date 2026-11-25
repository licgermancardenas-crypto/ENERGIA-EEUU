"""Frescura por dataset: último dato, días de atraso (desde el fin del período) y estado."""

from __future__ import annotations

from datetime import date

import pandas as pd

from eia_pulso.config import Settings
from eia_pulso.periodos import fin_de_periodo

COLUMNAS = [
    "dataset", "sector", "categoria", "frecuencia", "ultimo_periodo", "fin_periodo",
    "dias_atraso", "umbral_dias", "estado", "filas_silver", "calculado_al",
]


def calcular_frescura(silver: pd.DataFrame, settings: Settings, hoy: date) -> pd.DataFrame:
    filas = []
    for nombre, ds in settings.datasets.items():
        sub = silver[silver["dataset"] == nombre]
        umbral = settings.umbrales_frescura_dias[ds.frecuencia]
        if sub.empty:
            ultimo = fin = None
            atraso = None
            estado = "sin_datos"
        else:
            ultimo = sub["periodo"].max().date()
            fin = fin_de_periodo(ultimo, ds.frecuencia)
            atraso = (hoy - fin).days
            estado = "al_dia" if atraso <= umbral else "atrasado"
        filas.append({
            "dataset": nombre, "sector": ds.sector, "categoria": ds.categoria,
            "frecuencia": ds.frecuencia, "ultimo_periodo": ultimo, "fin_periodo": fin,
            "dias_atraso": atraso, "umbral_dias": umbral, "estado": estado,
            "filas_silver": len(sub), "calculado_al": hoy,
        })
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df["dias_atraso"] = df["dias_atraso"].astype("Int64")
    return df
