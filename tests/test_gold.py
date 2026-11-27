"""Gold: modelo estrella, validaciones, frescura y análisis de rezago."""

from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from eia_pulso.bronze.ingest import run_bronze
from eia_pulso.gold.build import run_gold
from eia_pulso.gold.freshness import calcular_frescura
from eia_pulso.gold.lag import correlacion_cruzada, resumen_rezago
from eia_pulso.gold.validations import GoldValidationError, validar_gold
from eia_pulso.silver.transform import run_silver
from tests.conftest import HOY

TABLAS = {
    "dim_fecha", "dim_serie", "dim_region", "fact_precios_diarios", "fact_precios_mensuales",
    "fact_precio_surtidor_semanal", "fact_inventarios_semanales",
    "fact_almacenamiento_gas_semanal", "fact_consumo_gas_mensual", "fact_produccion_mensual",
    "fact_ultimo_dato",
}


@pytest.fixture
def pipeline_completo(settings, cliente_falso):
    run_bronze(settings, cliente_falso, run_id="R1")
    run_silver(settings, hoy=HOY, run_id="S1")
    return run_gold(settings, hoy=HOY)


def test_gold_construye_estrella_completa(settings, pipeline_completo):
    res = pipeline_completo
    assert set(res.conteos) == TABLAS
    assert all(n > 0 for n in res.conteos.values())
    base = settings.gold_dir
    for t in TABLAS:
        assert (base / "parquet" / f"{t}.parquet").exists()
    assert (base / "pulso.duckdb").exists()
    for j in ("frescura", "analisis_rezago", "resumen"):
        json.loads((base / f"{j}.json").read_text(encoding="utf-8"))

    dim_serie = pd.read_parquet(base / "parquet" / "dim_serie.parquet")
    # la misma serie EIA en dos frecuencias tiene claves distintas
    assert {"RWTC_D", "RWTC_M"} <= set(dim_serie["serie_key"])
    ultimo = pd.read_parquet(base / "parquet" / "fact_ultimo_dato.parquet")
    assert len(ultimo) == len(dim_serie)
    assert ultimo["variacion_pct"].notna().all()


def test_gold_se_reconstruye_igual_en_cada_corrida(settings, pipeline_completo):
    segunda = run_gold(settings, hoy=HOY)
    assert segunda.conteos == pipeline_completo.conteos


def test_validaciones_detectan_problemas():
    dim_fecha = pd.DataFrame({"fecha_key": [20260101, 20260102]})
    dim_serie = pd.DataFrame({"serie_key": ["A_D", "A_D"]})  # duplicada
    dim_region = pd.DataFrame({"region_key": ["NUS"]})
    hecho = pd.DataFrame({"fecha_key": [20260101, 20260101, 20991231],
                          "serie_key": ["A_D", "A_D", "B_D"],
                          "region_key": ["NUS", "NUS", "ZZZ"], "valor": [1.0, 1.0, 2.0]})
    errores = validar_gold(
        {"dim_fecha": dim_fecha, "dim_serie": dim_serie, "dim_region": dim_region,
         "fact_x": hecho, "fact_vacia": pd.DataFrame()},
        conteos_silver={"fact_x": 4}, series_silver=1,
    )
    texto = "\n".join(errores)
    assert "fact_vacia: tabla vacía" in texto
    assert "dim_serie: 1 claves duplicadas" in texto
    assert "fact_x: 1 claves duplicadas" in texto
    assert "sin match en dim_fecha" in texto
    assert "sin match en dim_serie" in texto
    assert "sin match en dim_region" in texto
    assert "Conciliación fact_x: Silver=4 Gold=3" in texto


def test_gold_falla_y_no_pisa_gold_previo_si_falta_un_dataset(settings, cliente_falso):
    run_bronze(settings, cliente_falso, run_id="R1")
    run_silver(settings, hoy=HOY, run_id="S1")
    run_gold(settings, hoy=HOY)
    # simulamos que desaparece Silver de un dataset -> tabla vacía
    import shutil
    shutil.rmtree(settings.silver_dir / "consumo_gas_mensual")
    with pytest.raises(GoldValidationError, match="fact_consumo_gas_mensual: tabla vacía"):
        run_gold(settings, hoy=HOY)
    assert (settings.gold_dir / "parquet" / "fact_consumo_gas_mensual.parquet").exists()


# ----------------------------------------------------------------------------- Frescura
def _silver(dataset, periodo):
    return pd.DataFrame({"dataset": [dataset], "periodo": [pd.Timestamp(periodo)]})


