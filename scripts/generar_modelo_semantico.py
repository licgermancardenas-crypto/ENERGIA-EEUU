"""Genera el modelo semántico Direct Lake (TMDL) desde la especificación de Power BI.

Toma las tablas y relaciones de la §2 y las 55 medidas de la §4 de
powerbi/ESPECIFICACION_POWERBI.md, y escribe una carpeta `<nombre>.SemanticModel`
importable con la Fabric CLI:

    python scripts/generar_modelo_semantico.py --server <host SQL endpoint> \
        --endpoint-id <id SQL endpoint> --out <carpeta>
    fab import "<workspace>.Workspace/sm_pulso_energetico.SemanticModel" \
        -i <carpeta>/sm_pulso_energetico.SemanticModel -f

El host y el id salen de `fab get "<ws>.Workspace/<lh>.Lakehouse" -q properties`
(sqlEndpointProperties). No son secretos, pero dependen del tenant: por eso no se
versiona la salida.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generar_iconos as gi  # noqa: E402
import generar_powerbi as gp  # noqa: E402

NOMBRE = "sm_pulso_energetico"
CARPETA_IMAGENES = "Íconos e imágenes"  # medidas de dax/iconos.dax, categoría Image URL
TABLA_MEDIDAS = "dim_serie"  # Direct Lake no admite tablas calculadas ni "Enter data" (spec §2.4)

FACT_COLS = [("fecha_key", "int64"), ("fecha", "dateTime"), ("serie_key", "string"),
             ("region_key", "string"), ("valor", "double")]
FACTS = ["fact_precios_diarios", "fact_precios_mensuales", "fact_precio_surtidor_semanal",
         "fact_inventarios_semanales", "fact_almacenamiento_gas_semanal",
         "fact_consumo_gas_mensual", "fact_produccion_mensual"]

TABLAS: dict[str, list[tuple[str, str]]] = {
    "dim_fecha": [("fecha_key", "int64"), ("fecha", "dateTime"), ("anio", "int64"),
                  ("trimestre", "int64"), ("mes", "int64"), ("nombre_mes", "string"),
                  ("anio_mes", "string"), ("semana_iso", "int64"), ("dia_semana", "int64"),
                  ("nombre_dia", "string"), ("es_fin_de_semana", "boolean")],
    "dim_serie": [("serie_key", "string"), ("serie_eia", "string"), ("nombre", "string"),
                  ("descripcion_eia", "string"), ("unidad", "string"), ("frecuencia", "string"),
                  ("dataset", "string"), ("sector", "string"), ("categoria", "string"),
                  ("tabla_gold", "string"), ("region_key", "string"), ("orden", "int64")],
    "dim_region": [("region_key", "string"), ("nombre", "string"), ("tipo", "string")],
    **{f: FACT_COLS for f in FACTS},
    "fact_ultimo_dato": FACT_COLS + [("fecha_anterior", "dateTime"), ("valor_anterior", "double"),
                                     ("variacion_abs", "double"), ("variacion_pct", "double")],
    "frescura": [("dataset", "string"), ("sector", "string"), ("categoria", "string"),
                 ("frecuencia", "string"), ("ultimo_periodo", "dateTime"),
                 ("fin_periodo", "dateTime"), ("dias_atraso", "int64"), ("umbral_dias", "int64"),
                 ("estado", "string"), ("filas_silver", "int64"), ("calculado_al", "dateTime")],
    "analisis_rezago": [("rezago_meses", "int64"), ("correlacion", "double"), ("n_obs", "int64"),
                        ("desde", "string"), ("hasta", "string"), ("escenario", "string")],
}

ORDENAR_POR = {("dim_fecha", "nombre_mes"): "mes", ("dim_fecha", "nombre_dia"): "dia_semana",
               ("dim_serie", "nombre"): "orden"}

FORMATO_CARPETA = {
    "Precios spot": "#,0.00", "Combustibles en surtidor": "#,0.000",
    "Inventarios de petróleo": "#,0", "Almacenamiento de gas": "#,0", "Producción": "#,0",
    "Consumo de gas": "#,0", "Último dato (tarjetas)": "#,0.00", "Frescura y calidad": "0",
}
FORMATO_NOMBRE: dict[str, str | None] = {
                  "Correlación": "0.000", "Correlación en el óptimo": "0.000",
                  "Rezago óptimo (meses)": "0", "Es rezago óptimo": "0",
                  "Último mes de producción": "mmmm yyyy", "Fecha del último dato": "dd/mm/yyyy",
                  "Color barra rezago": None}


def relaciones() -> list[tuple[str, str, str, str]]:
    rels = []
    for f in FACTS:
        rels += [(f, "fecha_key", "dim_fecha", "fecha_key"),
                 (f, "serie_key", "dim_serie", "serie_key"),
                 (f, "region_key", "dim_region", "region_key")]
    rels.append(("fact_ultimo_dato", "serie_key", "dim_serie", "serie_key"))
    return rels


def q(nombre: str) -> str:
    """Nombre TMDL: entre comillas simples si no es un identificador simple."""
    if nombre.replace("_", "").isalnum() and nombre.isascii() and not nombre[0].isdigit():
        return nombre
    return "'" + nombre.replace("'", "''") + "'"


def formato(m: gp.Medida) -> str | None:
    if m.carpeta == CARPETA_IMAGENES:
        return None
    if m.nombre in FORMATO_NOMBRE:
        return FORMATO_NOMBRE[m.nombre]
    expr = m.expresion
    if "FORMAT (" in expr or "FORMAT(" in expr or '"<' in expr or m.carpeta.startswith("HTML"):
        return None  # medida de texto
    if m.nombre.endswith("%"):
        return "0.0 %"
    return FORMATO_CARPETA.get(m.carpeta, "#,0.00")


def tabla_tmdl(nombre: str, cols: list[tuple[str, str]], medidas: list[gp.Medida]) -> str:
    out = [f"table {nombre}"]
    if nombre == "dim_fecha":
        out.append("\tdataCategory: Time")
    out.append(f"\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, nombre)}")
    out.append("")
    for m in medidas:
        out.append(f"\tmeasure {q(m.nombre)} = ```")
        out += [f"\t\t\t{linea}" for linea in m.expresion.splitlines()]
        out.append("\t\t\t```")
        f = formato(m)
        if f:
            out.append(f"\t\tformatString: {f}")
        out.append(f"\t\tdisplayFolder: {m.carpeta}")
        if m.carpeta == CARPETA_IMAGENES:
            out.append("\t\tdataCategory: ImageUrl")
        out.append(f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, nombre + '/m/' + m.nombre)}")
        out.append("")
    for col, tipo in cols:
        out.append(f"\tcolumn {col}")
        out.append(f"\t\tdataType: {tipo}")
        if nombre == "dim_fecha" and col == "fecha":
            out.append("\t\tisKey")
        if tipo == "dateTime":
            out.append("\t\tformatString: dd/mm/yyyy")
        oculta = col.endswith("_key") or (nombre.startswith("fact_") and col == "valor")
        if oculta:
            out.append("\t\tisHidden")
        resumir = tipo == "double" and not nombre.startswith("dim_") and col != "correlacion"
        out.append(f"\t\tsummarizeBy: {'sum' if resumir else 'none'}")
        out.append(f"\t\tsourceColumn: {col}")
        if (nombre, col) in ORDENAR_POR:
            out.append(f"\t\tsortByColumn: {ORDENAR_POR[(nombre, col)]}")
        out.append(f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, nombre + '/c/' + col)}")
        out.append("")
    out += [f"\tpartition {nombre} = entity", "\t\tmode: directLake", "\t\tsource",
            f"\t\t\tentityName: {nombre}", "\t\t\tschemaName: dbo",
            "\t\t\texpressionSource: DatabaseQuery", ""]
    return "\n".join(out)


def todas_las_medidas() -> list[gp.Medida]:
    """Las de la especificación más las de íconos (dax/iconos.dax), sin repetir nombres."""
    base = gp.leer_medidas(gp.SPEC.read_text(encoding="utf-8"))
    iconos = [gp.Medida(m.nombre, m.expresion, CARPETA_IMAGENES) for m in gi.medidas()]
    nombres = [m.nombre for m in base + iconos]
    assert len(nombres) == len(set(nombres)), "nombre de medida repetido"
    return base + iconos


def generar(server: str, endpoint_id: str, out: Path) -> Path:
    medidas = todas_las_medidas()
    raiz = out / f"{NOMBRE}.SemanticModel"
    d = raiz / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    (raiz / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, NOMBRE))}},
        indent=2), encoding="utf-8")
    (raiz / "definition.pbism").write_text(json.dumps({"version": "4.0", "settings": {}}, indent=2),
                                           encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1604\n", encoding="utf-8")
    refs = "\n".join(f"ref table {q(t)}" for t in TABLAS)
    (d / "model.tmdl").write_text(
        "model Model\n\tculture: es-AR\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: es-AR\n\tdataAccessOptions\n\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n\n" + refs + "\n", encoding="utf-8")
    (d / "expressions.tmdl").write_text(
        "expression DatabaseQuery =\n\t\tlet\n"
        f'\t\t\tdatabase = Sql.Database("{server}", "{endpoint_id}")\n'
        "\t\tin\n\t\t\tdatabase\n"
        f"\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, 'DatabaseQuery')}\n", encoding="utf-8")
    rels = []
    for desde, cd, hacia, ch in relaciones():
        rels += [f"relationship {uuid.uuid5(uuid.NAMESPACE_URL, f'{desde}.{cd}->{hacia}')}",
                 f"\tfromColumn: {desde}.{cd}", f"\ttoColumn: {hacia}.{ch}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rels), encoding="utf-8")
    for t, cols in TABLAS.items():
        ms = medidas if t == TABLA_MEDIDAS else []
        (d / "tables" / f"{t}.tmdl").write_text(tabla_tmdl(t, cols, ms), encoding="utf-8")
    return raiz


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", required=True)
    ap.add_argument("--endpoint-id", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    r = generar(a.server, a.endpoint_id, a.out)
    print(f"modelo -> {r}")
