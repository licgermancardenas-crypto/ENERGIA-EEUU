"""Genera el informe Power BI (formato PBIR) de 5 páginas sobre el modelo sm_pulso_energetico.

Sigue la §5 de powerbi/ESPECIFICACION_POWERBI.md con visuales nativos. Los visuales
*HTML Content* (AppSource) no se pueden instalar por CLI: los banners se reemplazan por
tarjetas y cuadros de texto. Uso:

    python scripts/generar_informe.py --workspace "<nombre>" --model-id <id> --out <carpeta>
    fab import "<ws>.Workspace/Pulso Energetico EEUU.Report" -i <carpeta>/rp_pulso.Report -f
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TEMA = RAIZ / "powerbi" / "tema_pulso_energetico.json"
MED = "dim_serie"  # tabla que aloja las medidas (ver generar_modelo_semantico.py)
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
NOMBRE = "rp_pulso"

W, H, M = 1280, 720, 24


# ---------- campos ----------
def medida(nombre: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MED}}, "Property": nombre}}


def columna(tabla: str, col: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": col}}


def proy(campo: dict) -> dict:
    k = "Measure" if "Measure" in campo else "Column"
    ent = campo[k]["Expression"]["SourceRef"]["Entity"]
    prop = campo[k]["Property"]
    return {"field": campo, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}


def lit(v) -> dict:
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def filtro_en(tabla: str, col: str, valores: list[str], nombre: str) -> dict:
    return {
        "name": nombre, "field": columna(tabla, col), "type": "Categorical",
        "filter": {"Version": 2, "From": [{"Name": "t", "Entity": tabla, "Type": 0}],
                   "Where": [{"Condition": {"In": {
                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}},
                                                   "Property": col}}],
                       "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in valores]}}}]},
    }


# ---------- visuales ----------
class Pagina:
    def __init__(self, nombre: str, titulo: str):
        self.nombre, self.titulo, self.visuales = nombre, titulo, []

    def _agregar(self, x, y, w, h, visual, titulo=None, filtros=None):
        n = f"{self.nombre}_v{len(self.visuales):02d}"
        cont = {"$schema": f"{SCH}/visualContainer/1.0.0/schema.json", "name": n,
                "position": {"x": x, "y": y, "z": len(self.visuales), "width": w, "height": h},
                "visual": visual}
        if titulo:
            visual["visualContainerObjects"] = {"title": [{"properties": {
                "show": lit(True), "text": lit(titulo)}}]}
        if filtros:
            cont["filterConfig"] = {"filters": filtros}
        self.visuales.append(cont)

    def texto(self, x, y, w, h, texto, tam=11, negrita=False):
        estilo = {"fontSize": f"{tam}pt"} | ({"fontWeight": "bold"} if negrita else {})
        self._agregar(x, y, w, h, {"visualType": "textbox", "objects": {"general": [{"properties": {
            "paragraphs": [{"textRuns": [{"value": p, "textStyle": estilo}]}
                           for p in texto.split("\n")]}}]}})

    def tarjeta(self, x, y, w, h, m, titulo=None):
        self._agregar(x, y, w, h, {"visualType": "card", "query": {"queryState": {
            "Values": {"projections": [proy(medida(m))]}}}}, titulo or m)

    def grafico(self, tipo, x, y, w, h, eje, valores, titulo, serie=None, filtros=None):
        qs = {"Category": {"projections": [proy(eje)]},
              "Y": {"projections": [proy(medida(v)) for v in valores]}}
        if serie:
            qs["Series"] = {"projections": [proy(serie)]}
        self._agregar(x, y, w, h, {"visualType": tipo, "query": {"queryState": qs}}, titulo,
                      filtros)

    def segmentador(self, x, y, w, h, campo, titulo):
        self._agregar(x, y, w, h, {"visualType": "slicer", "query": {"queryState": {
            "Values": {"projections": [proy(campo)]}}}}, titulo)

    def tabla(self, x, y, w, h, campos, titulo):
        self._agregar(x, y, w, h, {"visualType": "tableEx", "query": {"queryState": {
            "Values": {"projections": [proy(c) for c in campos]}}}}, titulo)

    def encabezado(self):
        self.texto(M, 12, 760, 44, self.titulo, tam=20, negrita=True)
        self.tarjeta(800, 12, W - 800 - M, 52, "Estado de los datos", "Fuente: EIA, API v2")


def paginas() -> list[Pagina]:
    F, S, R = "dim_fecha", "dim_serie", "dim_region"
    ps = []

    p = Pagina("resumen", "Pulso energético de EE. UU. — El pulso hoy")
    p.encabezado()
    cw, y = (W - 2 * M - 3 * 16) // 4, 84
    for i, m in enumerate(["Último WTI", "WTI vs promedio 12 meses %", "Diferencial Brent-WTI",
                           "Stock crudo comercial"]):
        p.tarjeta(M + i * (cw + 16), y, cw, 120, m)
    for i, m in enumerate(["Último Henry Hub", "Henry Hub vs promedio 12 meses %",
                           "Gas almacenado Lower 48", "Participación generación eléctrica %"]):
        p.tarjeta(M + i * (cw + 16), y + 136, cw, 120, m)
    for i, m in enumerate(["Crudo comercial vs año anterior %", "Almacenamiento vs año anterior %",
                           "Inyección neta semanal", "Último mes de producción"]):
        p.tarjeta(M + i * (cw + 16), y + 272, cw, 120, m)
    p.texto(M, y + 412, W - 2 * M, 150,
            "Cada tarjeta muestra el último dato publicado de su serie.\n"
            "Precios en US$ (barril o MMBtu); inventarios en miles de barriles; gas en Bcf.\n"
            "Datos: U.S. Energy Information Administration (EIA), API v2. Autor: German Cardenas.",
            tam=10)
    ps.append(p)

    p = Pagina("petroleo", "Petróleo")
    p.encabezado()
    p.segmentador(M, 76, 180, 300, columna(F, "anio"), "Año")
    p.grafico("lineChart", 220, 76, 640, 300, columna(F, "fecha"), ["Precio WTI", "Precio Brent"],
              "Precio spot WTI y Brent (US$/barril)")
    p.grafico("clusteredBarChart", 876, 76, W - 876 - M, 300, columna(S, "nombre"),
              ["Último valor"], "Precio en surtidor, última semana (US$/galón)",
              filtros=[filtro_en(S, "categoria", ["precio_surtidor"], "f_surtidor")])
    p.grafico("lineChart", M, 392, 600, 300, columna(F, "fecha"),
              ["Stock crudo comercial", "Stock SPR"], "Inventarios de crudo (miles de barriles)")
    p.grafico("lineChart", 640, 392, W - 640 - M, 300, columna(F, "anio_mes"),
              ["Producción de crudo"], "Producción de crudo (miles de barriles por día)")
    ps.append(p)

    p = Pagina("gas", "Gas natural")
    p.encabezado()
    p.segmentador(M, 76, 180, 300, columna(F, "anio"), "Año")
    p.grafico("lineChart", 220, 76, 600, 300, columna(F, "fecha"), ["Precio Henry Hub"],
              "Precio Henry Hub (US$/MMBtu)")
    p.grafico("clusteredBarChart", 836, 76, W - 836 - M, 300, columna(R, "nombre"),
              ["Gas almacenado por región"], "Gas almacenado por región, última semana (Bcf)",
              filtros=[filtro_en(R, "tipo", ["region_almacenamiento"], "f_region")])
    p.grafico("hundredPercentStackedColumnChart", M, 392, 600, 300, columna(F, "anio"),
              ["Consumo por sector"], "Consumo de gas por sector (participación anual)",
              serie=columna(S, "nombre"),
              filtros=[filtro_en(S, "categoria", ["consumo"], "f_consumo")])
    p.grafico("lineChart", 640, 392, 420, 300, columna(F, "fecha"), ["Gas almacenado Lower 48"],
              "Gas almacenado Lower 48 (Bcf)")
    for i, m in enumerate(["Inyección neta semanal", "Producción de gas seco",
                           "Consumo total de gas"]):
        p.tarjeta(1076, 392 + i * 104, W - 1076 - M, 92, m)
    ps.append(p)

    p = Pagina("rezago", "¿Cuánto tarda la producción en reaccionar al precio?")
    p.encabezado()
    p.segmentador(M, 76, 260, 110, columna("analisis_rezago", "escenario"), "Escenario")
    p.tarjeta(300, 76, 220, 110, "Rezago óptimo (meses)")
    p.tarjeta(536, 76, 220, 110, "Correlación en el óptimo")
    p.tarjeta(772, 76, W - 772 - M, 110, "Texto rezago", "Lectura")
    p.grafico("clusteredColumnChart", M, 200, 600, 260, columna("analisis_rezago", "rezago_meses"),
              ["Correlación"], "Correlación WTI → producción según meses de rezago")
    p.texto(640, 200, W - 640 - M, 260,
            "Comparamos la variación mensual del WTI con la de la producción de crudo entre 0 y 12 "
            "meses después. Lo calculamos de dos maneras porque 2020 fue un año extremo: precio y "
            "producción se desplomaron y rebotaron casi a la vez. Que el resultado cambie tanto "
            "entre escenarios muestra que ninguna de las dos cifras es una regla fija.\n"
            "Es correlación, no causalidad.", tam=11)
    p.grafico("lineChart", M, 476, 600, 220, columna(F, "anio_mes"), ["Precio WTI mensual"],
              "Precio WTI mensual (US$/barril)")
    p.grafico("lineChart", 640, 476, W - 640 - M, 220, columna(F, "anio_mes"),
              ["Producción de crudo"], "Producción de crudo (miles de barriles por día)")
    ps.append(p)

    p = Pagina("calidad", "Calidad de los datos")
    p.encabezado()
    cw = (W - 2 * M - 2 * 16) // 3
    for i, m in enumerate(["Fuentes al día", "Fuentes atrasadas", "Máximo atraso (días)"]):
        p.tarjeta(M + i * (cw + 16), 76, cw, 110, m)
    fr = "frescura"
    p.tabla(M, 202, W - 2 * M, 494,
            [columna(fr, "dataset"), columna(fr, "frecuencia"), columna(fr, "ultimo_periodo"),
             columna(fr, "dias_atraso"), columna(fr, "umbral_dias"), medida("Icono de estado")],
            "Frescura de cada fuente")
    ps.append(p)
    return ps


def generar(workspace: str, model_id: str, out: Path) -> Path:
    raiz = out / f"{NOMBRE}.Report"
    if raiz.exists():
        shutil.rmtree(raiz)
    d = raiz / "definition"
    (d / "pages").mkdir(parents=True)

    def escribir(ruta: Path, obj) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    escribir(raiz / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "Pulso Energetico EEUU"},
        "config": {"version": "2.0", "logicalId": "6f1e9a52-6c1b-4f3e-9d0a-5b8f2c7e4a10"}})
    escribir(raiz / "definition.pbir", {"version": "4.0", "datasetReference": {"byConnection": {
        "connectionString": f'Data Source="powerbi://api.powerbi.com/v1.0/myorg/{workspace}";'
                            f"initial catalog=sm_pulso_energetico;integrated security=ClaimsToken;"
                            f"semanticmodelid={model_id}",
        "pbiServiceModelId": None, "pbiModelVirtualServerName": "sobe_wowvirtualserver",
        "pbiModelDatabaseName": model_id, "name": "EntityDataSource",
        "connectionType": "pbiServiceXmlaStyleLive"}}})
    escribir(d / "version.json", {"$schema": f"{SCH}/versionMetadata/1.0.0/schema.json",
                                  "version": "2.0.0"})
    tema = "tema_pulso_energetico.json"
    escribir(d / "report.json", {
        "$schema": f"{SCH}/report/1.0.0/schema.json",
        "themeCollection": {"customTheme": {"name": tema, "reportVersionAtImport": "5.59",
                                            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": tema, "path": tema, "type": "CustomTheme"}]}],
        "layoutOptimization": "None",
        "settings": {"useStylableVisualContainerHeader": True,
                     "defaultDrillFilterOtherVisuals": True}})
    dst = raiz / "StaticResources" / "RegisteredResources" / tema
    dst.parent.mkdir(parents=True)
    shutil.copy(TEMA, dst)

    ps = paginas()
    escribir(d / "pages" / "pages.json", {"$schema": f"{SCH}/pagesMetadata/1.0.0/schema.json",
                                          "pageOrder": [p.nombre for p in ps],
                                          "activePageName": ps[0].nombre})
    nombres = {"resumen": "Resumen", "petroleo": "Petróleo", "gas": "Gas", "rezago": "Rezago",
               "calidad": "Calidad"}
    for p in ps:
        base = d / "pages" / p.nombre
        escribir(base / "page.json", {"$schema": f"{SCH}/page/1.0.0/schema.json",
                                      "name": p.nombre, "displayName": nombres[p.nombre],
                                      "displayOption": "FitToPage", "height": H, "width": W})
        for v in p.visuales:
            escribir(base / "visuals" / v["name"] / "visual.json", v)
    return raiz


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    print(f"informe -> {generar(a.workspace, a.model_id, a.out)}")
