"""Genera powerbi/medidas.dax desde la especificación (fuente única de las medidas).

El archivo resultante se pega en Power BI Desktop → Vista de consultas DAX y se aplica con
"Actualizar modelo con cambios": crea o reemplaza todas las medidas en la tabla `_Medidas`.

Uso:  python scripts/generar_powerbi.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SPEC = RAIZ / "powerbi" / "ESPECIFICACION_POWERBI.md"
SALIDA = RAIZ / "powerbi" / "medidas.dax"
TABLA_MEDIDAS = "_Medidas"

CABECERA = re.compile(r"^(?!VAR\b|RETURN\b|--)(?P<nombre>\S.*?) =\s*$")
SECCION = re.compile(r"^### 4\.\d+ (?P<carpeta>.+)$")

# Medidas que se evalúan al final del archivo como prueba rápida (ver §8 de la especificación).
PRUEBA = ["Último WTI", "WTI vs promedio 12 meses %", "Diferencial Brent-WTI", "Último Henry Hub",
          "Stock crudo comercial", "Gas almacenado Lower 48",
          "Participación generación eléctrica %", "Fuentes al día"]


@dataclass
class Medida:
    nombre: str
    expresion: str
    carpeta: str


def leer_medidas(texto: str) -> list[Medida]:
    medidas: list[Medida] = []
    carpeta, en_dax, actual = "", False, None
    for linea in texto.splitlines():
        m = SECCION.match(linea)
        if m and not en_dax:
            carpeta = m.group("carpeta").strip()
            continue
        if linea.strip() == "```dax":
            en_dax, actual = True, None
            continue
        if en_dax and linea.strip() == "```":
            en_dax = False
            continue
        if not en_dax:
            continue
        c = CABECERA.match(linea)
        if c:
            actual = Medida(c.group("nombre"), "", carpeta)
            medidas.append(actual)
        elif actual is not None:
            actual.expresion += linea + "\n"
    for m in medidas:
        m.expresion = m.expresion.strip("\n")
    return medidas


def a_query_view(medidas: list[Medida]) -> str:
    out = [
        "// Generado desde powerbi/ESPECIFICACION_POWERBI.md con scripts/generar_powerbi.py.",
        "// No editar a mano: cambiá la especificación y volvé a generar.",
        "// Uso: Power BI Desktop → Vista de consultas DAX → pegar →",
        "//      \"Actualizar modelo con cambios\".",
        f"// Requiere una tabla '{TABLA_MEDIDAS}' en el modelo (ver §2 de la especificación).",
        "",
        "DEFINE",
    ]
    carpeta = None
    for m in medidas:
        if m.carpeta != carpeta:
            carpeta = m.carpeta
            out += ["", f"    // ---- {carpeta}"]
        out.append(f"    MEASURE '{TABLA_MEDIDAS}'[{m.nombre}] =")
        out += [f"        {linea}" if linea.strip() else "" for linea in m.expresion.splitlines()]
    out += ["", "EVALUATE", "ROW ("]
    out.append(",\n".join(f'    "{n}", [{n}]' for n in PRUEBA))
    out += [")", ""]
    return "\n".join(out)


def generar(spec: Path = SPEC, salida: Path = SALIDA) -> list[Medida]:
    medidas = leer_medidas(spec.read_text(encoding="utf-8"))
    salida.write_text(a_query_view(medidas), encoding="utf-8")
    return medidas


if __name__ == "__main__":
    ms = generar()
    print(f"{len(ms)} medidas -> {SALIDA.relative_to(RAIZ)}")
    sys.exit(0)
