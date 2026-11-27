"""Capa Gold: modelo estrella reconstruido completo en cada corrida (DuckDB + Parquet).

Se construye todo en memoria, se valida y recién entonces se reemplaza la carpeta Gold,
así una corrida fallida nunca deja un Gold a medio escribir.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from eia_pulso.config import Settings
from eia_pulso.gold.freshness import calcular_frescura
from eia_pulso.gold.lag import ADVERTENCIA, correlacion_cruzada, resumen_rezago
from eia_pulso.gold.validations import GoldValidationError, validar_gold
from eia_pulso.periodos import ahora_utc_iso, hoy_utc
from eia_pulso.silver.storage import leer_revisiones, leer_silver

log = logging.getLogger(__name__)

SUFIJO_FRECUENCIA = {"daily": "D", "weekly": "W", "monthly": "M"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
TABLAS_HECHOS = [
    "fact_precios_diarios",
    "fact_precios_mensuales",
    "fact_precio_surtidor_semanal",
    "fact_inventarios_semanales",
    "fact_almacenamiento_gas_semanal",
    "fact_consumo_gas_mensual",
    "fact_produccion_mensual",
]


@dataclass
class ResultadoGold:
    conteos: dict[str, int]
    frescura: pd.DataFrame
    rezago: dict
    directorio: Path


SUBCARPETAS_AJENAS = ("geo",)


def _preparar_silver(silver: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    df = silver[silver["dataset"].isin(list(settings.datasets))].copy()
    df["tabla_gold"] = df["dataset"].map({k: d.tabla_gold for k, d in settings.datasets.items()})
    df["serie_key"] = df["serie"] + "_" + df["frecuencia"].map(SUFIJO_FRECUENCIA)
    df["region_key"] = df["duoarea"].fillna("NA").replace("", "NA")
    return df


def construir_dim_serie(s: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    ult = s.sort_values("periodo").groupby("serie_key", as_index=False).tail(1)
    filas = []
    for r in ult.itertuples():
        ds = settings.datasets[r.dataset]
        filas.append({
            "serie_key": r.serie_key,
            "serie_eia": r.serie,
            "nombre": ds.series.get(r.serie, r.descripcion),
            "descripcion_eia": r.descripcion,
            "unidad": r.unidad,
            "frecuencia": r.frecuencia,
            "dataset": r.dataset,
            "sector": ds.sector,
            "categoria": ds.categoria,
            "tabla_gold": ds.tabla_gold,
            "region_key": r.region_key,
            "orden": list(ds.series).index(r.serie) if r.serie in ds.series else 99,
        })
    return pd.DataFrame(filas).sort_values(["sector", "dataset", "orden"]).reset_index(drop=True)


def construir_dim_region(s: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    filas = []
    for codigo in sorted(s["region_key"].unique()):
        cfg = settings.regiones.get(codigo, {})
        nombre_eia = s.loc[s["region_key"] == codigo, "area_nombre"].dropna()
        nombre_eia = nombre_eia.iloc[0] if len(nombre_eia) else codigo
        filas.append({
            "region_key": codigo,
            "nombre": cfg.get("nombre", nombre_eia if nombre_eia != "NA" else codigo),
            "tipo": cfg.get("tipo", "otro"),
        })
    return pd.DataFrame(filas)


def construir_dim_fecha(desde: pd.Timestamp, hasta: pd.Timestamp) -> pd.DataFrame:
    fechas = pd.date_range(desde.normalize(), hasta.normalize(), freq="D")
    iso = fechas.isocalendar()
    return pd.DataFrame({
        "fecha_key": (fechas.year * 10000 + fechas.month * 100 + fechas.day).astype("int32"),
        "fecha": fechas.date,
        "anio": fechas.year.astype("int16"),
        "trimestre": fechas.quarter.astype("int8"),
        "mes": fechas.month.astype("int8"),
        "nombre_mes": [MESES[m - 1] for m in fechas.month],
        "anio_mes": fechas.strftime("%Y-%m"),
        "semana_iso": iso["week"].to_numpy().astype("int8"),
        "dia_semana": (fechas.day_of_week + 1).astype("int8"),
        "nombre_dia": [DIAS[d] for d in fechas.day_of_week],
        "es_fin_de_semana": fechas.day_of_week >= 5,
    })


SQL_HECHO = """
SELECT CAST(strftime(CAST(periodo AS DATE), '%Y%m%d') AS INTEGER) AS fecha_key,
       CAST(periodo AS DATE)                         AS fecha,
       serie_key, region_key, valor
FROM silver WHERE tabla_gold = ? ORDER BY serie_key, fecha
"""

SQL_ULTIMO = """
WITH ord AS (
  SELECT serie_key, region_key, periodo, valor,
         ROW_NUMBER() OVER (PARTITION BY serie_key ORDER BY periodo DESC) AS rn,
         LEAD(periodo) OVER (PARTITION BY serie_key ORDER BY periodo DESC) AS periodo_anterior,
         LEAD(valor)   OVER (PARTITION BY serie_key ORDER BY periodo DESC) AS valor_anterior
  FROM silver)
SELECT CAST(strftime(CAST(periodo AS DATE), '%Y%m%d') AS INTEGER) AS fecha_key,
       CAST(periodo AS DATE) AS fecha, serie_key, region_key, valor,
       CAST(periodo_anterior AS DATE) AS fecha_anterior, valor_anterior,
       valor - valor_anterior AS variacion_abs,
       CASE WHEN valor_anterior IS NULL OR valor_anterior = 0 THEN NULL
            ELSE (valor - valor_anterior) / valor_anterior END AS variacion_pct
