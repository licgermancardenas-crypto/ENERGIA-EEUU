# %% [markdown]
# # NB00_Bronze_Alternativo — Pulso Energético de EE. UU.
#
# **Autor:** German Cardenas · **Plan B** para la capa Bronze.
#
# El camino principal es la actividad **Copy** del pipeline (conexión REST anónima). Usá este
# notebook solo si la paginación de Copy no se comporta como se espera en tu capacidad de Fabric:
# reemplazá el `ForEach` por este notebook y el resto del pipeline queda igual.
#
# Lee la key de `Files/config/eia_config.json` (nunca la imprime) y el plan incremental de
# `Files/config/eia_plan.json`. Pagina con `length/offset`, reintenta con backoff exponencial y
# escribe un JSON nuevo por dataset en `Files/bronze/<dataset>/` con metadatos
# (ruta, parámetros sin key, filas). Nunca sobrescribe.

# %% [parameters]
max_reintentos = 5
backoff_base_s = 2.0

# %%
import json
import os
import random
import time
from datetime import UTC, datetime

import requests

RAIZ = "/lakehouse/default/Files"
BASE = "https://api.eia.gov/v2"
with open(f"{RAIZ}/config/eia_config.json", encoding="utf-8") as fh:
    _KEY = json.load(fh)["api_key"].strip()
with open(f"{RAIZ}/config/eia_plan.json", encoding="utf-8") as fh:
    PLAN = json.load(fh)


def _get(url: str) -> dict:
    ultimo = ""
    for intento in range(max_reintentos + 1):
        try:
            r = requests.get(f"{url}&api_key={_KEY}", timeout=60)
            if r.status_code == 200:
                cuerpo = r.json()
                if "error" in cuerpo:
                    raise RuntimeError(f"Error de la EIA: {str(cuerpo['error']).replace(_KEY, '***')}")
                return cuerpo
            if r.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code} en {url}: {r.text[:300].replace(_KEY, '***')}")
            ultimo = f"HTTP {r.status_code}"
        except (requests.ConnectionError, requests.Timeout) as exc:
            ultimo = type(exc).__name__
        if intento < max_reintentos:
            time.sleep(backoff_base_s * 2**intento + random.uniform(0, 0.5))
    raise RuntimeError(f"Se agotaron los reintentos en {url}: {ultimo}")


# %%
resumen = {}
for item in PLAN:
    url_base = f"{BASE}/{item['ruta']}/data/?{item['query']}"
    filas, offset, total = [], 0, None
    while True:
        resp = _get(f"{url_base}&offset={offset}")["response"]
        datos = resp.get("data", [])
        total = int(resp.get("total") or 0)
        filas.extend(datos)
        offset += len(datos)
        if not datos or offset >= total:
            break
    if len(filas) < total:
        raise RuntimeError(f"Paginación incompleta en {item['nombre']}: {len(filas)}/{total}")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    carpeta = f"{RAIZ}/bronze/{item['nombre']}"
    os.makedirs(carpeta, exist_ok=True)
    doc = {"metadata": {"dataset": item["nombre"], "ruta": item["ruta"],
                        "parametros": item["query"], "filas": len(filas), "total_api": total,
                        "extraido_utc": datetime.now(UTC).isoformat()},
           "data": filas}
    with open(f"{carpeta}/{item['nombre']}__{run_id}.json", "x", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    resumen[item["nombre"]] = len(filas)
    print(f"{item['nombre']}: {len(filas)} filas desde {item['inicio']}")

notebookutils.notebook.exit(json.dumps(resumen))
