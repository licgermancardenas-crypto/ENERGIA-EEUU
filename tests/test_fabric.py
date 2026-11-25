"""Artefactos de Fabric: notebooks válidos, plan de Copy correcto y paridad de la lógica pura
de los notebooks con el pipeline local. (Spark/Delta no se ejecuta localmente.)"""

from __future__ import annotations

import ast
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import generar_fabric as gf  # noqa: E402

from eia_pulso.gold.freshness import calcular_frescura  # noqa: E402
from eia_pulso.gold.lag import correlacion_cruzada  # noqa: E402

SRC = RAIZ / "fabric" / "notebooks" / "src"


def _helpers(nombre: str) -> dict:
    ns: dict = {}
    exec(gf.celda_helpers((SRC / f"{nombre}.py").read_text(encoding="utf-8")), ns)
    return ns


@pytest.fixture(scope="module")
def nb01():
    return _helpers("NB01_Silver")


@pytest.fixture(scope="module")
def nb02():
    return _helpers("NB02_Gold")


# ----------------------------------------------------------------------- generación
def test_generacion_produce_notebooks_validos(tmp_path):
    escritos = gf.generar(salida=tmp_path)
    notebooks = [p for p in escritos if p.suffix == ".ipynb"]
    assert {p.stem for p in notebooks} == {"NB00_Bronze_Alternativo", "NB01_Silver", "NB02_Gold"}
    for p in notebooks:
        nb = json.loads(p.read_text(encoding="utf-8"))
        assert nb["nbformat"] == 4
        assert nb["metadata"]["kernelspec"]["name"] == "synapse_pyspark"
        assert nb["cells"][0]["cell_type"] == "markdown"
        param = [c for c in nb["cells"] if "parameters" in c["metadata"].get("tags", [])]
        assert len(param) == 1, f"{p.name}: debe tener exactamente una celda de parámetros"
        for c in nb["cells"]:
            if c["cell_type"] == "code":
                ast.parse("".join(c["source"]))  # todo el código compila


def test_artefactos_del_repo_estan_actualizados(tmp_path):
    gf.generar(salida=tmp_path)
    for rel in ("config/eia_datasets.json", "config/eia_plan.json",
                "notebooks/NB00_Bronze_Alternativo.ipynb", "notebooks/NB01_Silver.ipynb",
                "notebooks/NB02_Gold.ipynb"):
        repo = RAIZ / "fabric" / rel
        assert repo.exists(), f"Falta {rel}: corré python scripts/generar_fabric.py"
        assert repo.read_text(encoding="utf-8") == (tmp_path / rel).read_text(encoding="utf-8"), (
            f"{rel} desactualizado: corré python scripts/generar_fabric.py")


def test_plan_inicial_para_copy(tmp_path):
    gf.generar(salida=tmp_path)
    plan = json.loads((tmp_path / "config" / "eia_plan.json").read_text(encoding="utf-8"))
    cfg = json.loads((tmp_path / "config" / "eia_datasets.json").read_text(encoding="utf-8"))
    assert [p["nombre"] for p in plan] == [d["nombre"] for d in cfg["datasets"]]
    hh = next(p for p in plan if p["nombre"] == "henry_hub_diario")
    assert hh["ruta"] == "natural-gas/pri/fut" and hh["inicio"] == "2023-01-01"
    assert "facets%5Bseries%5D%5B%5D=RNGWHHD" in hh["query"]
    for p in plan:
        assert "api_key" not in p["query"] and "offset" not in p["query"]
    texto = json.dumps(cfg) + json.dumps(plan)
    assert "api_key" not in texto