def test_frescura_umbrales_y_fin_de_periodo(settings):
    silver = pd.concat([
        _silver("precios_spot_diarios", "2026-11-15"),     # 10 días -> al día (umbral 10)
        _silver("henry_hub_diario", "2026-11-14"),         # 11 días -> atrasado
        _silver("inventarios_semanales", "2026-11-13"),    # 12 días -> al día (14)
        _silver("almacenamiento_gas_semanal", "2026-11-01"),  # 24 días -> atrasado
        _silver("produccion_crudo_mensual", "2026-08-01"),  # fin 31-ago: 86 días -> al día
        _silver("consumo_gas_mensual", "2026-06-01"),       # fin 30-jun: 148 días -> atrasado
    ])
    f = calcular_frescura(silver, settings, date(2026, 11, 25)).set_index("dataset")
    assert f.loc["precios_spot_diarios", "estado"] == "al_dia"
    assert f.loc["henry_hub_diario", "estado"] == "atrasado"
    assert f.loc["inventarios_semanales", "estado"] == "al_dia"
    assert f.loc["almacenamiento_gas_semanal", "estado"] == "atrasado"
    assert f.loc["produccion_crudo_mensual", "dias_atraso"] == 86
    assert f.loc["produccion_crudo_mensual", "estado"] == "al_dia"
    assert f.loc["consumo_gas_mensual", "estado"] == "atrasado"
    assert f.loc["precio_surtidor_semanal", "estado"] == "sin_datos"


# ----------------------------------------------------------------------------- Rezago
def test_rezago_detecta_desfasaje_conocido():
    rng = np.random.default_rng(42)
    meses = pd.date_range("2010-01-01", periods=180, freq="MS")
    dp = rng.normal(0, 0.05, len(meses))
    precio = 60 * np.cumprod(1 + dp)
    k = 6
    dq = np.r_[np.zeros(k), dp[:-k]] * 0.5 + rng.normal(0, 0.005, len(meses))
    prod = 10000 * np.cumprod(1 + dq)
    tabla = correlacion_cruzada(pd.DataFrame({"periodo": meses, "valor": precio}),
                                pd.DataFrame({"periodo": meses, "valor": prod}), 12, 24)
    assert len(tabla) == 13
    r = resumen_rezago(tabla)
    assert r["rezago_optimo_meses"] == k
    assert r["correlacion"] > 0.9
    assert "no causal" in r["advertencia"]


def test_rezago_excluyendo_ventana():
    meses = pd.date_range("2018-01-01", periods=96, freq="MS")
    valores = np.linspace(100, 200, len(meses))
    df = pd.DataFrame({"periodo": meses, "valor": valores})
    completo = correlacion_cruzada(df, df, 0, 2)
    sin = correlacion_cruzada(df, df, 0, 2, excluir=("2020-01", "2021-12"))
    # 24 meses excluidos + la variación que sale de la ventana
    assert completo.loc[0, "n_obs"] - sin.loc[0, "n_obs"] == 25


def test_gold_publica_los_dos_escenarios_de_rezago(settings, pipeline_completo):
    r = json.loads((settings.gold_dir / "analisis_rezago.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in r["escenarios"]] == ["completo", "sin_pandemia"]
    assert r["escenarios"][1]["excluir"] == ["2020-01", "2021-12"]
    assert "no causal" in r["advertencia"]
    tabla = pd.read_parquet(settings.gold_dir / "parquet" / "analisis_rezago.parquet")
    assert set(tabla["escenario"]) == {"completo", "sin_pandemia"}
    assert len(tabla) == 2 * (settings.rezago_max_meses + 1)


def test_rezago_con_pocos_datos_no_inventa_resultado():
    meses = pd.date_range("2026-01-01", periods=10, freq="MS")
    df = pd.DataFrame({"periodo": meses, "valor": range(1, 11)})
    tabla = correlacion_cruzada(df, df, 12, 24)
    assert tabla["correlacion"].isna().all()
    assert resumen_rezago(tabla)["rezago_optimo_meses"] is None
    assert not any(isinstance(x, float) and math.isinf(x) for x in tabla["correlacion"])


def test_gold_conserva_la_capa_geo(settings, pipeline_completo):
    geo = settings.gold_dir / "geo"
    geo.mkdir(exist_ok=True)
    (geo / "validacion.json").write_text("{}", encoding="utf-8")
    run_gold(settings, hoy=HOY)
    assert (settings.gold_dir / "geo" / "validacion.json").exists()
