# %% [markdown]
# # NB02_Gold — Pulso Energético de EE. UU. (Petróleo y Gas)
#
# **Autor:** German Cardenas · Capa **Gold** del pipeline medallón en Microsoft Fabric.
#
# Reconstruye completo, en cada corrida, el modelo estrella sobre `silver_observaciones`:
#
# | Dimensiones | Hechos |
# |---|---|
# | `dim_fecha`, `dim_serie`, `dim_region` | `fact_precios_diarios`, `fact_precios_mensuales`, `fact_precio_surtidor_semanal`, `fact_inventarios_semanales`, `fact_almacenamiento_gas_semanal`, `fact_consumo_gas_mensual`, `fact_produccion_mensual`, `fact_ultimo_dato` |
#
# Antes de escribir valida: ninguna tabla vacía, claves únicas, integridad referencial y
# conciliación de conteos Silver vs Gold. **Si algo falla, lanza una excepción y no escribe nada**
# (el pipeline marca la corrida como fallida y dispara el aviso).
#
# Además calcula la **frescura** por dataset y el **análisis de rezago** WTI → producción
# (descriptivo, no causal) y los deja como tablas y como JSON en `Files/gold/`.
#
# Generado desde `fabric/notebooks/src/NB02_Gold.py` con `python scripts/generar_fabric.py`.

# %% [parameters]
fecha_referencia = ""  # "YYYY-MM-DD" para reprocesos; vacío = hoy (UTC)

# %% [helpers]
# Funciones puras (sin Spark): se prueban localmente con pytest.
import math
from datetime import date, timedelta

import pandas as pd

ADVERTENCIA = (
    "Análisis descriptivo, no causal: mide cuánto se parecen los movimientos del precio "
    "y de la producción con distintos desfasajes. No prueba que el precio cause la producción."
)


def fin_de_periodo(periodo: date, frecuencia: str) -> date:
    if frecuencia == "monthly":
        siguiente = date(periodo.year + (periodo.month == 12), periodo.month % 12 + 1, 1)
        return siguiente - timedelta(days=1)
    return periodo


def estado_frescura(ultimo: date | None, frecuencia: str, umbral: int, hoy: date) -> dict:
    if ultimo is None:
        return {"fin_periodo": None, "dias_atraso": None, "estado": "sin_datos"}
    fin = fin_de_periodo(ultimo, frecuencia)
    atraso = (hoy - fin).days
    return {"fin_periodo": fin, "dias_atraso": atraso,
            "estado": "al_dia" if atraso <= umbral else "atrasado"}


def _serie_mensual(df: pd.DataFrame, excluir) -> pd.Series:
    s = df.set_index("periodo")["valor"].sort_index()
    s.index = pd.DatetimeIndex(s.index).to_period("M")
    s = s[~s.index.duplicated(keep="first")]
    s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
    if excluir:
        desde, hasta = pd.Period(excluir[0], "M"), pd.Period(excluir[1], "M")
        s[(s.index >= desde) & (s.index <= hasta)] = float("nan")
    return s


def correlacion_cruzada(precio: pd.DataFrame, produccion: pd.DataFrame, max_rezago: int = 12,
                        min_obs: int = 24, excluir=None) -> pd.DataFrame:
    """corr_k = corr(ΔWTI_t, ΔProducción_{t+k}) con variaciones % mensuales."""
    dp = _serie_mensual(precio, excluir).pct_change(fill_method=None)
    dq = _serie_mensual(produccion, excluir).pct_change(fill_method=None)
    idx = dp.index.union(dq.index)
    dp, dq = dp.reindex(idx), dq.reindex(idx)
    filas = []
    for k in range(max_rezago + 1):
        par = pd.DataFrame({"x": dp, "y": dq.shift(-k)}).dropna()
        n = len(par)
        r = float(par["x"].corr(par["y"])) if n >= min_obs else math.nan
        filas.append({"rezago_meses": k, "correlacion": r, "n_obs": n,
                      "desde": str(par.index.min()) if n else None,
                      "hasta": str(par.index.max()) if n else None})
    return pd.DataFrame(filas)


