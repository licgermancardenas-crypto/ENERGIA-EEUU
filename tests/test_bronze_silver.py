"""Bronze (no sobrescribe, metadatos, incremental) y Silver (validación, dedup, idempotencia,
días incompletos y auditoría de revisiones)."""

from __future__ import annotations

import json
from datetime import timedelta

import pandas as pd
import pytest

from eia_pulso.api.client import ResultadoConsulta
from eia_pulso.bronze.ingest import calcular_inicio, escribir_bronze, run_bronze
from eia_pulso.silver.storage import leer_revisiones, leer_silver
from eia_pulso.silver.transform import run_silver, validar
from tests.conftest import HOY, ClienteFalso, dias_atras, fila_api


def _bronze_manual(settings, dataset, filas, run_id):
    ds = settings.datasets[dataset]
    res = ResultadoConsulta(filas, len(filas), 1, "https://fake", {"facets": ds.facetas})
    return escribir_bronze(settings.bronze_dir, ds, res, run_id)


# ----------------------------------------------------------------------------- Bronze
def test_bronze_escribe_un_json_por_dataset_con_metadatos(settings, cliente_falso):
    res = run_bronze(settings, cliente_falso, run_id="20261125T000000000000Z")
    assert len(res) == len(settings.datasets)
    doc = json.loads(res[0].archivo.read_text(encoding="utf-8"))
    meta = doc["metadata"]
    assert meta["filas"] == len(doc["data"]) == res[0].filas
    assert {"ruta", "parametros", "extraido_utc", "run_id"} <= set(meta)
    assert "20261125T000000000000Z" in res[0].archivo.name


def test_bronze_nunca_sobrescribe(settings, cliente_falso):
    run_bronze(settings, cliente_falso, datasets=["henry_hub_diario"], run_id="R1")
    with pytest.raises(FileExistsError):
        run_bronze(settings, cliente_falso, datasets=["henry_hub_diario"], run_id="R1")
    run_bronze(settings, cliente_falso, datasets=["henry_hub_diario"], run_id="R2")
    assert len(list((settings.bronze_dir / "henry_hub_diario").glob("*.json"))) == 2


def test_bronze_incremental_usa_ultimo_periodo_silver_menos_ventana(settings, cliente_falso):
    ds = settings.datasets["produccion_crudo_mensual"]
    assert calcular_inicio(ds, settings) == "2010-01"  # primera corrida: desde el inicio
    run_bronze(settings, cliente_falso, datasets=[ds.nombre], run_id="R1")
    run_silver(settings, hoy=HOY, run_id="S1", datasets=[ds.nombre])
    ultimo = leer_silver(settings.silver_dir, ds.nombre)["periodo"].max().date()
    esperado = (ultimo - timedelta(days=settings.ventana_relectura_dias["monthly"]))
    assert calcular_inicio(ds, settings) == esperado.strftime("%Y-%m")
    assert calcular_inicio(ds, settings, completo=True) == "2010-01"


# ----------------------------------------------------------------------------- Silver
def test_validacion_descarta_filas_invalidas(settings):
    ds = settings.datasets["precios_spot_diarios"]
    crudo = pd.DataFrame([
        fila_api("RWTC", dias_atras(10), 70.5),        # ok
        fila_api("RWTC", None, 70.0),                  # sin fecha
        fila_api("RWTC", "no-es-fecha", 70.0),         # sin fecha (inválida)
        fila_api("RWTC", dias_atras(11), None),        # sin valor
        fila_api("RWTC", dias_atras(12), "NA"),        # sin valor (no numérico)
        fila_api(None, dias_atras(13), 70.0),          # clave incompleta
        fila_api("OTRA", dias_atras(14), 70.0),        # serie no configurada
        fila_api("RBRTE", dias_atras(15), 0),          # valor <= 0
        fila_api("RBRTE", dias_atras(16), -3.2),       # valor <= 0
        fila_api("RBRTE", dias_atras(1), 80.0),        # día incompleto (N=2)
        fila_api("RBRTE", dias_atras(2), 80.0),        # ok (justo N días)
    ])
    validas, desc = validar(crudo, ds, HOY, dias_minimos=2)
    assert len(validas) == 2
    assert desc == {"sin_fecha": 2, "sin_valor": 2, "clave_incompleta": 1,
                    "serie_no_configurada": 1, "valor_no_positivo": 2, "dia_incompleto": 1}
    assert validas["valor"].dtype == "float64"


