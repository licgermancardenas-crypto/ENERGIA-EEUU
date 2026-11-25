"""Especificación Power BI: las medidas DAX referencian tablas, columnas, medidas y series que
existen. (DAX no se ejecuta localmente: esto valida la estructura contra el esquema Gold real.)"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

from eia_pulso.bronze.ingest import run_bronze
from eia_pulso.config import load_settings
from eia_pulso.gold.build import run_gold
from eia_pulso.silver.transform import run_silver
from tests.conftest import HOY, ClienteFalso

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import generar_powerbi as gp  # noqa: E402

REF_COLUMNA = re.compile(r"\b([a-z_]+)\[([a-z_]+)\]")
REF_MEDIDA = re.compile(r"(?<![\w'\]])\[([^\]]+)\]")
LITERAL_SERIE = re.compile(r'serie_key\]\s*(?:=|<>)\s*"([A-Z0-9_]+)"')


@pytest.fixture(scope="module")
def medidas():
    return gp.leer_medidas(gp.SPEC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def esquema_gold(tmp_path_factory):
    settings = load_settings(data_dir=tmp_path_factory.mktemp("pbi") / "data")
    run_bronze(settings, ClienteFalso(settings), run_id="R1")
    run_silver(settings, hoy=HOY, run_id="S1")
    run_gold(settings, hoy=HOY)
    base = settings.gold_dir / "parquet"
    return {p.stem: set(pd.read_parquet(p).columns) for p in base.glob("*.parquet")}, settings


def _sin_comentarios_ni_textos(expr: str) -> str:
    expr = re.sub(r"--.*", "", expr)
    return re.sub(r'"(?:[^"]|"")*"', '""', expr)


def test_cantidad_y_nombres_unicos(medidas):
    nombres = [m.nombre for m in medidas]
    assert 40 <= len(nombres) <= 60
    assert len(set(nombres)) == len(nombres), "nombres de medida duplicados"
    assert all(m.expresion.strip() for m in medidas)
    assert all(m.carpeta for m in medidas)


def test_columnas_existen_en_gold(medidas, esquema_gold):
    esquema, _ = esquema_gold
    for m in medidas:
        for tabla, col in REF_COLUMNA.findall(_sin_comentarios_ni_textos(m.expresion)):
            assert tabla in esquema, f"{m.nombre}: tabla inexistente {tabla}"
            assert col in esquema[tabla], f"{m.nombre}: columna inexistente {tabla}[{col}]"


def test_medidas_referenciadas_existen(medidas):
    definidas = {m.nombre for m in medidas}
    for m in medidas:
        for ref in REF_MEDIDA.findall(_sin_comentarios_ni_textos(m.expresion)):
            assert ref in definidas, f"{m.nombre}: referencia a medida inexistente [{ref}]"


def test_series_existen_en_configuracion(medidas, esquema_gold):
    _, settings = esquema_gold
    sufijo = {"daily": "_D", "weekly": "_W", "monthly": "_M"}
    validas = {s + sufijo[d.frecuencia] for d in settings.datasets.values() for s in d.series}
    usadas = {s for m in medidas for s in LITERAL_SERIE.findall(m.expresion)}
    assert usadas, "no se encontraron series en las medidas"
    assert usadas <= validas, f"series inexistentes: {usadas - validas}"


def test_parentesis_balanceados(medidas):
    for m in medidas:
        e = _sin_comentarios_ni_textos(m.expresion)
        assert e.count("(") == e.count(")"), m.nombre


def test_archivo_dax_actualizado(tmp_path):
    destino = tmp_path / "medidas.dax"
    gp.generar(salida=destino)
    repo = gp.SALIDA
    assert repo.exists(), "Falta powerbi/medidas.dax: corré python scripts/generar_powerbi.py"
    assert repo.read_text(encoding="utf-8") == destino.read_text(encoding="utf-8"), (
        "powerbi/medidas.dax desactualizado: corré python scripts/generar_powerbi.py")
    texto = destino.read_text(encoding="utf-8")
    for n in gp.PRUEBA:
        assert f"[{n}] =" in texto


def test_tema_usa_la_paleta_de_la_web():
    tema = json.loads((RAIZ / "powerbi" / "tema_pulso_energetico.json").read_text(encoding="utf-8"))
    css = (RAIZ / "web" / "src" / "app" / "globals.css").read_text(encoding="utf-8")
    claro = css.split("@media")[0]
    web = [re.search(rf"--s{i}:\s*(#[0-9a-fA-F]{{6}})", claro).group(1).upper()
           for i in range(1, 5)]
    assert [c.upper() for c in tema["dataColors"][:4]] == web
