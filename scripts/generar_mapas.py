"""Specs de Vega-Lite (visual Deneb) para las páginas "Mapa de la red" y "Análisis geoespacial".

La geometría (estados, red de gasoductos simplificada, regiones) y los puntos estáticos (hubs,
GNL, reserva estratégica, centrales) se embeben en la spec desde data/gold/geo: Deneb no carga
URLs externas. Lo que cambia con los datos (almacenamiento, precio, km, balance, capas
elegidas) llega desde el modelo como filas del dataset de Deneb, una por estado.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "data" / "gold" / "geo"
SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
UMBRAL_KM = float(yaml.safe_load((RAIZ / "config" / "pipeline.yaml").read_text(
    encoding="utf-8"))["geo"]["umbral_proximidad_km"])

AZUL, NARANJA, TINTA, TINTA_2, TINTA_3 = "#1F6FD1", "#C4531A", "#1B1F24", "#4A5260", "#7A8394"
GRIS_RED, FONDO_ESTADO, OCRE = "#5B6770", "#F1EEE7", "#A87D00"
AZULES = ["#DCE8F8", "#A9C7EE", "#6FA0E0", "#3478D2", "#164E9C"]
FUENTE = "Segoe UI"


def _leer(nombre: str) -> dict[str, Any]:
    return json.loads((GOLD / f"mapa_{nombre}.geojson").read_text(encoding="utf-8"))


def _puntos(tabla: str, cols: list[str]) -> list[dict[str, Any]]:
    p = GOLD / f"{tabla}.parquet"
    if not p.exists():
        return []
    df = pd.read_parquet(p)
    return json.loads(df[cols].round(4).to_json(orient="records", force_ascii=False))


def _estados_por_clave() -> list[dict[str, Any]]:
    """Features de estados aplanadas para un lookup por estado_key."""
    return [{"k": f["properties"]["estado_key"], "geo": f} for f in _leer("estados")["features"]]


def capa_visible(nombre: str) -> str:
    return f"indexof(data('dataset')[0]['Capas visibles'] || '', '{nombre}') >= 0"


CONFIG = {"font": FUENTE, "view": {"stroke": None},
          "legend": {"labelFont": FUENTE, "titleFont": FUENTE, "labelColor": TINTA_2,
                     "titleColor": TINTA_2, "orient": "bottom-left", "direction": "horizontal"},
          "axis": {"labelFont": FUENTE, "titleFont": FUENTE, "labelColor": TINTA_3,
                   "titleColor": TINTA_2, "gridColor": "#ECE7DD", "domainColor": "#D8D2C6"}}


def _base(capas: list[dict[str, Any]]) -> dict[str, Any]:
    return {"$schema": SCHEMA, "data": {"name": "dataset"}, "width": "container",
            "height": "container", "autosize": {"type": "fit", "contains": "padding"},
            "projection": {"type": "albersUsa"}, "config": CONFIG, "layer": capas}


def _capa_estados(color: dict[str, Any], tooltip: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "transform": [{"lookup": "estado_key", "from": {"data": {"values": _estados_por_clave()},
                                                       "key": "k", "fields": ["geo"]}}],
        "mark": {"type": "geoshape", "stroke": "#FFFFFF", "strokeWidth": 0.8},
        "encoding": {"shape": {"field": "geo", "type": "geojson"}, "color": color,
                     "strokeWidth": {"condition": {"test": "datum.__selected__ == 'on'",
                                                   "value": 2.5}, "value": 0.8},
                     "stroke": {"condition": {"test": "datum.__selected__ == 'on'",
                                              "value": TINTA}, "value": "#FFFFFF"},
                     "tooltip": tooltip}}


def _capa_red(filtro: str | None = None, hh_destacado: bool = False) -> dict[str, Any]:
    t = [{"filter": filtro}] if filtro else []
    enc: dict[str, Any] = {
        "strokeWidth": {"condition": {"test": "datum.properties.tipo == 'interestatal'",
                                      "value": 0.9}, "value": 0.45}}
    if hh_destacado:
        enc["stroke"] = {"condition": {"test": "datum.properties.hh", "value": "#164E9C"},
                         "value": "#B9B3A8"}
        enc["strokeOpacity"] = {"condition": {"test": "datum.properties.hh", "value": 0.9},
                                "value": 0.35}
    return {"data": {"values": _leer("red"), "format": {"property": "features"}},
            "transform": t,
            "mark": {"type": "geoshape", "filled": False, "stroke": GRIS_RED,
                     "strokeOpacity": 0.55}, "encoding": enc}


def _capa_puntos(valores: list[dict[str, Any]], filtro: str, marca: dict[str, Any],
                 tooltip: list[str]) -> dict[str, Any]:
    return {"data": {"values": valores}, "transform": [{"filter": filtro}],
            "mark": marca,
            "encoding": {"longitude": {"field": "lon", "type": "quantitative"},
                         "latitude": {"field": "lat", "type": "quantitative"},
                         "tooltip": [{"field": c, "type": "nominal"} for c in tooltip]}}


def _henry_hub() -> list[dict[str, Any]]:
    hh = [p for p in _puntos("geo_hubs", ["nombre", "lon", "lat"]) if p["nombre"] == "Henry Hub"]
    texto = ("'Henry Hub · US$ ' + (isValid(data('dataset')[0]['Último Henry Hub']) ? "
             "format(data('dataset')[0]['Último Henry Hub'], '.2f') : 's/d')")
    enc = {"longitude": {"field": "lon", "type": "quantitative"},
           "latitude": {"field": "lat", "type": "quantitative"}}
    return [
        {"data": {"values": hh}, "mark": {"type": "circle", "size": 260, "color": NARANJA,
                                          "stroke": "#FFFFFF", "strokeWidth": 2.5, "opacity": 1},
         "encoding": enc},
        {"data": {"values": hh}, "mark": {"type": "text", "align": "left", "dx": 14, "dy": -12,
                                          "fontSize": 13, "fontWeight": "bold",
                                          "stroke": "#FFFFFF", "strokeWidth": 4},
         "encoding": {**enc, "text": {"value": {"expr": texto}}}},
        {"data": {"values": hh}, "mark": {"type": "text", "align": "left", "dx": 14, "dy": -12,
                                          "fontSize": 13, "fontWeight": "bold", "color": TINTA},
         "encoding": {**enc, "text": {"value": {"expr": texto}}}}]


def spec_mapa_red() -> dict[str, Any]:
    """Mapa principal: estados por almacenamiento de su región, red, hubs, GNL y centrales."""
    almac = {"condition": {"test": capa_visible("Regiones de almacenamiento"),
                           "field": "Gas almacenado región del estado", "type": "quantitative",
                           "scale": {"range": AZULES},
                           "legend": {"title": "Gas almacenado en la región (Bcf)",
                                      "gradientLength": 160}},
             "value": FONDO_ESTADO}
    tooltip = [{"field": "nombre", "title": "Estado"},
               {"field": "Km de red en estados", "title": "km de red", "format": ",.0f"},
               {"field": "Gas almacenado región del estado", "title": "Gas en su región (Bcf)",
                "format": ",.0f"}]
    capas = [_capa_estados(almac, tooltip)]
    capas.append({**_capa_red(capa_visible("Gasoductos"))})
    capas.append(_capa_puntos(
        _puntos("geo_centrales", ["planta", "estado_key", "capacidad_mw", "lon", "lat"]),
        capa_visible("Centrales a gas"),
        {"type": "circle", "size": 9, "color": "#6FA0E0", "opacity": 0.55},
        ["planta", "capacidad_mw"]))
    capas.append(_capa_puntos(
        _puntos("geo_reserva_estrategica", ["nombre", "estado", "lon", "lat"]),
        capa_visible("Reserva estratégica"),
        {"type": "square", "size": 70, "color": TINTA_2, "stroke": "#FFFFFF",
         "strokeWidth": 1.5}, ["nombre", "estado"]))
    capas.append(_capa_puntos(
        [p for p in _puntos("geo_hubs", ["nombre", "lon", "lat"]) if p["nombre"] != "Henry Hub"],
        capa_visible("Hubs"),
        {"type": "circle", "size": 45, "color": "#164E9C", "stroke": "#FFFFFF",
         "strokeWidth": 1.2}, ["nombre"]))
    capas.append(_capa_puntos(
        _puntos("geo_gnl", ["nombre", "funcion", "lon", "lat"]),
        capa_visible("Terminales de GNL"),
        {"type": "point", "shape": "diamond", "size": 110, "filled": True, "color": AZUL,
         "stroke": "#FFFFFF", "strokeWidth": 1.5}, ["nombre", "funcion"]))
    capas += _henry_hub()
    return _base(capas)


def spec_balance() -> dict[str, Any]:
    """Coroplético del balance interestatal neto (recibe − entrega). Sin datos: aviso."""
    color = {"field": "Balance neto interestatal", "type": "quantitative",
             "scale": {"type": "symlog", "domainMid": 0, "range": [OCRE, "#F3EFE8", AZUL]},
             "legend": None}
    tooltip = [{"field": "nombre", "title": "Estado"},
               {"field": "Balance neto (texto)", "title": "Balance neto"}]
    capas = [_capa_estados(color, tooltip),
             {"transform": [{"aggregate": [{"op": "valid", "field": "Balance neto interestatal",
                                            "as": "n"}]},
                            {"filter": "datum.n == 0"}],
              "mark": {"type": "text", "fontSize": 13, "color": TINTA_2, "x": {"expr": "width/2"},
                       "y": {"expr": "height/2"}, "align": "center", "lineBreak": "|"},
              "encoding": {"text": {"value": "No disponible|La API de la EIA no publicó los "
                                             "flujos interestatales en esta carga"}}}]
    return _base(capas)


def spec_alcance_hh() -> dict[str, Any]:
    color = {"condition": {"test": "datum['Conectado al Henry Hub'] == 1", "value": "#A9C7EE"},
             "value": FONDO_ESTADO}
    tooltip = [{"field": "nombre", "title": "Estado"},
               {"field": "Km huella Henry Hub", "title": "km de huella", "format": ",.0f"}]
    return _base([_capa_estados(color, tooltip), _capa_red(hh_destacado=True), *_henry_hub()])


def spec_ranking(medida: str, titulo_eje: str, n: int = 12, formato: str = ",.0f",
                 orden: str = "descending") -> dict[str, Any]:
    return {"$schema": SCHEMA, "data": {"name": "dataset"}, "width": "container",
            "height": "container", "config": CONFIG,
            "transform": [{"window": [{"op": "row_number", "as": "r"}],
                           "sort": [{"field": medida, "order": orden}]},
                          {"filter": f"datum.r <= {n}"}],
            "layer": [
                {"mark": {"type": "bar", "color": AZUL, "cornerRadiusEnd": 3, "height": 14},
                 "encoding": {"y": {"field": "nombre", "type": "nominal", "title": None,
                                    "sort": "-x" if orden == "descending" else "x"},
                              "x": {"field": medida, "type": "quantitative",
                                    "title": titulo_eje},
                              "opacity": {"condition": {"test": "datum.__selected__ == 'off'",
                                                        "value": 0.35}, "value": 1}}},
                {"mark": {"type": "text", "align": "left", "dx": 4, "fontSize": 10,
                          "color": TINTA_2},
                 "encoding": {"y": {"field": "nombre", "type": "nominal",
                                    "sort": "-x" if orden == "descending" else "x"},
                              "x": {"field": medida, "type": "quantitative"},
                              "text": {"field": medida, "type": "quantitative",
                                       "format": formato}}}]}


def spec_proximidad(umbral_km: float) -> dict[str, Any]:
    """Capacidad a gas por distancia a la red (bandas de 5 km hasta 50; resto agrupado)."""
    valores = _puntos("geo_centrales", ["capacidad_mw", "distancia_red_km"])
    base = {"$schema": SCHEMA, "width": "container", "height": "container", "config": CONFIG}
    if not valores:
        return {**base, "data": {"values": [{}]},
                "mark": {"type": "text", "fontSize": 12, "color": TINTA_2, "lineBreak": "|"},
                "encoding": {"text": {"value": "No disponible|La API de la EIA no respondió "
                                               "(centrales a gas, EIA-860M)"}}}
    return {**base, "data": {"values": valores},
            "transform": [{"calculate": "min(floor(datum.distancia_red_km / 5) * 5, 50)",
                           "as": "banda"}],
            "layer": [
                {"mark": {"type": "bar", "color": AZUL, "cornerRadiusEnd": 2},
                 "encoding": {"x": {"field": "banda", "type": "ordinal",
                                    "title": "km a la red (bandas de 5; 50 = 50 o más)"},
                              "y": {"aggregate": "sum", "field": "capacidad_mw",
                                    "type": "quantitative", "title": "MW"}}},
                {"mark": {"type": "rule", "color": NARANJA, "strokeDash": [4, 3]},
                 "encoding": {"x": {"datum": int(umbral_km // 5 * 5), "type": "ordinal"}}}]}
