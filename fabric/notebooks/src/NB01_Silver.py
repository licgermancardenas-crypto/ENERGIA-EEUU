# %% [markdown]
# # NB01_Silver — Pulso Energético de EE. UU. (Petróleo y Gas)
#
# **Autor:** Germán Cárdenas · Capa **Silver** del pipeline medallón en Microsoft Fabric.
#
# Qué hace:
# 1. Lee los JSON nuevos de `Files/bronze/<dataset>/` (los deja el pipeline de Data Factory).
# 2. Tipa y valida: descarta filas sin fecha, sin valor, sin clave completa, de series no
#    configuradas, con valor <= 0 y días todavía incompletos (series diarias).
# 3. **MERGE insert-only** en la tabla Delta `silver_observaciones` (particionada por año y mes):
#    solo agrega claves naturales `(dataset, serie, periodo)` que no existen.
# 4. Si llega un valor distinto para una clave ya cargada (revisión de la EIA), **no lo pisa**:
#    lo registra con MERGE en `silver_auditoria_revisiones` (una vez por valor nuevo).
# 5. Registra cada archivo procesado en `bronze_manifest` (metadatos: dataset, ruta, filas...).
# 6. Regenera `Files/config/eia_plan.json` con la fecha de inicio incremental de cada dataset
#    para la próxima corrida del pipeline (último período en Silver menos la ventana de relectura).
#
# Generado desde `fabric/notebooks/src/NB01_Silver.py` con `python scripts/generar_fabric.py`.

# %% [parameters]
dias_minimos_diarios = -1  # -1 = usar el valor de eia_datasets.json
reprocesar_todo = False  # True = vuelve a leer todos los Bronze (idempotente igual)
fecha_referencia = ""  # "YYYY-MM-DD" para reprocesos; vacío = hoy (UTC)

# %% [helpers]
# Funciones puras (sin Spark): se prueban localmente con pytest.
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

CAMPOS_API = [
    "period", "series", "value", "units", "series-description", "duoarea", "area-name",
    "product", "product-name", "process", "process-name",
]


def parsear_bronze(texto: str) -> list[dict]:
    """Extrae las filas de un archivo Bronze, sea cual sea su forma:
    - respuesta cruda de la API ({"response": {"data": [...]}}), una o varias páginas
      concatenadas, en arreglo o una por línea (salida de la actividad Copy con paginación);
    - formato del pipeline local ({"metadata": {...}, "data": [...]});
    - filas sueltas ya aplanadas.
    """
    decoder = json.JSONDecoder()
    filas: list[dict] = []

    def visitar(obj) -> None:
        if isinstance(obj, list):
            for x in obj:
                visitar(x)
        elif isinstance(obj, dict):
            if isinstance(obj.get("response"), dict):
                filas.extend(obj["response"].get("data") or [])
            elif "metadata" in obj and isinstance(obj.get("data"), list):
                filas.extend(obj["data"])
            elif "period" in obj:
                filas.append(obj)

    i, n = 0, len(texto)
    while i < n:
        while i < n and texto[i] in " \t\r\n,﻿":
            i += 1
        if i >= n:
            break
        obj, i = decoder.raw_decode(texto, i)
        visitar(obj)
    return filas


def ts_desde_nombre(nombre: str) -> str:
    """'<dataset>__20261125T030501123456Z.json' -> '2026-11-25T03:05:01.123456Z'."""
    m = re.search(r"__(\d{8}T\d{6})(\d*)Z", nombre)
    if not m:
        return ""
    base = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").strftime("%Y-%m-%dT%H:%M:%S")
    return f"{base}.{m.group(2)}Z" if m.group(2) else f"{base}Z"


def a_fecha(texto: str) -> date:
    partes = [int(p) for p in str(texto).split("-")]
    return date(partes[0], partes[1] if len(partes) > 1 else 1, partes[2] if len(partes) > 2 else 1)


