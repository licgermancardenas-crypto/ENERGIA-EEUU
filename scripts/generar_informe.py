"""Genera el informe Power BI (formato PBIR) de 5 páginas sobre el modelo sm_pulso_energetico.

Sigue la §5 de powerbi/ESPECIFICACION_POWERBI.md con visuales nativos: banda de encabezado,
navegación entre páginas, tarjetas KPI con jerarquía y gráficos con la paleta del proyecto.
Los visuales *HTML Content* (AppSource) no se pueden instalar por CLI. Uso:

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

W, H, M, G = 1280, 720, 24, 16
BANDA = 92  # alto de la banda de encabezado
Y0 = BANDA + 16  # primera fila de contenido
ALTO_KPI = 100
FIN = H - 30  # borde inferior del contenido (debajo va el pie)
PIE = ("Fuente: U.S. Energy Information Administration (EIA) · API v2 · "
       "Autor: Germán Cárdenas")
PAGINAS = [("resumen", "Resumen"), ("petroleo", "Petróleo"), ("gas", "Gas"),
           ("rezago", "Rezago"), ("calidad", "Calidad")]

# Paleta (misma que la web y el tema)
NAVY, NAVY_2 = "#0B1F3A", "#16335C"
AZUL, NARANJA, VIOLETA, OCRE = "#1F6FD1", "#C4531A", "#7A45C2", "#A87D00"
VERDE, ALERTA, ERROR = "#1D7A3B", "#A35400", "#B42318"
TINTA, TINTA_2, TINTA_3 = "#1B1F24", "#4A5260", "#7A8394"
BLANCO, PAPEL, LINEA = "#FFFFFF", "#F4F1EA", "#E4DED2"
FUENTE, FUENTE_FUERTE = "Segoe UI", "Segoe UI Semibold"
SEL_DEF, SEL_HOVER, SEL_SEL = {"id": "default"}, {"id": "hover"}, {"id": "selected"}


# ---------- expresiones ----------
def lit(v) -> dict:
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, int):
        return {"expr": {"Literal": {"Value": f"{v}L"}}}
    if isinstance(v, float):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def color(hex_: str) -> dict:
    return {"solid": {"color": lit(hex_)}}


def medida(nombre: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MED}}, "Property": nombre}}


def columna(tabla: str, col: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": col}}


def proy(campo: dict, alias: str | None = None) -> dict:
    k = "Measure" if "Measure" in campo else "Column"
    ent = campo[k]["Expression"]["SourceRef"]["Entity"]
    prop = campo[k]["Property"]
    p = {"field": campo, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if alias:
        p["displayName"] = alias
    return p


def _col_src(col: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": col}}


def filtro_en(tabla: str, col: str, valores: list[str], nombre: str) -> dict:
    return {"name": nombre, "field": columna(tabla, col), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": tabla, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [_col_src(col)],
                           "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in valores]}}}]}}


def filtro_desde(tabla: str, col: str, minimo: int, nombre: str) -> dict:
    """col >= minimo (saca el miembro en blanco de los segmentadores de año)."""
    return {"name": nombre, "field": columna(tabla, col), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": tabla, "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {
                           "ComparisonKind": 2, "Left": _col_src(col),
                           "Right": {"Literal": {"Value": f"{minimo}L"}}}}}]}}


# ---------- estilo de contenedores ----------
def contenedor(titulo: str | None = None, subtitulo: str | None = None, fondo: str = BLANCO,
               borde: bool = True, sombra: bool = True, radio: int = 12) -> dict:
    o: dict = {
        "background": [{"properties": {"show": lit(True), "color": color(fondo),
                                       "transparency": lit(0.0)}}],
        "border": [{"properties": {"show": lit(borde), "color": color(LINEA),
                                   "radius": lit(float(radio))}}],
        "dropShadow": [{"properties": {"show": lit(sombra), "color": color("#0B1F3A"),
                                       "transparency": lit(88.0), "preset": lit("BottomRight")}}],
        "padding": [{"properties": {"top": lit(10.0), "bottom": lit(10.0), "left": lit(14.0),
                                    "right": lit(14.0)}}],
        "visualHeader": [{"properties": {"show": lit(False)}}],
    }
    if titulo:
        o["title"] = [{"properties": {"show": lit(True), "text": lit(titulo),
                                      "fontColor": color(TINTA), "fontSize": lit(12.0),
                                      "fontFamily": lit(FUENTE_FUERTE), "bold": lit(False)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    if subtitulo:
        o["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitulo),
                                         "fontColor": color(TINTA_3), "fontSize": lit(9.0)}}]
    return o


def ejes_limpios(leyenda: bool = True) -> dict:
    return {
        "legend": [{"properties": {"show": lit(leyenda), "position": lit("Top"),
                                   "showTitle": lit(False), "fontSize": lit(9.0),
                                   "labelColor": color(TINTA_2)}}],
        "categoryAxis": [{"properties": {"showAxisTitle": lit(False), "fontSize": lit(9.0),
                                         "labelColor": color(TINTA_3)}}],
        "valueAxis": [{"properties": {"showAxisTitle": lit(False), "fontSize": lit(9.0),
                                      "labelColor": color(TINTA_3), "gridlineShow": lit(True),
                                      "gridlineColor": color("#ECE7DD")}}],
    }


# ---------- páginas ----------
class Pagina:
    def __init__(self, nombre: str, menu: str, titulo: str, bajada: str):
        self.nombre, self.menu, self.titulo, self.bajada = nombre, menu, titulo, bajada
        self.visuales: list[dict] = []

    def _agregar(self, x, y, w, h, visual, filtros=None):
        n = f"{self.nombre}_v{len(self.visuales):02d}"
        cont = {"$schema": f"{SCH}/visualContainer/1.0.0/schema.json", "name": n,
                "position": {"x": x, "y": y, "z": len(self.visuales) * 1000, "width": w,
                             "height": h},
                "visual": visual}
        if filtros:
            cont["filterConfig"] = {"filters": filtros}
        self.visuales.append(cont)

    # -- piezas
    def texto(self, x, y, w, h, parrafos: list[tuple[str, float, str, bool]], fondo=None):
        """parrafos: (texto, tamaño pt, color, negrita)."""
        runs = [{"textRuns": [{"value": t, "textStyle": {
            "fontSize": f"{tam}pt", "color": col,
            "fontFamily": FUENTE_FUERTE if neg else FUENTE}}]} for t, tam, col, neg in parrafos]
        tarjeta = fondo == BLANCO
        vco = contenedor(fondo=fondo or BLANCO, borde=tarjeta, sombra=tarjeta,
                         radio=12 if tarjeta else 0)
        if not tarjeta:
            vco["padding"] = [{"properties": {"top": lit(0.0), "bottom": lit(0.0),
                                              "left": lit(0.0), "right": lit(0.0)}}]
        if fondo is None:
            vco["background"] = [{"properties": {"show": lit(False)}}]
        general = [{"properties": {"paragraphs": runs}}]
        v = {"visualType": "textbox", "objects": {"general": general},
             "visualContainerObjects": vco}
        self._agregar(x, y, w, h, v)

    def imagen(self, x, y, w, h, m: str, titulo=None, subtitulo=None, pagina: str | None = None,
               tarjeta=False):
        """Visual de imagen cuya URL sale de una medida (data URI SVG de dax/iconos.dax)."""
        if tarjeta:
            vco = contenedor(titulo, subtitulo)
        else:
            vco = {"background": [{"properties": {"show": lit(False)}}],
                   "title": [{"properties": {"show": lit(False)}}],
                   "border": [{"properties": {"show": lit(False)}}],
                   "dropShadow": [{"properties": {"show": lit(False)}}],
                   "visualHeader": [{"properties": {"show": lit(False)}}],
                   "padding": [{"properties": {"top": lit(0.0), "bottom": lit(0.0),
                                               "left": lit(0.0), "right": lit(0.0)}}]}
        if pagina:
            vco["visualLink"] = [{"properties": {"show": lit(True), "type": lit("PageNavigation"),
                                                 "navigationSection": lit(pagina)}}]
        self._agregar(x, y, w, h, {
            "visualType": "image",
            "objects": {"general": [{"properties": {"imageUrl": {"expr": medida(m)}}}]},
            "visualContainerObjects": vco})

    def icono_titulo(self, x, y, w, m: str):
        """Ícono de 20 px en la esquina superior derecha de un contenedor."""
        self.imagen(x + w - 38, y + 12, 22, 22, m)

    def kpi(self, x, y, w, h, m, etiqueta, nota, acento=AZUL, tam=26.0, icono: str | None = None):
        objs = {
            "labels": [{"properties": {"fontSize": lit(tam), "color": color(TINTA),
                                       "fontFamily": lit(FUENTE_FUERTE),
                                       "labelDisplayUnits": lit(1.0)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}],
            "wordWrap": [{"properties": {"show": lit(True)}}],
        }
        vco = contenedor(etiqueta.upper(), nota)
        vco["title"][0]["properties"].update({"fontSize": lit(9.0), "fontColor": color(acento),
                                              "fontFamily": lit(FUENTE_FUERTE)})
        vco["border"] = [{"properties": {"show": lit(True), "color": color(LINEA),
                                         "radius": lit(12.0)}}]
        self._agregar(x, y, w, h, {"visualType": "card", "query": {"queryState": {
            "Values": {"projections": [proy(medida(m))]}}}, "objects": objs,
            "visualContainerObjects": vco})
        if icono:
            self.icono_titulo(x, y, w, icono)

    def nota(self, x, y, w, icono: str, texto: str, color_txt: str = TINTA_2):
        """Anotación fija: ícono de 16 px + texto breve (va dentro de un contenedor)."""
        self.imagen(x, y + 1, 16, 16, icono)
        self.texto(x + 22, y, w - 22, 20, [(texto, 9, color_txt, False)])

    def grafico(self, tipo, x, y, w, h, eje, valores, titulo, subtitulo=None, serie=None,
                filtros=None, etiquetas=False, leyenda=True, colores=None, relleno=None,
                por_categoria: dict[str, str] | None = None):
        qs = {"Category": {"projections": [proy(eje)]},
              "Y": {"projections": [proy(medida(v)) for v in valores]}}
        if serie:
            qs["Series"] = {"projections": [proy(serie)]}
        objs = ejes_limpios(leyenda and (len(valores) > 1 or serie is not None))
        if tipo == "lineChart":
            objs["lineStyles"] = [{"properties": {"strokeWidth": lit(2.0)}}]
        if etiquetas:
            objs["labels"] = [{"properties": {"show": lit(True), "fontSize": lit(9.0),
                                              "color": color(TINTA_2)}}]
        if colores:
            objs["dataPoint"] = [{"properties": {"fill": color(c)},
                                  "selector": {"metadata": f"{MED}.{v}"}}
                                 for v, c in zip(valores, colores, strict=True)]
        if por_categoria:  # un color por valor del eje (p. ej. diésel vs. gasolinas)
            col = eje["Column"]
            objs["dataPoint"] = [{"properties": {"fill": color(c)}, "selector": {"data": [{
                "scopeId": {"Comparison": {"ComparisonKind": 0, "Left": {"Column": col},
                                           "Right": {"Literal": {"Value": f"'{k}'"}}}}}]}}
                for k, c in por_categoria.items()]
        if relleno:  # color por valor de campo (medida que devuelve un hex)
            objs["dataPoint"] = [{"properties": {"fill": {"solid": {"color": {"expr": medida(
                relleno)}}}}, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]
        self._agregar(x, y, w, h, {"visualType": tipo, "query": {"queryState": qs},
                                   "objects": objs,
                                   "visualContainerObjects": contenedor(titulo, subtitulo)},
                      filtros)

    def segmentador(self, x, y, w, h, campo, titulo, desplegable=True, filtros=None,
                    seleccion: str | None = None):
        objs: dict = {"data": [{"properties": {"mode": lit("Dropdown" if desplegable
                                                           else "Basic")}}],
                      "header": [{"properties": {"show": lit(False)}}],
                      "items": [{"properties": {"fontColor": color(TINTA), "textSize": lit(10.0)}}]}
        if seleccion:
            ent = campo["Column"]["Expression"]["SourceRef"]["Entity"]
            col = campo["Column"]["Property"]
            objs["selection"] = [{"properties": {"singleSelect": lit(True),
                                                 "strictSingleSelect": lit(True)}}]
            objs["general"] = [{"properties": {"filter": {"filter": filtro_en(
                ent, col, [seleccion], "sel")["filter"]}}}]
        self._agregar(x, y, w, h, {"visualType": "slicer", "query": {"queryState": {
            "Values": {"projections": [proy(campo)]}}}, "objects": objs,
            "visualContainerObjects": contenedor(titulo)}, filtros)

    def tabla(self, x, y, w, h, campos: list[tuple[dict, str]], titulo, subtitulo=None):
        objs = {"columnHeaders": [{"properties": {"fontColor": color(BLANCO),
                                                  "backColor": color(NAVY),
                                                  "fontFamily": lit(FUENTE_FUERTE)}}],
                "values": [{"properties": {"fontColorPrimary": color(TINTA),
                                           "backColorPrimary": color(BLANCO),
                                           "backColorSecondary": color("#F7F4EE")}}],
                "grid": [{"properties": {"rowPadding": lit(6.0), "textSize": lit(10.0)}}],
                "total": [{"properties": {"totals": lit(False)}}]}
        self._agregar(x, y, w, h, {"visualType": "tableEx", "query": {"queryState": {
            "Values": {"projections": [proy(c, a) for c, a in campos]}}}, "objects": objs,
            "visualContainerObjects": contenedor(titulo, subtitulo)})

    def pie(self):
        self.texto(M, H - 22, W - 2 * M, 18, [(PIE, 8.5, TINTA_3, False)])

    def boton(self, x, y, w, h, destino: str, texto: str, activo: bool):
        """Botón de navegación con estados normal, hover, presionado y activo."""
        fondo, letra = (AZUL, BLANCO) if activo else (NAVY_2, "#C9D4E5")
        hover, presion = ("#2F7DDB", "#1A5FB4") if activo else ("#23446F", "#2B5689")
        self._agregar(x, y, w, h, {
            "visualType": "actionButton",
            "objects": {
                "icon": [{"properties": {"shapeType": lit("blank")}, "selector": SEL_DEF}],
                "text": [{"properties": {"show": lit(True)}},
                         {"properties": {"text": lit(" " * 4 + texto), "fontColor": color(letra),
                                         "fontSize": lit(10.0),
                                         "fontFamily": lit(FUENTE_FUERTE)}, "selector": SEL_DEF},
                         {"properties": {"fontColor": color(BLANCO)}, "selector": SEL_HOVER}],
                "fill": [{"properties": {"show": lit(True)}},
                         {"properties": {"fillColor": color(fondo), "transparency": lit(0.0)},
                          "selector": SEL_DEF},
                         {"properties": {"fillColor": color(hover), "transparency": lit(0.0)},
                          "selector": SEL_HOVER},
                         {"properties": {"fillColor": color(presion), "transparency": lit(0.0)},
                          "selector": {"id": "press"}}],
                "outline": [{"properties": {"show": lit(activo), "lineColor": color("#9DB7DD"),
                                            "weight": lit(1.0)}, "selector": SEL_DEF}],
                "shape": [{"properties": {"tileShape": lit("roundedRectangle"),
                                          "rectangleRoundedCurve": lit(8)}}],
            },
            "visualContainerObjects": {
                "visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"),
                                               "navigationSection": lit(destino)}}],
                "title": [{"properties": {"show": lit(False)}}],
                "background": [{"properties": {"show": lit(False)}}],
                "border": [{"properties": {"show": lit(False)}}],
                "dropShadow": [{"properties": {"show": lit(False)}}],
                "visualHeader": [{"properties": {"show": lit(False)}}]}})

    def encabezado(self):
        # banda oscura a todo el ancho con textura topográfica sutil
        self.texto(0, 0, W, BANDA, [(" ", 8, NAVY, False)], fondo=NAVY)
        self.imagen(0, 0, W, BANDA, "Textura encabezado")
        self.imagen(M, 34, 26, 26, f"Ícono página {self.menu}")
        self.texto(M, 12, 640, 18, [("PULSO ENERGÉTICO DE EE. UU.  ·  " + self.menu.upper(),
                                     8.5, "#9DB7DD", True)])
        self.texto(M + 36, 30, 620, 34, [(self.titulo, 18, BLANCO, True)])
        self.texto(M, 66, 640, 20, [(self.bajada, 9, "#C9D4E5", False)])
        # navegación: botones propios con ícono
        nav_x, nav_w = 680, W - 680 - M
        bw = (nav_w - 4 * 6) // 5
        for i, (destino, texto) in enumerate(PAGINAS):
            bx = nav_x + i * (bw + 6)
            self.boton(bx, 14, bw, 36, destino, texto, destino == self.nombre)
            # el texto va centrado: el ícono se ubica justo a la izquierda de la palabra
            ancho_txt = len(texto) * 6.4 + 11
            ix = bx + int((bw - ancho_txt) / 2) - 8
            self.imagen(ix, 24, 16, 16, f"Ícono página {texto}", pagina=destino)
        self.pie()
        # estado de los datos
        self._agregar(nav_x, 56, nav_w, 28, {
            "visualType": "card",
            "query": {"queryState": {"Values": {"projections": [
                proy(medida("Estado de los datos"))]}}},
            "objects": {"labels": [{"properties": {"fontSize": lit(9.5), "color": color("#8FD3A8"),
                                                   "fontFamily": lit(FUENTE)}}],
                        "categoryLabels": [{"properties": {"show": lit(False)}}]},
            "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}],
                                       "title": [{"properties": {"show": lit(False)}}],
                                       "visualHeader": [{"properties": {"show": lit(False)}}],
                                       "padding": [{"properties": {"top": lit(0.0),
                                                                   "bottom": lit(0.0)}}]}})


def _fila(n: int, x0: int = M, ancho: int = W - 2 * M) -> tuple[int, list[int]]:
    w = (ancho - (n - 1) * G) // n
    return w, [x0 + i * (w + G) for i in range(n)]


def paginas() -> list[Pagina]:
    F, S, R, AR = "dim_fecha", "dim_serie", "dim_region", "analisis_rezago"
    fecha = columna(F, "fecha")
    sin_blanco = [filtro_desde(F, "anio", 2000, "f_anio")]
    ps = []

    # 1 · Resumen
    p = Pagina("resumen", "Resumen", "El pulso hoy",
               "Último dato publicado de cada serie de la EIA")
    p.encabezado()
    w, xs = _fila(5)
    p.imagen(M, Y0 + 1, 18, 18, "Ícono sección petróleo")
    p.texto(M + 24, Y0, 400, 22, [("PETRÓLEO", 10, NARANJA, True)])
    for x, (m, e, n, ic) in zip(xs, [
            ("Último WTI", "WTI", "US$ por barril", "Ícono WTI"),
            ("WTI vs promedio 12 meses %", "WTI vs. promedio 12 m", "variación",
             "Flecha WTI vs promedio 12 meses"),
            ("Diferencial Brent-WTI", "Brent − WTI", "US$ por barril", "Ícono Brent-WTI"),
            ("Stock crudo comercial", "Crudo comercial", "miles de barriles",
             "Ícono crudo comercial"),
            ("Crudo comercial vs año anterior %", "Crudo vs. año anterior", "misma semana",
             "Flecha crudo vs año anterior")], strict=True):
        p.kpi(x, Y0 + 26, w, 112, m, e, n, NARANJA, icono=ic)
    y2 = Y0 + 26 + 112 + 20
    p.imagen(M, y2 + 1, 18, 18, "Ícono sección gas")
    p.texto(M + 24, y2, 400, 22, [("GAS NATURAL", 10, AZUL, True)])
    for x, (m, e, n, ic) in zip(xs, [
            ("Último Henry Hub", "Henry Hub", "US$ por MMBtu", "Ícono Henry Hub"),
            ("Henry Hub vs promedio 12 meses %", "Henry Hub vs. prom. 12 m", "variación",
             "Flecha Henry Hub vs promedio 12 meses"),
            ("Gas almacenado Lower 48", "Gas almacenado", "Bcf · Lower 48",
             "Ícono gas almacenado"),
            ("Inyección neta semanal", "Inyección neta", "Bcf en la semana",
             "Ícono inyección neta"),
            ("Participación generación eléctrica %", "Generación eléctrica",
             "del consumo de gas", "Ícono generación eléctrica")], strict=True):
        p.kpi(x, y2 + 26, w, 112, m, e, n, AZUL, icono=ic)
    y3 = y2 + 26 + 112 + 18
    hc = FIN - y3
    w2, xs2 = _fila(2)
    p.grafico("lineChart", xs2[0], y3, w2, hc, fecha, ["Precio WTI", "Precio Brent"],
              "Precio spot del crudo", "US$ por barril", colores=[AZUL, NARANJA])
    p.grafico("lineChart", xs2[1], y3, w2, hc, fecha, ["Gas almacenado Lower 48"],
              "Gas natural almacenado", "Bcf · Lower 48", colores=[AZUL])
    ps.append(p)

    # 2 · Petróleo
    p = Pagina("petroleo", "Petróleo", "Petróleo: precios, inventarios y producción",
               "Precios diarios, inventarios semanales y producción mensual")
    p.encabezado()
    p.segmentador(M, Y0, 200, ALTO_KPI, columna(F, "anio"), "Año", filtros=sin_blanco)
    w4, xs4 = _fila(4, M + 216, W - 2 * M - 216)
    for x, (m, e, n, ic) in zip(xs4, [
            ("Último WTI", "WTI", "US$ por barril", "Ícono WTI"),
            ("Stock crudo comercial", "Crudo comercial", "miles de barriles",
             "Ícono crudo comercial"),
            ("Stock SPR", "Reserva estratégica", "miles de barriles", "Ícono reserva estratégica"),
            ("Variación semanal crudo comercial", "Variación semanal", "miles de barriles",
             "Flecha variación semanal crudo")], strict=True):
        p.kpi(x, Y0, w4, ALTO_KPI, m, e, n, NARANJA, tam=22.0, icono=ic)
    ya = Y0 + ALTO_KPI + G
    ha = (FIN - ya - G) // 2
    p.grafico("lineChart", M, ya, 800, ha, fecha, ["Precio WTI", "Precio Brent"],
              "Precio spot WTI y Brent", "US$ por barril", colores=[AZUL, NARANJA])
    xs_ = M + 800 + G
    ws_ = W - 2 * M - 800 - G
    p.grafico("clusteredBarChart", xs_, ya, ws_, ha,
              columna(S, "nombre"), ["Último valor"], "Precio en surtidor",
              "US$ por galón · última semana · diésel en ocre", etiquetas=True,
              por_categoria={"Gasolina regular": NARANJA, "Gasolina media": NARANJA,
                             "Gasolina premium": NARANJA, "Diésel": OCRE},
              filtros=[filtro_en(S, "categoria", ["precio_surtidor"], "f_surtidor")])
    p.icono_titulo(xs_, ya, ws_, "Ícono surtidor")
    yb = ya + ha + G
    w2, xs2 = _fila(2)
    p.grafico("lineChart", xs2[0], yb, w2, ha, fecha, ["Stock crudo comercial", "Stock SPR"],
              "Inventarios de crudo", "miles de barriles", colores=[AZUL, NARANJA])
    p.nota(xs2[0] + w2 - 300, yb + 14, 286, "Ícono alerta",
           "2026: fuerte caída de la reserva estratégica", ALERTA)
    p.grafico("lineChart", xs2[1], yb, w2, ha, fecha, ["Producción de crudo"],
              "Producción de crudo", "miles de barriles por día", colores=[NARANJA])
    p.nota(xs2[1] + w2 - 300, yb + 14, 286, "Ícono info",
           "2020: COVID, caída y rebote de la producción")
    ps.append(p)

    # 3 · Gas
    p = Pagina("gas", "Gas", "Gas natural: precio, almacenamiento y consumo",
               "Henry Hub diario, almacenamiento semanal y consumo mensual por sector")
    p.encabezado()
    p.segmentador(M, Y0, 200, ALTO_KPI, columna(F, "anio"), "Año", filtros=sin_blanco)
    for x, (m, e, n) in zip(xs4, [
            ("Último Henry Hub", "Henry Hub", "US$ por MMBtu"),
            ("Gas almacenado Lower 48", "Gas almacenado", "Bcf · Lower 48"),
            ("Almacenamiento vs año anterior %", "Vs. año anterior", "misma semana"),
            ("Inyección neta semanal", "Inyección neta", "Bcf en la semana")], strict=True):
        p.kpi(x, Y0, w4, ALTO_KPI, m, e, n, AZUL, tam=22.0)
    p.grafico("lineChart", M, ya, 800, ha, fecha, ["Precio Henry Hub"], "Precio Henry Hub",
              "US$ por MMBtu", colores=[AZUL])
    p.grafico("clusteredBarChart", M + 800 + G, ya, W - 2 * M - 800 - G, ha,
              columna(R, "nombre"), ["Gas almacenado por región"], "Almacenamiento por región",
              "Bcf · última semana", etiquetas=True, colores=[AZUL],
              filtros=[filtro_en(R, "tipo", ["region_almacenamiento"], "f_region")])
    p.grafico("hundredPercentStackedColumnChart", xs2[0], yb, w2, ha, columna(F, "anio"),
              ["Consumo por sector"], "Consumo de gas por sector", "participación anual",
              serie=columna(S, "nombre"),
              filtros=[filtro_en(S, "categoria", ["consumo"], "f_consumo")] + sin_blanco)
    p.grafico("lineChart", xs2[1], yb, w2, ha, fecha, ["Gas almacenado Lower 48"],
              "Gas almacenado Lower 48", "Bcf · el ciclo de inyección y extracción",
              colores=[AZUL])
    ps.append(p)

    # 4 · Rezago
    p = Pagina("rezago", "Rezago", "¿Cuánto tarda la producción en reaccionar al precio?",
               "Correlación entre la variación mensual del WTI y la de la producción, 0 a 12 meses "
               "después")
    p.encabezado()
    p.segmentador(M, Y0, 260, 96, columna(AR, "escenario"), "Escenario", desplegable=False,
                  seleccion="completo")
    p.kpi(M + 260 + G, Y0, 200, 96, "Rezago óptimo (meses)", "Rezago óptimo", "meses", NARANJA)
    p.kpi(M + 476 + G, Y0, 200, 96, "Correlación en el óptimo", "Correlación", "r de Pearson",
          NARANJA)
    xl = M + 692 + G
    p.kpi(xl, Y0, W - M - xl, 96, "Texto rezago", "Lectura", "correlación, no causalidad",
          NARANJA, tam=13.0)
    yc = Y0 + 96 + G
    hc = 250
    p.grafico("clusteredColumnChart", M, yc, 800, hc, columna(AR, "rezago_meses"),
              ["Correlación"], "Correlación según meses de rezago",
              "naranja = rezago con mayor correlación", relleno="Color barra rezago",
              etiquetas=True)
    p.texto(M + 800 + G, yc, W - 2 * M - 800 - G, hc, [
        ("Cómo leerlo", 12, TINTA, True),
        ("Comparamos la variación mensual del WTI con la de la producción de crudo entre 0 y 12 "
         "meses después.", 10, TINTA_2, False),
        ("Lo calculamos de dos maneras porque 2020 fue un año extremo: precio y producción se "
         "desplomaron y rebotaron casi a la vez.", 10, TINTA_2, False),
        ("Que el resultado cambie tanto entre escenarios muestra que ninguna cifra es una regla "
         "fija. Es correlación, no causalidad.", 10, TINTA_2, False)], fondo=BLANCO)
    yd = yc + hc + G
    hd = FIN - yd
    p.grafico("lineChart", xs2[0], yd, w2, hd, fecha, ["Precio WTI mensual"],
              "Precio WTI mensual", "US$ por barril", colores=[AZUL])
    p.grafico("lineChart", xs2[1], yd, w2, hd, fecha, ["Producción de crudo"],
              "Producción de crudo", "miles de barriles por día", colores=[NARANJA])
    ps.append(p)

    # 5 · Calidad
    p = Pagina("calidad", "Calidad", "Calidad y frescura de los datos",
               "Cada fuente se compara con un umbral de atraso según su frecuencia")
    p.encabezado()
    w3, xs3 = _fila(3)
    for x, (m, e, n, a) in zip(xs3, [
            ("Fuentes al día", "Fuentes al día", "de 10 datasets", "#1D7A3B"),
            ("Fuentes atrasadas", "Fuentes atrasadas", "superan su umbral", "#A35400"),
            ("Máximo atraso (días)", "Máximo atraso", "días desde el último período", AZUL)],
            strict=True):
        p.kpi(x, Y0, w3, 100, m, e, n, a, tam=30.0)
    fr = "frescura"
    yt = Y0 + 100 + G
    p.tabla(M, yt, 860, FIN - yt,
            [(columna(fr, "dataset"), "Dataset"), (columna(fr, "frecuencia"), "Frecuencia"),
             (columna(fr, "ultimo_periodo"), "Último período"),
             (columna(fr, "dias_atraso"), "Días de atraso"),
             (columna(fr, "umbral_dias"), "Umbral (días)"),
             (medida("Icono de estado"), "Estado")],
            "Frescura de cada fuente", "una fila por dataset de la EIA")
    p.texto(M + 860 + G, yt, W - 2 * M - 860 - G, FIN - yt, [
        ("Umbrales de atraso", 12, TINTA, True),
        ("Diaria: 10 días", 10, TINTA_2, False),
        ("Semanal: 14 días", 10, TINTA_2, False),
        ("Mensual: 120 días", 10, TINTA_2, False),
        (" ", 6, TINTA_2, False),
        ("Los datos mensuales de la EIA salen con unos 2 a 3 meses de demora: por eso su "
         "umbral es más amplio.", 10, TINTA_3, False),
        ("Las revisiones que hace la EIA sobre datos ya cargados se auditan en "
         "silver_auditoria_revisiones y nunca se pisan.", 10, TINTA_3, False)], fondo=BLANCO)
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
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/"
                   "platformProperties/2.0.0/schema.json",
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
        "layoutOptimization": "None",
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": tema, "path": tema, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True,
                     "defaultDrillFilterOtherVisuals": True}})
    dst = raiz / "StaticResources" / "RegisteredResources" / tema
    dst.parent.mkdir(parents=True)
    shutil.copy(TEMA, dst)

    ps = paginas()
    escribir(d / "pages" / "pages.json", {"$schema": f"{SCH}/pagesMetadata/1.0.0/schema.json",
                                          "pageOrder": [p.nombre for p in ps],
                                          "activePageName": ps[0].nombre})
    for p in ps:
        base = d / "pages" / p.nombre
        escribir(base / "page.json", {
            "$schema": f"{SCH}/page/1.0.0/schema.json", "name": p.nombre,
            "displayName": p.menu, "displayOption": "FitToPage", "height": H, "width": W,
            "objects": {"background": [{"properties": {"color": color(PAPEL),
                                                       "transparency": lit(0.0)}}],
                        "outspace": [{"properties": {"color": color(PAPEL)}}]}})
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
