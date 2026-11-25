"""Exportación Gold -> JSON del dashboard: todo número publicado debe salir de Gold."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from eia_pulso.bronze.ingest import run_bronze
from eia_pulso.gold.build import run_gold
from eia_pulso.silver.transform import run_silver
from eia_pulso.web.export import ExportError, exportar, fecha_larga, num, pct
from tests.conftest import HOY

ARCHIVOS = {"meta", "series", "ultimo_dato", "diarios", "semanales", "mensuales", "frescura",
            "rezago", "destacados"}


@pytest.fixture
def exportado(settings, cliente_falso, tmp_path):
    run_bronze(settings, cliente_falso, run_id="R1")
    run_silver(settings, hoy=HOY, run_id="S1")
    run_gold(settings, hoy=HOY)
    destino = tmp_path / "web_data"
    res = exportar(settings.gold_dir, destino)
    datos = {n: json.loads((destino / f"{n}.json").read_text(encoding="utf-8")) for n in ARCHIVOS}
    return settings, res, datos


def test_formato_rioplatense():
    assert num(1234567.891) == "1.234.567,89"
    assert num(3.1, 0) == "3"
    assert pct(-0.0153) == "1,5 %"
    assert fecha_larga(date(2026, 8, 1), "monthly") == "agosto de 2026"
    assert fecha_larga(date(2026, 11, 7), "daily") == "07/11/2026"


def test_exporta_todos_los_archivos(exportado):
    _, res, datos = exportado
    assert set(res.archivos) == ARCHIVOS
    assert datos["meta"]["conteos"]["fact_ultimo_dato"] == len(datos["ultimo_dato"])
    assert {s["key"] for s in datos["series"]} == set(datos["ultimo_dato"])
    assert len(datos["rezago"]["escenarios"]) == 2
    assert all(f["estado"] for f in datos["frescura"]["datasets"])


def test_hechos_identicos_a_gold(exportado):
    settings, _, datos = exportado
    gold = pd.read_parquet(settings.gold_dir / "parquet" / "fact_precios_diarios.parquet")
    wti = gold[gold["serie_key"] == "RWTC_D"].sort_values("fecha")
    exp = datos["diarios"]["RWTC_D"]
    assert len(exp) == len(wti)
    assert exp[-1] == [wti["fecha"].iloc[-1].isoformat()[:10], wti["valor"].iloc[-1]]
    fechas = [f for f, _ in exp]
    assert fechas == sorted(fechas)


def test_banner_y_barras_salen_de_ultimo_dato(exportado):
    _, _, datos = exportado
    ultimo = datos["ultimo_dato"]
    for sector, d in datos["destacados"].items():
        for key in [d["banner"]["principal"], *d["banner"]["indicadores"]]:
            assert key in ultimo, (sector, key)
        for item in d["barras"]["items"]:
            assert item["valor"] == ultimo[item["key"]]["valor"]
            assert item["fecha"] == ultimo[item["key"]]["fecha"]
        assert len(d["frases"]) == 3
    gas = datos["destacados"]["gas"]["barras"]["items"]
    assert "N9140US2_M" not in {i["key"] for i in gas}  # el total no es un sector


def test_frases_trazables(exportado):
    _, _, datos = exportado
    wti = datos["diarios"]["RWTC_D"]
    frase = datos["destacados"]["petroleo"]["frases"][0]
    assert frase["fecha"] == wti[-1][0]
    assert frase["valores"]["ultimo"] == wti[-1][1]
    assert num(wti[-1][1]) in frase["texto"]
    for d in datos["destacados"].values():
        for f in d["frases"]:
            assert f["origen"] and f["texto"].endswith(".")
            assert "nan" not in f["texto"].lower()


def test_sin_gold_falla_claro(tmp_path):
    with pytest.raises(ExportError, match="No hay Gold"):
        exportar(tmp_path / "nada", tmp_path / "out")
