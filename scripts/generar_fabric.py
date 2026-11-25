"""Genera los artefactos de Microsoft Fabric a partir de la configuración del repo.

- fabric/config/eia_datasets.json : datasets, series, umbrales y rezago (sin secretos)
- fabric/config/eia_plan.json     : plan inicial de la actividad Copy (carga histórica completa)
- fabric/notebooks/*.ipynb        : notebooks importables, desde fabric/notebooks/src/*.py

Uso:  python scripts/generar_fabric.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
SRC_NOTEBOOKS = RAIZ / "fabric" / "notebooks" / "src"
MARCA = re.compile(r"^# %%(?:\s*\[(?P<tipo>[a-z]+)\])?(?P<titulo>.*)$")

METADATA_NOTEBOOK = {
    "kernel_info": {"name": "synapse_pyspark"},
    "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark",
                   "language": "Python"},
    "language_info": {"name": "python"},
    "microsoft": {"language": "python", "language_group": "synapse_pyspark"},
}


def leer_celdas(fuente: str) -> list[dict]:
    """Parsea el formato 'percent' (# %%) en celdas {tipo, titulo, lineas}."""
    celdas: list[dict] = []
    for linea in fuente.splitlines():
        m = MARCA.match(linea)
        if m:
            celdas.append({"tipo": m.group("tipo") or "code",
                           "titulo": m.group("titulo").strip(), "lineas": []})
        elif celdas:
            celdas[-1]["lineas"].append(linea)
    for c in celdas:
        while c["lineas"] and not c["lineas"][-1].strip():
            c["lineas"].pop()
        while c["lineas"] and not c["lineas"][0].strip():
            c["lineas"].pop(0)
    return celdas


def celda_helpers(fuente: str) -> str:
    """Código de la celda [helpers] (funciones puras, testeables sin Spark)."""
    return "\n".join(
        "\n".join(c["lineas"]) for c in leer_celdas(fuente) if c["tipo"] == "helpers"
    )


def _fuente(lineas: list[str]) -> list[str]:
    return [linea + "\n" for linea in lineas[:-1]] + lineas[-1:] if lineas else []


def a_ipynb(fuente: str) -> dict:
    celdas = []
    for c in leer_celdas(fuente):
        if c["tipo"] == "markdown":
            texto = [re.sub(r"^# ?", "", linea) for linea in c["lineas"]]
            celdas.append({"cell_type": "markdown", "metadata": {}, "source": _fuente(texto)})
            continue
        lineas = list(c["lineas"])
        if c["titulo"]:
            lineas.insert(0, f"# {c['titulo']}")
        meta = {"tags": ["parameters"]} if c["tipo"] == "parameters" else {}
        if c["tipo"] == "helpers":
            meta = {"tags": ["helpers"]}
        celdas.append({"cell_type": "code", "execution_count": None, "metadata": meta,
                       "outputs": [], "source": _fuente(lineas)})
    return {"cells": celdas, "metadata": METADATA_NOTEBOOK, "nbformat": 4, "nbformat_minor": 5}


def config_fabric(config_yaml: Path) -> dict:
    raw = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    return {
        "generado_desde": "config/pipeline.yaml",
        "dias_minimos_diarios": raw["silver"]["dias_minimos_diarios"],
        "ventana_relectura_dias": raw["ventana_relectura_dias"],
        "umbrales_frescura_dias": raw["umbrales_frescura_dias"],
        "rezago": raw["rezago"],
        "regiones": raw["regiones"],
        "datasets": [
            {"nombre": n, "ruta": d["ruta"].strip("/"), "frecuencia": d["frecuencia"],
             "inicio": str(d["inicio"]), "sector": d["sector"], "categoria": d["categoria"],
             "tabla_gold": d["tabla_gold"], "solo_positivos": d.get("solo_positivos", True),
             "series": d["series"]}
            for n, d in raw["datasets"].items()
        ],
    }


def _escribir_json(destino: Path, obj) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generar(salida: Path = RAIZ / "fabric", config_yaml: Path = RAIZ / "config" / "pipeline.yaml"
            ) -> list[Path]:
    escritos = []
    cfg = config_fabric(config_yaml)
    _escribir_json(salida / "config" / "eia_datasets.json", cfg)
    escritos.append(salida / "config" / "eia_datasets.json")

    ns: dict = {}
    exec(celda_helpers((SRC_NOTEBOOKS / "NB01_Silver.py").read_text(encoding="utf-8")), ns)
    _escribir_json(salida / "config" / "eia_plan.json", ns["construir_plan"](cfg, {}))
    escritos.append(salida / "config" / "eia_plan.json")

    for py in sorted(SRC_NOTEBOOKS.glob("*.py")):
        destino = salida / "notebooks" / f"{py.stem}.ipynb"
        _escribir_json(destino, a_ipynb(py.read_text(encoding="utf-8")))
        escritos.append(destino)
    return escritos


if __name__ == "__main__":
    for p in generar():
        print(f"generado: {p.relative_to(RAIZ)}")
    sys.exit(0)