def inicio_incremental(inicio_cfg: str, max_periodo, frecuencia: str, ventana_dias: int) -> str:
    """Primera vez: inicio configurado. Después: último período - ventana (nunca antes del inicio)."""
    desde = a_fecha(inicio_cfg)
    if max_periodo is not None:
        desde = max(desde, max_periodo - timedelta(days=int(ventana_dias)))
    return desde.strftime("%Y-%m" if frecuencia == "monthly" else "%Y-%m-%d")


def construir_query(ds: dict, inicio: str, length: int = 5000) -> str:
    """Query string (URL-encoded, SIN api_key ni offset) para la actividad Copy."""
    params = [("frequency", ds["frecuencia"]), ("data[0]", "value"), ("start", inicio)]
    params += [("facets[series][]", s) for s in ds["series"]]
    params += [
        ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
        ("sort[1][column]", "series"), ("sort[1][direction]", "asc"),
        ("length", str(length)),
    ]
    return urlencode(params)


def construir_plan(cfg: dict, max_periodos: dict) -> list[dict]:
    plan = []
    for ds in cfg["datasets"]:
        ini = inicio_incremental(ds["inicio"], max_periodos.get(ds["nombre"]), ds["frecuencia"],
                                 cfg["ventana_relectura_dias"][ds["frecuencia"]])
        plan.append({"nombre": ds["nombre"], "ruta": ds["ruta"], "frecuencia": ds["frecuencia"],
                     "inicio": ini, "query": construir_query(ds, ini)})
    return plan


# %%
import os
from datetime import UTC

from delta.tables import DeltaTable
from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

RAIZ = "/lakehouse/default/Files"  # Lakehouse adjuntado como predeterminado
with open(f"{RAIZ}/config/eia_datasets.json", encoding="utf-8") as fh:
    CFG = json.load(fh)
DATASETS = {d["nombre"]: d for d in CFG["datasets"]}
N_DIAS = int(CFG["dias_minimos_diarios"] if dias_minimos_diarios < 0 else dias_minimos_diarios)
HOY = date.fromisoformat(fecha_referencia) if fecha_referencia else datetime.now(UTC).date()
AHORA = datetime.now(UTC).replace(tzinfo=None)
CLAVE = ["dataset", "serie", "periodo"]
print(f"Datasets: {len(DATASETS)} · hoy={HOY} · días mínimos (diarias)={N_DIAS}")

# %%
spark.sql("""
CREATE TABLE IF NOT EXISTS silver_observaciones (
  dataset STRING, serie STRING, periodo DATE, valor DOUBLE, frecuencia STRING,
  unidad STRING, descripcion STRING, duoarea STRING, area_nombre STRING,
  producto STRING, producto_nombre STRING, proceso STRING, proceso_nombre STRING,
  archivo_bronze STRING, extraido_utc STRING, cargado_utc TIMESTAMP, anio INT, mes INT
) USING DELTA PARTITIONED BY (anio, mes)
""")
spark.sql("""
CREATE TABLE IF NOT EXISTS silver_auditoria_revisiones (
  dataset STRING, serie STRING, periodo DATE, valor_cargado DOUBLE, valor_nuevo DOUBLE,
  archivo_bronze STRING, extraido_utc STRING, detectado_utc TIMESTAMP
) USING DELTA
""")
spark.sql("""
CREATE TABLE IF NOT EXISTS bronze_manifest (
  archivo STRING, dataset STRING, ruta STRING, frecuencia STRING, filas INT,
  tamanio_bytes BIGINT, extraido_utc STRING, procesado_utc TIMESTAMP
) USING DELTA
""")

# %% Bronze pendientes de procesar
procesados = set()
if not reprocesar_todo:
    procesados = {r.archivo for r in spark.table("bronze_manifest").select("archivo").collect()}

