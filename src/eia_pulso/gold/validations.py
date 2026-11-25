"""Validaciones de Gold: no vacías, claves únicas, integridad referencial y conciliación."""

from __future__ import annotations

import pandas as pd

CLAVES = {
    "dim_fecha": ["fecha_key"],
    "dim_serie": ["serie_key"],
    "dim_region": ["region_key"],
    "fact_ultimo_dato": ["serie_key"],
}
CLAVE_HECHO = ["fecha_key", "serie_key"]
RELACIONES = {"fecha_key": "dim_fecha", "serie_key": "dim_serie", "region_key": "dim_region"}


class GoldValidationError(RuntimeError):
    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("Validaciones de Gold fallidas:\n- " + "\n- ".join(errores))


def validar_gold(
    tablas: dict[str, pd.DataFrame], conteos_silver: dict[str, int], series_silver: int
) -> list[str]:
    """Devuelve la lista de errores (vacía si todo está bien)."""
    errores: list[str] = []
    for nombre, df in tablas.items():
        if df.empty:
            errores.append(f"{nombre}: tabla vacía")
            continue
        clave = CLAVES.get(nombre, CLAVE_HECHO if nombre.startswith("fact_") else None)
        if clave:
            dup = int(df.duplicated(clave).sum())
            if dup:
                errores.append(f"{nombre}: {dup} claves duplicadas en {clave}")
        if nombre.startswith("fact_"):
            for col, dim in RELACIONES.items():
                if col in df.columns and dim in tablas:
                    huerfanos = ~df[col].isin(tablas[dim][col])
                    if huerfanos.any():
                        errores.append(
                            f"{nombre}: {int(huerfanos.sum())} filas sin match en {dim}.{col}"
                        )
    for tabla, esperado in conteos_silver.items():
        real = len(tablas.get(tabla, []))
        if real != esperado:
            errores.append(f"Conciliación {tabla}: Silver={esperado} Gold={real}")
    if "fact_ultimo_dato" in tablas and len(tablas["fact_ultimo_dato"]) != series_silver:
        errores.append(
            f"Conciliación fact_ultimo_dato: series en Silver={series_silver} "
            f"Gold={len(tablas['fact_ultimo_dato'])}"
        )
    return errores