FROM ord WHERE rn = 1 ORDER BY serie_key
"""


def construir_tablas(silver: pd.DataFrame, settings: Settings) -> dict[str, pd.DataFrame]:
    s = _preparar_silver(silver, settings)
    tablas: dict[str, pd.DataFrame] = {}
    with duckdb.connect() as con:
        con.register("silver", s)
        for t in TABLAS_HECHOS:
            tablas[t] = con.execute(SQL_HECHO, [t]).df()
        tablas["fact_ultimo_dato"] = con.execute(SQL_ULTIMO).df()
    for df in tablas.values():
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    if "fecha_anterior" in tablas["fact_ultimo_dato"]:
        fa = pd.to_datetime(tablas["fact_ultimo_dato"]["fecha_anterior"])
        tablas["fact_ultimo_dato"]["fecha_anterior"] = fa.dt.date

    tablas["dim_serie"] = construir_dim_serie(s, settings) if not s.empty else pd.DataFrame()
    tablas["dim_region"] = construir_dim_region(s, settings) if not s.empty else pd.DataFrame()
    tablas["dim_fecha"] = (
        construir_dim_fecha(s["periodo"].min(), s["periodo"].max()) if not s.empty
        else pd.DataFrame()
    )
    orden = ["dim_fecha", "dim_serie", "dim_region", *TABLAS_HECHOS, "fact_ultimo_dato"]
    return {k: tablas[k] for k in orden}


def _escribir(directorio: Path, tablas: dict[str, pd.DataFrame], extras: dict[str, pd.DataFrame],
              jsons: dict[str, object]) -> None:
    (directorio / "parquet").mkdir(parents=True, exist_ok=True)
    todas = {**tablas, **extras}
    for nombre, df in todas.items():
        df.to_parquet(directorio / "parquet" / f"{nombre}.parquet", index=False)
    with duckdb.connect(str(directorio / "pulso.duckdb")) as con:
        for nombre, df in todas.items():
            con.register("tmp", df)
            con.execute(f"CREATE TABLE {nombre} AS SELECT * FROM tmp")
            con.unregister("tmp")
    for nombre, obj in jsons.items():
        (directorio / f"{nombre}.json").write_text(
            json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )


def run_gold(settings: Settings, hoy: date | None = None) -> ResultadoGold:
    hoy = hoy or hoy_utc()
    silver = leer_silver(settings.silver_dir)
    s = _preparar_silver(silver, settings)
    tablas = construir_tablas(silver, settings)

    conteos_silver = {t: int((s["tabla_gold"] == t).sum()) for t in TABLAS_HECHOS}
    errores = validar_gold(tablas, conteos_silver, series_silver=s["serie_key"].nunique())
    if errores:
        raise GoldValidationError(errores)

    frescura = calcular_frescura(silver, settings, hoy)
    (ds_p, serie_p), (ds_q, serie_q) = settings.rezago_precio, settings.rezago_produccion
    precio = silver[(silver["dataset"] == ds_p) & (silver["serie"] == serie_p)]
    prod = silver[(silver["dataset"] == ds_q) & (silver["serie"] == serie_q)]
    tablas_rezago, escenarios = [], []
    for esc in settings.rezago_escenarios:
        excluir = tuple(esc["excluir"]) if esc.get("excluir") else None
        t = correlacion_cruzada(precio, prod, settings.rezago_max_meses,
                                settings.rezago_min_obs, excluir=excluir)
        tablas_rezago.append(t.assign(escenario=esc["id"]))
        escenarios.append({"id": esc["id"], "etiqueta": esc["etiqueta"],
                           "excluir": list(excluir) if excluir else None, **resumen_rezago(t)})
    tabla_rezago = pd.concat(tablas_rezago, ignore_index=True)
    rezago = {"serie_precio": f"{serie_p}_M", "serie_produccion": f"{serie_q}_M",
              "calculado_al": hoy.isoformat(), "advertencia": ADVERTENCIA,
              "escenarios": escenarios}

    conteos = {k: len(v) for k, v in tablas.items()}
    resumen = {"generado_utc": ahora_utc_iso(), "calculado_al": hoy.isoformat(),
               "conteos": conteos, "validaciones": "ok"}
    frescura_json = {"calculado_al": hoy.isoformat(),
                     "datasets": json.loads(frescura.to_json(orient="records", date_format="iso"))}

    destino = settings.gold_dir
    tmp = destino.with_name(destino.name + "_tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    _escribir(
        tmp, tablas,
        extras={"frescura": frescura, "analisis_rezago": tabla_rezago,
                "auditoria_revisiones": leer_revisiones(settings.silver_dir)},
        jsons={"frescura": frescura_json, "analisis_rezago": rezago, "resumen": resumen},
    )
    if destino.exists():
        # la capa geoespacial (gold/geo) la escribe otro comando: se conserva
        for sub in SUBCARPETAS_AJENAS:
            if (destino / sub).exists():
                shutil.move(str(destino / sub), str(tmp / sub))
        shutil.rmtree(destino)
    tmp.rename(destino)
    log.info("Gold reconstruido en %s: %s", destino, conteos)
    return ResultadoGold(conteos, frescura, rezago, destino)