def test_query_del_notebook_igual_a_la_del_cliente_local(nb01, settings):
    """El notebook arma los mismos parámetros que el cliente local (salvo offset/api_key)."""
    import responses

    from eia_pulso.api.client import EIAClient

    ds = settings.datasets["inventarios_semanales"]
    with responses.RequestsMock() as rsps:
        rsps.get(f"https://api.eia.gov/v2/{ds.ruta}/data/",
                 json={"response": {"total": "0", "data": []}})
        EIAClient("k", tamanio_pagina=5000).fetch_data(ds.ruta, ds.frecuencia, "2023-01-01",
                                                      ds.facetas)
        local = [(k, v) for k, v in parse_qsl(rsps.calls[0].request.url.split("?", 1)[1])
                 if k not in ("api_key", "offset")]
    ds_nb = {"frecuencia": ds.frecuencia, "series": ds.series}
    assert sorted(parse_qsl(nb01["construir_query"](ds_nb, "2023-01-01"))) == sorted(local)


# ----------------------------------------------------------------------- NB01 helpers
FILAS = [{"period": "2026-11-13", "series": "WCESTUS1", "value": "417797"},
         {"period": "2026-11-06", "series": "WCESTUS1", "value": "415000"}]


@pytest.mark.parametrize("texto", [
    json.dumps({"response": {"total": "2", "data": FILAS}}),                      # 1 página
    json.dumps([{"response": {"data": FILAS[:1]}}, {"response": {"data": FILAS[1:]}}]),  # arreglo
    "\n".join(json.dumps({"response": {"data": [f]}}) for f in FILAS),            # 1 por línea
    "".join(json.dumps({"response": {"data": [f]}}) for f in FILAS),              # concatenadas
    json.dumps({"metadata": {"filas": 2}, "data": FILAS}),                        # formato local
    "﻿" + json.dumps(FILAS),                                                 # filas + BOM
])
def test_parsear_bronze_acepta_todas_las_formas(nb01, texto):
    assert nb01["parsear_bronze"](texto) == FILAS


def test_ts_desde_nombre(nb01):
    f = nb01["ts_desde_nombre"]
    assert f("inventarios__20261125T030501123456Z.json") == "2026-11-25T03:05:01.123456Z"
    assert f("inventarios__20261125T030501Z.json") == "2026-11-25T03:05:01Z"
    assert f("sin_timestamp.json") == ""


def test_inicio_incremental(nb01):
    f = nb01["inicio_incremental"]
    assert f("2010-01", None, "monthly", 186) == "2010-01"
    assert f("2010-01", date(2026, 8, 1), "monthly", 186) == "2026-01"
    assert f("2023-01-01", date(2026, 11, 17), "daily", 30) == "2026-10-18"
    assert f("2026-11-01", date(2026, 11, 17), "daily", 30) == "2026-11-01"  # >= inicio


# ----------------------------------------------------------------------- NB02 helpers
def test_rezago_del_notebook_igual_al_local(nb02):
    rng = np.random.default_rng(7)
    meses = pd.date_range("2010-01-01", periods=190, freq="MS")
    precio = pd.DataFrame({"periodo": meses, "valor": 60 * np.cumprod(1 + rng.normal(0, .05, 190))})
    prod = pd.DataFrame({"periodo": meses, "valor": 9e3 * np.cumprod(1 + rng.normal(0, .01, 190))})
    for excluir in (None, ("2020-01", "2021-12")):
        a = correlacion_cruzada(precio, prod, 12, 24, excluir=excluir)
        b = nb02["correlacion_cruzada"](precio, prod, 12, 24, excluir)
        pd.testing.assert_frame_equal(a, b)


def test_frescura_del_notebook_igual_a_la_local(nb02, settings):
    hoy = date(2026, 11, 25)
    casos = {"precios_spot_diarios": "2026-11-14", "inventarios_semanales": "2026-11-13",
             "consumo_gas_mensual": "2026-06-01", "produccion_crudo_mensual": "2026-08-01"}
    silver = pd.DataFrame({"dataset": list(casos), "periodo": pd.to_datetime(list(casos.values()))})
    local = calcular_frescura(silver, settings, hoy).set_index("dataset")
    for ds, p in casos.items():
        frec = settings.datasets[ds].frecuencia
        nb = nb02["estado_frescura"](date.fromisoformat(p), frec,
                                     settings.umbrales_frescura_dias[frec], hoy)
        assert nb["estado"] == local.loc[ds, "estado"]
        assert nb["dias_atraso"] == local.loc[ds, "dias_atraso"]
