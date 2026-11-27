"""Sube las tablas Gold geoespaciales al Lakehouse de Fabric y las carga como tablas Delta.

Requiere la Fabric CLI (`pip install ms-fabric-cli`) con sesión iniciada (`fab auth login`).
Cada tabla va a Files/gold/geo/<tabla>/<tabla>.parquet y se carga en Tables/<tabla>
(modo overwrite). Las tablas vacías (por ejemplo, si la API de la EIA no respondió) también
se cargan, para que el modelo semántico conserve su estructura.

Uso:
    python scripts/publicar_geo_fabric.py --workspace "Pulso Energetico EEUU" \
        --lakehouse lh_pulso_energetico [--fab ruta/a/fab]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "data" / "gold" / "geo"
TABLAS = ["geo_dim_estado", "geo_estado_metricas", "geo_km_estado_operador",
          "geo_henry_hub_conexiones", "geo_gnl", "geo_hubs", "geo_reserva_estrategica",
          "geo_flujos_estado", "geo_centrales", "geo_capas_mapa", "frescura_geo"]


def _fab(fab: str, *args: str) -> str:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    r = subprocess.run([fab, *args], capture_output=True, text=True, encoding="utf-8", env=env)
    salida = (r.stdout + r.stderr).strip()
    if r.returncode != 0 and "already exists" not in salida:
        raise RuntimeError(f"fab {' '.join(args)} falló: {salida[-400:]}")
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--lakehouse", default="lh_pulso_energetico")
    ap.add_argument("--fab", default=shutil.which("fab") or "fab")
    a = ap.parse_args()
    lh = f"{a.workspace}.Workspace/{a.lakehouse}.Lakehouse"
    faltan = [t for t in TABLAS if not (GOLD / f"{t}.parquet").exists()]
    if faltan:
        print(f"Faltan tablas Gold: {faltan}. Corré `python -m eia_pulso geo`.")
        return 1
    _fab(a.fab, "mkdir", f"{lh}/Files/gold/geo")
    for t in TABLAS:
        _fab(a.fab, "mkdir", f"{lh}/Files/gold/geo/{t}")
        _fab(a.fab, "cp", str(GOLD / f"{t}.parquet"), f"{lh}/Files/gold/geo/{t}/{t}.parquet",
             "-f")
        _fab(a.fab, "table", "load", f"{lh}/Tables/{t}", "--file", f"{lh}/Files/gold/geo/{t}",
             "--format", "format=parquet", "--mode", "overwrite")
        print(f"  {t}: cargada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
