"""Modelo semántico TMDL: todas las medidas de la especificación, relaciones y tablas válidas."""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import generar_modelo_semantico as gm  # noqa: E402
import generar_powerbi as gp  # noqa: E402


def test_modelo_generado(tmp_path):
    raiz = gm.generar("srv.datawarehouse.fabric.microsoft.com",
                      "00000000-0000-0000-0000-000000000000", tmp_path)
    d = raiz / "definition"
    medidas = gm.todas_las_medidas()
    imagenes = [m for m in medidas if m.carpeta == gm.CARPETA_IMAGENES]
    assert imagenes, "faltan las medidas de íconos"

    tablas = {p.stem for p in (d / "tables").glob("*.tmdl")}
    assert tablas == set(gm.TABLAS)

    serie = (d / "tables" / f"{gm.TABLA_MEDIDAS}.tmdl").read_text(encoding="utf-8")
    assert len(re.findall(r"^\tmeasure ", serie, re.M)) == len(medidas)
    assert serie.count("```") == 2 * len(medidas)
    assert serie.count("dataCategory: ImageUrl") == len(imagenes)

    rels = (d / "relationships.tmdl").read_text(encoding="utf-8")
    assert rels.count("relationship ") == len(gm.FACTS) * 3 + 1
    for desde, cd, hacia, ch in gm.relaciones():
        assert (desde, cd) in {(t, c) for t, cols in gm.TABLAS.items() for c, _ in cols}
        assert (hacia, ch) in {(t, c) for t, cols in gm.TABLAS.items() for c, _ in cols}

    fecha = (d / "tables" / "dim_fecha.tmdl").read_text(encoding="utf-8")
    assert "dataCategory: Time" in fecha and "isKey" in fecha
    assert "mode: directLake" in fecha


def test_formatos():
    m = gp.Medida
    assert gm.formato(m("WTI vs promedio 12 meses %", "DIVIDE ( 1, 2 )", "Precios spot")) == "0.0 %"
    assert gm.formato(m("Precio gasolina regular", "AVERAGE ( x[v] )",
                        "Combustibles en surtidor")) == "#,0.000"
    assert gm.formato(m("Texto", 'FORMAT ( 1, "0" )', "Precios spot")) is None


def test_nombres_tmdl():
    assert gm.q("dim_serie") == "dim_serie"
    assert gm.q("Último WTI") == "'Último WTI'"
    assert gm.q("O'Neil") == "'O''Neil'"
