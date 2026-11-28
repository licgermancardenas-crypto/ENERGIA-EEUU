"""Refinerías de petróleo: ubicación (capa de la EIA), capacidad por refinería (Refinery Capacity
Report, EIA-820) y totales por estado (API v2 petroleum/pnp/cap1).

- La capa de puntos trae empresa, sitio, estado y coordenadas (vintage 1/1/2024).
- El Excel refcapYY.xlsx trae la capacidad operable de destilación atmosférica de cada
  refinería en barriles por día calendario (vintage 1/1 del año YY): es el dato más nuevo.
- Se unen por estado + sitio (+ empresa si hay más de una refinería en el mismo sitio). Las
  refinerías del Excel que no aparecen en la capa quedan sin coordenadas: no se inventan.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

PRODUCTO_OPERABLE = "TOTAL OPERABLE CAPACITY"
PRODUCTO_OPERANDO = "OPERATING CAPACITY"
PRODUCTO_OCIOSA = "IDLE CAPACITY"
PROCESOS_API = {"8D0": "capacidad_operable_bcd", "8DO": "capacidad_operando_bcd",
                "8O0": "refinerias_operables", "8OO": "refinerias_operando"}

COLS_REFINERIAS = {"refineria_id": "str", "empresa": "str", "corporacion": "str", "sitio": "str",
                   "estado_key": "str", "padd": "int64", "capacidad_operable_bcd": "float64",
                   "capacidad_operando_bcd": "float64", "capacidad_ociosa_bcd": "float64",
                   "con_ubicacion": "bool", "lon": "float64", "lat": "float64"}


def _norm(s: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper()) if pd.notna(s) else ""


def silver_capacidad(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por refinería con su capacidad de destilación atmosférica (b/d calendario)."""
    cal = df[df["SUPPLY"].str.contains("calendar day", case=False, na=False)]
    claves = ["STATE_NAME", "SITE", "COMPANY_NAME", "CORPORATION", "PADD"]

    def cap(producto: str) -> pd.Series:
        return cal[cal["PRODUCT"] == producto].groupby(claves)["QUANTITY"].sum()

    out = pd.DataFrame({"capacidad_operable_bcd": cap(PRODUCTO_OPERABLE),
                        "capacidad_operando_bcd": cap(PRODUCTO_OPERANDO),
                        "capacidad_ociosa_bcd": cap(PRODUCTO_OCIOSA)}).reset_index()
    out = out.rename(columns={"STATE_NAME": "estado_nombre", "SITE": "sitio",
                              "COMPANY_NAME": "empresa", "CORPORATION": "corporacion",
                              "PADD": "padd"})
    for c in ("capacidad_operable_bcd", "capacidad_operando_bcd", "capacidad_ociosa_bcd"):
        out[c] = out[c].fillna(0.0).astype("float64")
    return out


def unir(capacidad: pd.DataFrame, puntos: pd.DataFrame, estados: pd.DataFrame
         ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Asigna coordenadas a cada refinería del Excel. `puntos` necesita estado, sitio, empresa,
    lon y lat; `estados` mapea nombre -> estado_key."""
    clave_estado = {_norm(n): k
                    for n, k in zip(estados["nombre"], estados["estado_key"], strict=True)}
    pts = puntos.assign(_e=puntos["estado"].map(_norm), _s=puntos["sitio"].map(_norm),
                        _c=puntos["empresa"].map(_norm))
    usados: set[int] = set()
    filas = []
    for r in capacidad.itertuples():
        cand = pts[(pts["_e"] == _norm(r.estado_nombre)) & (pts["_s"] == _norm(r.sitio))]
        cand = cand[~cand.index.isin(usados)]
        if len(cand) > 1:  # más de una refinería en el mismo sitio: desempata la empresa
            emp = _norm(r.empresa)
            mejor = cand[cand["_c"].map(lambda c, e=emp: c[:6] == e[:6])]
            cand = mejor if len(mejor) else cand
        p = cand.iloc[0] if len(cand) else None
        if p is not None:
            usados.add(p.name)
        ek = clave_estado.get(_norm(r.estado_nombre), "??")
        filas.append({
            "refineria_id": f"{ek}-{_norm(r.sitio)}-{_norm(r.empresa)[:12]}",
            "empresa": r.empresa, "corporacion": r.corporacion, "sitio": str(r.sitio).title(),
            "estado_key": clave_estado.get(_norm(r.estado_nombre)), "padd": int(r.padd),
            "capacidad_operable_bcd": r.capacidad_operable_bcd,
            "capacidad_operando_bcd": r.capacidad_operando_bcd,
            "capacidad_ociosa_bcd": r.capacidad_ociosa_bcd,
            "con_ubicacion": p is not None,
            "lon": float(p["lon"]) if p is not None else float("nan"),
            "lat": float(p["lat"]) if p is not None else float("nan")})
    out = pd.DataFrame(filas)
    val = {"refinerias_informe": len(capacidad), "con_ubicacion": int(out["con_ubicacion"].sum()),
           "sin_ubicacion": out.loc[~out["con_ubicacion"], "refineria_id"].tolist(),
           "puntos_capa": len(puntos), "puntos_sin_refineria_en_informe": len(puntos) - len(usados),
           "sin_estado": out.loc[out["estado_key"].isna(), "refineria_id"].tolist()}
    return out.astype({c: t for c, t in COLS_REFINERIAS.items() if c in out}), val


def estado_refinacion(filas: list[dict[str, Any]], estados: set[str]) -> pd.DataFrame:
    """Totales por estado del último año de la API (capacidad en barriles/día calendario)."""
    cols = ["estado_key", "anio", *PROCESOS_API.values()]
    if not filas:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(filas)
    df = df[df["process"].isin(PROCESOS_API) & df["units"].isin(["B/CD", "COUNT"])
            & df["duoarea"].str.match(r"^S[A-Z]{2}$")]
    df = df.assign(estado_key=df["duoarea"].str[1:], anio=df["period"].astype(int),
                   valor=pd.to_numeric(df["value"], errors="coerce"))
    df = df[df["estado_key"].isin(estados) & (df["anio"] == df["anio"].max())]
    p = df.pivot_table(index=["estado_key", "anio"], columns="process", values="valor",
                       aggfunc="sum").reset_index().rename(columns=PROCESOS_API)
    for c in PROCESOS_API.values():
        if c not in p:
            p[c] = 0.0
    return p[cols]


def total_nacional_api(filas: list[dict[str, Any]]) -> float | None:
    """Capacidad operable de EE. UU. (NUS) del último año: sirve para validar la suma del Excel."""
    df = pd.DataFrame(filas)
    if df.empty:
        return None
    df = df[(df["duoarea"] == "NUS") & (df["process"] == "8D0") & (df["units"] == "B/CD")]
    if df.empty:
        return None
    return float(pd.to_numeric(df.loc[df["period"] == df["period"].max(), "value"]).sum())