def resumen_rezago(tabla: pd.DataFrame) -> dict:
    validas = tabla.dropna(subset=["correlacion"])
    detalle = [{"rezago_meses": int(f.rezago_meses),
                "correlacion": None if pd.isna(f.correlacion) else round(float(f.correlacion), 4),
                "n_obs": int(f.n_obs)} for f in tabla.itertuples()]
    if validas.empty:
        return {"rezago_optimo_meses": None, "correlacion": None, "n_obs": 0, "detalle": detalle}
    m = validas.loc[validas["correlacion"].idxmax()]
    return {"rezago_optimo_meses": int(m["rezago_meses"]),
            "correlacion": round(float(m["correlacion"]), 4), "n_obs": int(m["n_obs"]),
            "desde": m["desde"], "hasta": m["hasta"],
            "metodo": "Pearson entre variación % mensual del WTI (t) y de la producción (t+k)",
            "criterio": "rezago con la mayor correlación (con signo)", "detalle": detalle}


# %%
import json
from datetime import UTC, datetime

from pyspark.sql import Window
from pyspark.sql import functions as F

RAIZ = "/lakehouse/default/Files"
with open(f"{RAIZ}/config/eia_datasets.json", encoding="utf-8") as fh:
    CFG = json.load(fh)
DATASETS = {d["nombre"]: d for d in CFG["datasets"]}
HOY = date.fromisoformat(fecha_referencia) if fecha_referencia else datetime.now(UTC).date()
TABLAS_HECHOS = [
    "fact_precios_diarios", "fact_precios_mensuales", "fact_precio_surtidor_semanal",
    "fact_inventarios_semanales", "fact_almacenamiento_gas_semanal",
    "fact_consumo_gas_mensual", "fact_produccion_mensual",
]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# %% Silver enriquecido
cfg_ds = spark.createDataFrame(
    [(n, d["tabla_gold"], d["sector"], d["categoria"]) for n, d in DATASETS.items()],
    "dataset STRING, tabla_gold STRING, sector STRING, categoria STRING",
)
sufijo = F.create_map(F.lit("daily"), F.lit("D"), F.lit("weekly"), F.lit("W"),
                      F.lit("monthly"), F.lit("M"))
s = (
    spark.table("silver_observaciones")
    .join(F.broadcast(cfg_ds), "dataset")
    .withColumn("serie_key", F.concat_ws("_", "serie", F.element_at(sufijo, F.col("frecuencia"))))
    .withColumn("region_key", F.when((F.col("duoarea").isNull()) | (F.col("duoarea") == ""),
                                     F.lit("NA")).otherwise(F.col("duoarea")))
    .withColumn("fecha_key", F.date_format("periodo", "yyyyMMdd").cast("int"))
    .cache()
)

# %% Hechos
tablas = {}
for t in TABLAS_HECHOS:
    tablas[t] = (s.filter(F.col("tabla_gold") == t)
                 .select("fecha_key", F.col("periodo").alias("fecha"), "serie_key",
                         "region_key", "valor"))

w_ult = Window.partitionBy("serie_key").orderBy(F.col("periodo").desc())
tablas["fact_ultimo_dato"] = (
    s.withColumn("_rn", F.row_number().over(w_ult))
    .withColumn("fecha_anterior", F.lead("periodo").over(w_ult))
    .withColumn("valor_anterior", F.lead("valor").over(w_ult))
    .filter("_rn = 1")
    .select("fecha_key", F.col("periodo").alias("fecha"), "serie_key", "region_key", "valor",
            "fecha_anterior", "valor_anterior",
            (F.col("valor") - F.col("valor_anterior")).alias("variacion_abs"),
            F.when(F.col("valor_anterior").isNull() | (F.col("valor_anterior") == 0), None)
            .otherwise((F.col("valor") - F.col("valor_anterior")) / F.col("valor_anterior"))
            .alias("variacion_pct"))
)