def test_dias_incompletos_entran_en_corridas_posteriores(settings):
    ds = "henry_hub_diario"
    _bronze_manual(settings, ds, [fila_api("RNGWHHD", dias_atras(1), 3.1)], "R1")
    r1 = run_silver(settings, hoy=HOY, run_id="S1", datasets=[ds])
    assert r1.insertadas[ds] == 0
    r2 = run_silver(settings, hoy=HOY + timedelta(days=1), run_id="S2", datasets=[ds])
    assert r2.insertadas[ds] == 1


def test_merge_insert_only_es_idempotente(settings, cliente_falso):
    run_bronze(settings, cliente_falso, run_id="R1")
    r1 = run_silver(settings, hoy=HOY, run_id="S1")
    total = len(leer_silver(settings.silver_dir))
    assert total > 0 and sum(r1.insertadas.values()) == total

    r2 = run_silver(settings, hoy=HOY, run_id="S2")  # misma entrada: no inserta nada
    assert sum(r2.insertadas.values()) == 0
    assert len(leer_silver(settings.silver_dir)) == total

    run_bronze(settings, cliente_falso, run_id="R2")  # Bronze repetido (solapado)
    r3 = run_silver(settings, hoy=HOY, run_id="S3")
    assert sum(r3.insertadas.values()) == 0
    df = leer_silver(settings.silver_dir)
    assert len(df) == total
    assert not df.duplicated(["dataset", "serie", "periodo"]).any()


def test_dedup_dentro_de_un_mismo_bronze(settings):
    ds = "henry_hub_diario"
    fila = fila_api("RNGWHHD", dias_atras(10), 3.1)
    _bronze_manual(settings, ds, [fila, dict(fila)], "R1")
    r = run_silver(settings, hoy=HOY, run_id="S1", datasets=[ds])
    assert r.insertadas[ds] == 1


def test_particiona_por_anio_y_mes(settings):
    ds = "produccion_crudo_mensual"
    _bronze_manual(settings, ds, [fila_api("MCRFPUS2", "2025-12", 13500),
                                  fila_api("MCRFPUS2", "2026-01", 13600)], "R1")
    run_silver(settings, hoy=HOY, run_id="S1", datasets=[ds])
    base = settings.silver_dir / ds
    assert (base / "anio=2025" / "mes=12" / "part-S1.parquet").exists()
    assert (base / "anio=2026" / "mes=01" / "part-S1.parquet").exists()


def test_revision_no_pisa_y_se_audita_una_sola_vez(settings):
    ds = "produccion_crudo_mensual"
    _bronze_manual(settings, ds, [fila_api("MCRFPUS2", "2026-07", 13800)], "R1")
    run_silver(settings, hoy=HOY, run_id="S1", datasets=[ds])

    # la EIA revisa julio y además publica agosto
    _bronze_manual(settings, ds, [fila_api("MCRFPUS2", "2026-07", 13850),
                                  fila_api("MCRFPUS2", "2026-08", 13965)], "R2")
    r2 = run_silver(settings, hoy=HOY, run_id="S2", datasets=[ds])
    assert r2.insertadas[ds] == 1
    assert r2.revisiones_nuevas == 1

    silver = leer_silver(settings.silver_dir, ds).set_index("periodo")["valor"]
    assert silver[pd.Timestamp("2026-07-01")] == 13800  # no se pisó
    rev = leer_revisiones(settings.silver_dir)
    assert len(rev) == 1
    assert rev.iloc[0]["valor_cargado"] == 13800 and rev.iloc[0]["valor_nuevo"] == 13850

    r3 = run_silver(settings, hoy=HOY, run_id="S3", datasets=[ds])  # re-correr: nada nuevo
    assert r3.revisiones_nuevas == 0 and r3.insertadas[ds] == 0
    assert len(leer_revisiones(settings.silver_dir)) == 1


def test_revision_dentro_de_la_primera_carga_se_detecta(settings):
    ds = "precios_spot_diarios"
    clienteA = ClienteFalso(settings, valor=lambda s, i: 70.0)
    clienteB = ClienteFalso(settings, valor=lambda s, i: 70.0,
                            ajustes={("RWTC", dias_atras(30)): 71.0})
    run_bronze(settings, clienteA, datasets=[ds], run_id="R1")
    run_bronze(settings, clienteB, datasets=[ds], run_id="R2")
    r = run_silver(settings, hoy=HOY, run_id="S1", datasets=[ds])
    assert r.revisiones_nuevas == 1
    df = leer_silver(settings.silver_dir, ds)
    fila = df[(df["serie"] == "RWTC") & (df["periodo"] == pd.Timestamp(dias_atras(30)))]
    assert fila["valor"].item() == 70.0  # se conserva el primer valor cargado
