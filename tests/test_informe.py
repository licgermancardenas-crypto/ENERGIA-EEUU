"""Informe PBIR: 5 páginas y cada medida o columna usada existe en el modelo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import generar_informe as gi  # noqa: E402
import generar_modelo_semantico as gm  # noqa: E402


def _campos(obj):
    if isinstance(obj, dict):
        for k in ("Measure", "Column"):
            if k in obj and "Property" in obj[k] and "Entity" in obj[k]["Expression"].get(
                    "SourceRef", {}):
                yield k, obj[k]["Expression"]["SourceRef"]["Entity"], obj[k]["Property"]
        for v in obj.values():
            yield from _campos(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _campos(v)


def test_informe_referencia_campos_existentes(tmp_path):
    raiz = gi.generar("WS", "00000000-0000-0000-0000-000000000000", tmp_path)
    paginas = json.loads((raiz / "definition/pages/pages.json").read_text(encoding="utf-8"))
    assert len(paginas["pageOrder"]) == 7

    medidas = {m.nombre for m in gm.todas_las_medidas()}
    columnas = {(t, c) for t, cols in gm.TABLAS.items() for c, _ in cols}
    visuales = list(raiz.glob("definition/pages/*/visuals/*/visual.json"))
    assert len(visuales) > 30
    for v in visuales:
        for tipo, ent, prop in _campos(json.loads(v.read_text(encoding="utf-8"))):
            if tipo == "Measure":
                assert ent == gm.TABLA_MEDIDAS and prop in medidas, f"{v}: [{prop}]"
            else:
                assert (ent, prop) in columnas, f"{v}: {ent}[{prop}]"
    assert (raiz / "StaticResources/RegisteredResources/tema_pulso_energetico.json").exists()