# %% Dimensiones
nombres = spark.createDataFrame(
    [(n, cod, nom, i) for n, d in DATASETS.items() for i, (cod, nom) in enumerate(d["series"].items())],
    "dataset STRING, serie STRING, nombre STRING, orden INT",
)
w_meta = Window.partitionBy("serie_key").orderBy(F.col("periodo").desc())
tablas["dim_serie"] = (
    s.withColumn("_rn", F.row_number().over(w_meta)).filter("_rn = 1")
    .join(F.broadcast(nombres), ["dataset", "serie"], "left")
    .select("serie_key", F.col("serie").alias("serie_eia"),
            F.coalesce("nombre", "descripcion").alias("nombre"),
            F.col("descripcion").alias("descripcion_eia"), "unidad", "frecuencia", "dataset",
            "sector", "categoria", "tabla_gold", "region_key",
            F.coalesce("orden", F.lit(99)).alias("orden"))
)

regiones = spark.createDataFrame(
    [(k, v["nombre"], v["tipo"]) for k, v in CFG["regiones"].items()],
    "region_key STRING, nombre_cfg STRING, tipo_cfg STRING",
)
tablas["dim_region"] = (
    s.groupBy("region_key").agg(F.first("area_nombre", ignorenulls=True).alias("area_nombre"))
    .join(F.broadcast(regiones), "region_key", "left")
    .select("region_key",
            F.coalesce("nombre_cfg",
                       F.when(F.col("area_nombre") != "NA", F.col("area_nombre")),
                       F.col("region_key")).alias("nombre"),
            F.coalesce("tipo_cfg", F.lit("otro")).alias("tipo"))
)

dia_iso = ((F.dayofweek("fecha") + 5) % 7) + 1  # Spark: 1=domingo -> ISO: 1=lunes
tablas["dim_fecha"] = (
    s.agg(F.min("periodo").alias("desde"), F.max("periodo").alias("hasta"))
    .select(F.explode(F.sequence("desde", "hasta", F.expr("INTERVAL 1 DAY"))).alias("fecha"))
    .select(
        F.date_format("fecha", "yyyyMMdd").cast("int").alias("fecha_key"),
        "fecha",
        F.year("fecha").cast("smallint").alias("anio"),
        F.quarter("fecha").cast("tinyint").alias("trimestre"),
        F.month("fecha").cast("tinyint").alias("mes"),
        F.element_at(F.array(*[F.lit(m) for m in MESES]), F.month("fecha")).alias("nombre_mes"),
        F.date_format("fecha", "yyyy-MM").alias("anio_mes"),
        F.weekofyear("fecha").cast("tinyint").alias("semana_iso"),
        dia_iso.cast("tinyint").alias("dia_semana"),
        F.element_at(F.array(*[F.lit(d) for d in DIAS]), dia_iso).alias("nombre_dia"),
        (dia_iso >= 6).alias("es_fin_de_semana"),
    )
)
for df in tablas.values():
    df.cache()

# %% Validaciones (antes de escribir)
errores = []
claves = {"dim_fecha": ["fecha_key"], "dim_serie": ["serie_key"], "dim_region": ["region_key"],
          "fact_ultimo_dato": ["serie_key"]}
conteos = {n: df.count() for n, df in tablas.items()}
for nombre, df in tablas.items():
    if conteos[nombre] == 0:
        errores.append(f"{nombre}: tabla vacía")
        continue
    clave = claves.get(nombre, ["fecha_key", "serie_key"])
    dup = df.groupBy(*clave).count().filter("count > 1").count()
    if dup:
        errores.append(f"{nombre}: {dup} claves duplicadas en {clave}")
    if nombre.startswith("fact_"):
        for col, dim in (("fecha_key", "dim_fecha"), ("serie_key", "dim_serie"),
                         ("region_key", "dim_region")):
            huerfanos = df.join(tablas[dim].select(col), col, "left_anti").count()
            if huerfanos:
                errores.append(f"{nombre}: {huerfanos} filas sin match en {dim}.{col}")

conteo_silver = {r["tabla_gold"]: r["count"] for r in s.groupBy("tabla_gold").count().collect()}
for t in TABLAS_HECHOS:
    if conteo_silver.get(t, 0) != conteos[t]:
        errores.append(f"Conciliación {t}: Silver={conteo_silver.get(t, 0)} Gold={conteos[t]}")