registros, manifest = [], []
for nombre, ds in DATASETS.items():
    carpeta = f"{RAIZ}/bronze/{nombre}"
    if not os.path.isdir(carpeta):
        print(f"  (sin carpeta Bronze para {nombre})")
        continue
    for archivo in sorted(os.listdir(carpeta)):
        clave_archivo = f"{nombre}/{archivo}"
        if not archivo.endswith(".json") or clave_archivo in procesados:
            continue
        ruta_local = f"{carpeta}/{archivo}"
        with open(ruta_local, encoding="utf-8") as fh:
            filas = parsear_bronze(fh.read())
        ts = ts_desde_nombre(archivo)
        for f in filas:
            registros.append(
                tuple(None if f.get(c) is None else str(f.get(c)) for c in CAMPOS_API)
                + (nombre, clave_archivo, ts)
            )
        manifest.append((clave_archivo, nombre, ds["ruta"], ds["frecuencia"], len(filas),
                         os.path.getsize(ruta_local), ts, AHORA))
print(f"Archivos Bronze nuevos: {len(manifest)} · filas: {len(registros)}")

# %% Tipado y validación
esquema_crudo = T.StructType(
    [T.StructField(c, T.StringType()) for c in CAMPOS_API]
    + [T.StructField(c, T.StringType()) for c in ("dataset", "archivo_bronze", "extraido_utc")]
)
crudo = spark.createDataFrame(registros, esquema_crudo)

cfg_ds = spark.createDataFrame(
    [(n, d["frecuencia"], bool(d.get("solo_positivos", True))) for n, d in DATASETS.items()],
    "dataset STRING, frecuencia STRING, solo_positivos BOOLEAN",
)
cfg_series = spark.createDataFrame(
    [(n, s, True) for n, d in DATASETS.items() for s in d["series"]],
    "dataset STRING, serie STRING, en_config BOOLEAN",
)

periodo_txt = F.when(F.col("frecuencia") == "monthly", F.concat(F.col("period"), F.lit("-01")))
periodo_txt = periodo_txt.otherwise(F.col("period"))
tipado = (
    crudo.join(F.broadcast(cfg_ds), "dataset")
    .withColumn("periodo_txt", periodo_txt)
    .withColumn("periodo", F.to_date(F.expr("try_to_timestamp(periodo_txt, 'yyyy-MM-dd')")))
    .withColumn("valor", F.expr("try_cast(value AS DOUBLE)"))
    .withColumn("serie", F.trim(F.col("series")))
    .join(F.broadcast(cfg_series), ["dataset", "serie"], "left")
)
limite_diario = F.date_sub(F.lit(HOY), N_DIAS)
motivo = (
    F.when(F.col("periodo").isNull(), "sin_fecha")
    .when(F.col("valor").isNull() | F.isnan("valor") | (F.abs("valor") == float("inf")),
          "sin_valor")
    .when(F.col("serie").isNull() | (F.col("serie") == ""), "clave_incompleta")
    .when(F.col("en_config").isNull(), "serie_no_configurada")
    .when(F.col("solo_positivos") & (F.col("valor") <= 0), "valor_no_positivo")
    .when((F.col("frecuencia") == "daily") & (F.col("periodo") > limite_diario), "dia_incompleto")
)
tipado = tipado.withColumn("motivo_descarte", motivo).cache()

descartes = (tipado.filter(F.col("motivo_descarte").isNotNull())
             .groupBy("dataset", "motivo_descarte").count().orderBy("dataset"))
display(descartes)

validas = tipado.filter(F.col("motivo_descarte").isNull()).select(
    "dataset", "serie", "periodo", "valor", "frecuencia",
    F.col("units").alias("unidad"),
    F.col("`series-description`").alias("descripcion"),
    "duoarea",
    F.col("`area-name`").alias("area_nombre"),
    F.col("product").alias("producto"),
    F.col("`product-name`").alias("producto_nombre"),
    F.col("process").alias("proceso"),
    F.col("`process-name`").alias("proceso_nombre"),
    "archivo_bronze", "extraido_utc",
)

# Dedup del lote: por clave, el primer valor extraído (orden cronológico de Bronze)
w = Window.partitionBy(*CLAVE).orderBy("extraido_utc", "archivo_bronze")
lote = validas.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")

# %% Auditoría de revisiones (antes del MERGE de Silver)
silver_ref = spark.table("silver_observaciones").select(*CLAVE, F.col("valor").alias("valor_cargado"))
nuevas_ref = (lote.join(silver_ref.select(*CLAVE), CLAVE, "left_anti")
              .select(*CLAVE, F.col("valor").alias("valor_cargado")))
