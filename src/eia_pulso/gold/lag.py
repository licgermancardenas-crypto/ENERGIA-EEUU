"""Métrica propia: correlación cruzada entre la variación mensual del WTI y la variación
mensual de la producción de crudo, para rezagos de 0 a 12 meses.

corr_k = corr( ΔWTI_t , ΔProducción_{t+k} )

Es una medida DESCRIPTIVA de co-movimiento, no una prueba de causalidad: la producción
depende también de tecnología, costos, coberturas, clima, regulación, etc.
"""

from __future__ import annotations

import math

import pandas as pd

ADVERTENCIA = (
    "Análisis descriptivo, no causal: mide cuánto se parecen los movimientos del precio "
    "y de la producción con distintos desfasajes. No prueba que el precio cause la producción."
)


def _serie_mensual(df: pd.DataFrame) -> pd.Series:
    s = df.set_index("periodo")["valor"].sort_index()
    s.index = pd.DatetimeIndex(s.index).to_period("M")
    s = s[~s.index.duplicated(keep="first")]
    rango = pd.period_range(s.index.min(), s.index.max(), freq="M")
    return s.reindex(rango)


def correlacion_cruzada(
    precio: pd.DataFrame, produccion: pd.DataFrame, max_rezago: int = 12, min_obs: int = 24
) -> pd.DataFrame:
    """Recibe DataFrames con columnas periodo/valor. Devuelve una fila por rezago."""
    dp = _serie_mensual(precio).pct_change(fill_method=None)
    dq = _serie_mensual(produccion).pct_change(fill_method=None)
    idx = dp.index.union(dq.index)
    dp, dq = dp.reindex(idx), dq.reindex(idx)
    filas = []
    for k in range(max_rezago + 1):
        par = pd.DataFrame({"x": dp, "y": dq.shift(-k)}).dropna()
        n = len(par)
        r = float(par["x"].corr(par["y"])) if n >= min_obs else math.nan
        filas.append({
            "rezago_meses": k,
            "correlacion": r,
            "n_obs": n,
            "desde": str(par.index.min()) if n else None,
            "hasta": str(par.index.max()) if n else None,
        })
    return pd.DataFrame(filas)


def resumen_rezago(tabla: pd.DataFrame) -> dict:
    validas = tabla.dropna(subset=["correlacion"])
    if validas.empty:
        return {"rezago_optimo_meses": None, "correlacion": None, "n_obs": 0,
                "advertencia": ADVERTENCIA, "detalle": []}
    mejor = validas.loc[validas["correlacion"].idxmax()]
    return {
        "rezago_optimo_meses": int(mejor["rezago_meses"]),
        "correlacion": round(float(mejor["correlacion"]), 4),
        "n_obs": int(mejor["n_obs"]),
        "desde": mejor["desde"],
        "hasta": mejor["hasta"],
        "metodo": "Pearson entre variación % mensual del WTI (t) y de la producción (t+k)",
        "criterio": "rezago con la mayor correlación (con signo)",
        "advertencia": ADVERTENCIA,
        "detalle": [
            {"rezago_meses": int(f.rezago_meses),
             "correlacion": None if pd.isna(f.correlacion) else round(float(f.correlacion), 4),
             "n_obs": int(f.n_obs)}
            for f in tabla.itertuples()
        ],
    }
