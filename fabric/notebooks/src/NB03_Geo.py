# %% [markdown]
# # NB03_Geo — Pulso Energético de EE. UU. (capa geoespacial)
#
# **Autor:** Germán Cárdenas · Red de gas natural: gasoductos, Henry Hub, hubs, GNL, centrales
# a gas y flujos interestatales por estado.
#
# No duplica lógica: instala el paquete `eia_pulso` desde el repositorio y corre las **mismas
# funciones** que el pipeline local (`src/eia_pulso/geo`): Bronze (capas + API de la EIA, con
# manifiesto y vintage) → Silver (GeoParquet) → Gold (métricas por estado, alcance del Henry Hub,
# proximidad, geometría liviana). Al final escribe las tablas `geo_*` y `frescura_geo` en el
# Lakehouse (Delta, modo overwrite).
#
# - Todo queda en `Files/geo/` (`bronze_geo/`, `silver_geo/`, `gold/geo/`).
# - La key de la EIA se lee de `Files/config/eia_config.json` y **nunca se imprime**.
# - Si la API de la EIA no responde, Bronze API se saltea con un aviso: flujos y centrales quedan
#   como tablas vacías y el informe las muestra como "No disponible".
# - Metodología, fuentes y vintage: `docs/geoespacial.md` del repositorio.
#
# Generado desde `fabric/notebooks/src/NB03_Geo.py` con `python scripts/generar_fabric.py`.

# %% [parameters]
repo = "https://github.com/licgermancardenas-crypto/ENERGIA-EEUU"
ref = "main"           # rama o commit del repositorio a instalar
saltear_api = False    # True: no consulta la API de la EIA (solo capas estáticas)

# %%
# Instala el paquete del proyecto con el extra geoespacial (geopandas, shapely, pyproj, pyogrio)
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet",
                       f"eia-pulso[geo] @ git+{repo}@{ref}"])

# %%
# Configuración: pipeline.yaml y la tabla editable de conexiones del Henry Hub, desde el repo
import json
import os
from pathlib import Path

import requests

BASE = Path("/lakehouse/default/Files")
DATA = BASE / "geo"
CONF = BASE / "config" / "geo"
CONF.mkdir(parents=True, exist_ok=True)
raw = repo.replace("github.com", "raw.githubusercontent.com") + f"/{ref}"
for nombre in ("pipeline.yaml", "henry_hub_conexiones.csv"):
    r = requests.get(f"{raw}/config/{nombre}", timeout=60)
    r.raise_for_status()
    (CONF / nombre).write_bytes(r.content)
os.environ["EIA_PULSO_CONEXIONES_HH"] = str(CONF / "henry_hub_conexiones.csv")
clave = json.loads((BASE / "config" / "eia_config.json").read_text(encoding="utf-8"))
os.environ["EIA_API_KEY"] = clave["api_key"]  # no se imprime
print("Configuración lista en", CONF)

# %%
# Bronze -> Silver -> Gold con las mismas funciones del pipeline local
import logging

from eia_pulso.api.client import EIAApiError, EIAClient
from eia_pulso.config import get_api_key, load_settings
from eia_pulso.geo.bronze import bronze_api, bronze_capas
from eia_pulso.geo.config import load_geo
from eia_pulso.geo.gold import run_gold
from eia_pulso.geo.silver import run_silver

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
settings = load_settings(CONF / "pipeline.yaml", data_dir=DATA)
cfg = load_geo(CONF / "pipeline.yaml", data_dir=DATA)

print({k: v.name for k, v in bronze_capas(cfg).items()})
if not saltear_api:
    try:
        cliente = EIAClient(get_api_key(), settings.api_base, settings.tamanio_pagina,
                            settings.max_reintentos, settings.backoff_base_s, settings.timeout_s)
        print({k: v.name for k, v in bronze_api(cfg, settings, cliente).items()})
    except EIAApiError as e:
        print("Aviso: la API de la EIA no respondió; flujos y centrales quedan no disponibles.")
        print(str(e)[:200])
run_silver(cfg)
resultado = run_gold(cfg)
print(json.dumps(resultado["validacion"], ensure_ascii=False, indent=2))

# %%
# Escribe las tablas Gold en el Lakehouse (Delta). Las vacías se crean con su esquema.
from pyspark.sql import types as T

TIPOS = {"str": T.StringType(), "object": T.StringType(), "string": T.StringType(),
         "float64": T.DoubleType(), "int64": T.LongType(), "bool": T.BooleanType()}


def a_spark(df):
    esquema = T.StructType([T.StructField(c, TIPOS.get(str(t), T.StringType()), True)
                            for c, t in df.dtypes.items()])
    filas = df.astype(object).where(df.notna(), None).values.tolist()
    return spark.createDataFrame(filas, esquema)  # noqa: F821 - `spark` lo provee Fabric


for nombre, df in resultado["tablas"].items():
    (a_spark(df).write.mode("overwrite").option("overwriteSchema", "true")
     .format("delta").saveAsTable(nombre))
    print(f"{nombre}: {len(df)} filas")