referencia = silver_ref.unionByName(nuevas_ref)

candidatos = (validas.groupBy(*CLAVE, "valor")
              .agg(F.min(F.struct("extraido_utc", "archivo_bronze")).alias("p"))
              .select(*CLAVE, "valor", "p.extraido_utc", "p.archivo_bronze"))
tolerancia = F.greatest(F.lit(1e-12), F.abs(F.col("valor_cargado")) * F.lit(1e-9))
revisiones = (
    candidatos.join(referencia, CLAVE)
    .filter(F.abs(F.col("valor") - F.col("valor_cargado")) > tolerancia)
    .select(*CLAVE, "valor_cargado", F.col("valor").alias("valor_nuevo"),
            "archivo_bronze", "extraido_utc", F.lit(AHORA).cast("timestamp").alias("detectado_utc"))
    .dropDuplicates([*CLAVE, "valor_nuevo"])
)
tabla_rev = DeltaTable.forName(spark, "silver_auditoria_revisiones")
(tabla_rev.alias("t")
 .merge(revisiones.alias("s"),
        "t.dataset = s.dataset AND t.serie = s.serie AND t.periodo = s.periodo "
        "AND t.valor_nuevo = s.valor_nuevo")
 .whenNotMatchedInsertAll()
 .execute())
rev_nuevas = int(tabla_rev.history(1).select("operationMetrics").first()[0]
                 .get("numTargetRowsInserted", 0))
print(f"Revisiones nuevas auditadas: {rev_nuevas}")

# %% MERGE insert-only en Silver
lote_final = lote.select(
    *lote.columns,
    F.lit(AHORA).cast("timestamp").alias("cargado_utc"),
    F.year("periodo").alias("anio"),
    F.month("periodo").alias("mes"),
)
tabla_silver = DeltaTable.forName(spark, "silver_observaciones")
(tabla_silver.alias("t")
 .merge(lote_final.alias("s"),
        "t.anio = s.anio AND t.mes = s.mes AND t.dataset = s.dataset "
        "AND t.serie = s.serie AND t.periodo = s.periodo")
 .whenNotMatchedInsertAll()   # nunca UPDATE: las revisiones van a la auditoría
 .execute())
insertadas = int(tabla_silver.history(1).select("operationMetrics").first()[0]
                 .get("numTargetRowsInserted", 0))
print(f"Filas nuevas en Silver: {insertadas}")

# %% Manifest de Bronze (después del MERGE: si algo falla, el archivo se reprocesa)
if manifest:
    esquema_manifest = ("archivo STRING, dataset STRING, ruta STRING, frecuencia STRING, "
                        "filas INT, tamanio_bytes BIGINT, extraido_utc STRING, "
                        "procesado_utc TIMESTAMP")
    (spark.createDataFrame(manifest, esquema_manifest)
     .write.format("delta").mode("append").saveAsTable("bronze_manifest"))

# %% Plan incremental para la próxima corrida del pipeline
maximos = {r["dataset"]: r["max_p"] for r in spark.table("silver_observaciones")
           .groupBy("dataset").agg(F.max("periodo").alias("max_p")).collect()}
plan = construir_plan(CFG, maximos)
notebookutils.fs.put("Files/config/eia_plan.json",
                     json.dumps(plan, ensure_ascii=False, indent=2), True)
display(spark.createDataFrame([(p["nombre"], p["inicio"]) for p in plan], "dataset STRING, proximo_inicio STRING"))

# %% Resumen
totales = {r["dataset"]: r["count"] for r in
           spark.table("silver_observaciones").groupBy("dataset").count().collect()}
resumen = {"archivos_bronze_nuevos": len(manifest), "filas_leidas": len(registros),
           "insertadas": insertadas, "revisiones_nuevas": rev_nuevas, "totales_silver": totales}
print(json.dumps(resumen, ensure_ascii=False, indent=2))
notebookutils.notebook.exit(json.dumps(resumen))
