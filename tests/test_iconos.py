"""Íconos SVG y medidas de imagen: SVG válidos, un solo estilo y DAX bien formado."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import generar_iconos as gi  # noqa: E402
import generar_powerbi as gp  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"


def test_archivos_svg_validos_y_con_un_solo_estilo():
    archivos = sorted((RAIZ / "assets" / "icons").glob("*.svg"))
    assert {p.stem for p in archivos} == set(gi.ICONOS)
    for p in archivos:
        r = ET.parse(p).getroot()
        assert r.tag == f"{NS}svg" and r.get("viewBox") == "0 0 24 24", p.name
        assert r.get("stroke-width") == "2" and r.get("stroke-linecap") == "round", p.name
        assert "http" not in p.read_text(encoding="utf-8").replace(
            "http://www.w3.org/2000/svg", ""), f"{p.name}: dependencia externa"


def test_indice_lista_todos_los_iconos():
    indice = (RAIZ / "assets" / "icons" / "index.md").read_text(encoding="utf-8")
    for n in gi.ICONOS:
        assert f"`{n}.svg`" in indice
    assert set(gi.USOS) == set(gi.ICONOS)


def test_data_uri_escapado_y_reversible():
    for n in gi.ICONOS:
        uri = gi.data_uri(gi.svg(n, "#C4531A", 20))
        assert uri.startswith("data:image/svg+xml;utf8,")
        cuerpo = uri.split(",", 1)[1]
        assert "#" not in cuerpo and "<" not in cuerpo and '"' not in cuerpo
        ET.fromstring(unquote(cuerpo))


def test_medidas_bien_formadas_y_sin_pisar_las_existentes():
    ms = gi.medidas()
    nombres = [m.nombre for m in ms]
    assert len(nombres) == len(set(nombres))
    existentes = {m.nombre for m in gp.leer_medidas(gp.SPEC.read_text(encoding="utf-8"))}
    assert not set(nombres) & existentes
    for m in ms:
        sin_textos = re.sub(r'"(?:[^"]|"")*"', '""', m.expresion)
        assert sin_textos.count("(") == sin_textos.count(")"), m.nombre
        for ref in re.findall(r"(?<![\w'\]])\[([^\]]+)\]", sin_textos):
            # [Value] y [i] son columnas locales ({...} y ADDCOLUMNS), no medidas
            assert ref in existentes or ref in ("Value", "i"), f"{m.nombre}: [{ref}]"


def test_archivo_dax_actualizado(tmp_path, monkeypatch):
    actual = gi.DAX.read_text(encoding="utf-8")
    assert actual == gi.a_dax(gi.medidas()), "corré python scripts/generar_iconos.py"