series_silver = s.select("serie_key").distinct().count()
if conteos["fact_ultimo_dato"] != series_silver:
    errores.append(f"Conciliación fact_ultimo_dato: Silver={series_silver} "
                   f"Gold={conteos['fact_ultimo_dato']}")

if errores:
    raise RuntimeError("Validaciones de Gold fallidas:\n- " + "\n- ".join(errores))
print("Validaciones OK:", json.dumps(conteos, indent=2))

# %% Escritura (reconstrucción completa)
for nombre, df in tablas.items():
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(nombre))

# %% Frescura
maximos = {r["dataset"]: (r["max_p"], r["filas"]) for r in
           s.groupBy("dataset").agg(F.max("periodo").alias("max_p"),
                                     F.count("*").alias("filas")).collect()}
filas_fr = []
for n, d in DATASETS.items():
    ultimo, filas = maximos.get(n, (None, 0))
    umbral = CFG["umbrales_frescura_dias"][d["frecuencia"]]
    filas_fr.append({"dataset": n, "sector": d["sector"], "categoria": d["categoria"],
                     "frecuencia": d["frecuencia"], "ultimo_periodo": ultimo,
                     "umbral_dias": umbral, "filas_silver": filas, "calculado_al": HOY,
                     **estado_frescura(ultimo, d["frecuencia"], umbral, HOY)})
COLS_FR = ["dataset", "sector", "categoria", "frecuencia", "ultimo_periodo", "fin_periodo",
           "dias_atraso", "umbral_dias", "estado", "filas_silver", "calculado_al"]
frescura = spark.createDataFrame(
    [tuple(f[c] for c in COLS_FR) for f in filas_fr],
    "dataset STRING, sector STRING, categoria STRING, frecuencia STRING, ultimo_periodo DATE, "
    "fin_periodo DATE, dias_atraso INT, umbral_dias INT, estado STRING, filas_silver BIGINT, "
    "calculado_al DATE",
)
(frescura.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable("frescura"))
notebookutils.fs.put(
    "Files/gold/frescura.json",
    json.dumps({"calculado_al": HOY.isoformat(), "datasets": filas_fr},
               ensure_ascii=False, indent=2, default=str),
    True,
)
display(frescura)

# %% Análisis de rezago (dos escenarios)
rez = CFG["rezago"]


def _serie(dataset: str, serie: str) -> pd.DataFrame:
    return (spark.table("silver_observaciones")
            .filter((F.col("dataset") == dataset) & (F.col("serie") == serie))
            .select("periodo", "valor").toPandas())


precio = _serie(rez["precio"]["dataset"], rez["precio"]["serie"])
prod = _serie(rez["produccion"]["dataset"], rez["produccion"]["serie"])
tablas_rez, escenarios = [], []
for esc in rez["escenarios"]:
    t = correlacion_cruzada(precio, prod, rez["max_meses"], rez["min_observaciones"],
                            esc.get("excluir"))
    tablas_rez.append(t.assign(escenario=esc["id"]))
    escenarios.append({"id": esc["id"], "etiqueta": esc["etiqueta"],
                       "excluir": esc.get("excluir"), **resumen_rezago(t)})
(spark.createDataFrame(pd.concat(tablas_rez, ignore_index=True))
 .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable("analisis_rezago"))
analisis = {"serie_precio": f"{rez['precio']['serie']}_M",
            "serie_produccion": f"{rez['produccion']['serie']}_M",
            "calculado_al": HOY.isoformat(), "advertencia": ADVERTENCIA, "escenarios": escenarios}
notebookutils.fs.put("Files/gold/analisis_rezago.json",
                     json.dumps(analisis, ensure_ascii=False, indent=2, default=str), True)
for e in escenarios:
    print(f"{e['etiqueta']}: rezago óptimo {e['rezago_optimo_meses']} meses "
          f"(r={e['correlacion']}, n={e['n_obs']})")
print(ADVERTENCIA)

# %% Resumen
resumen = {"calculado_al": HOY.isoformat(), "conteos": conteos, "validaciones": "ok"}
notebookutils.fs.put("Files/gold/resumen.json", json.dumps(resumen, indent=2), True)
notebookutils.notebook.exit(json.dumps(resumen))
