"""Capa geoespacial: intersección por estado, densidad, alcance del Henry Hub y geometría liviana.

Se usan geometrías sintéticas en EPSG:5070 (metros) para que los km sean exactos.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import LineString, Point, box  # noqa: E402

from eia_pulso.geo import gold, silver  # noqa: E402
from eia_pulso.geo.config import load_geo  # noqa: E402

CRS = 5070


@pytest.fixture()
def estados():
    # dos "estados" de 100 km x 100 km lado a lado
    g = gpd.GeoDataFrame({"estado_key": ["AA", "BB"], "fips": ["01", "02"],
                          "nombre": ["Estado A", "Estado B"]},
                         geometry=[box(0, 0, 100_000, 100_000), box(100_000, 0, 200_000, 100_000)],
                         crs=CRS)
    g["area_km2"] = g.area / 1e6
    return g


@pytest.fixture()
def red():
    return gpd.GeoDataFrame({
        "tipo": ["interestatal", "intraestatal", "interestatal"],
        "operador": ["Op Hub", "Op Local", "Op Hub"],
        "estado_operativo": ["Operating"] * 3},
        geometry=[LineString([(50_000, 50_000), (150_000, 50_000)]),   # 50 km en A y 50 en B
                  LineString([(10_000, 10_000), (10_000, 30_000)]),    # 20 km en A
                  LineString([(250_000, 0), (260_000, 0)])],           # 10 km fuera
        crs=CRS)


def test_km_por_estado_y_validacion(estados, red):
    km = gold.km_por_estado(red, estados, CRS)
    total = km.groupby("estado_key")["km"].sum().round(6).to_dict()
    assert total == {"AA": 70.0, "BB": 50.0}
    m = gold.metricas_estado(km, estados, {"Op Hub"})
    a = m.set_index("estado_key").loc["AA"]
    assert a["km_interestatal"] == pytest.approx(50) and a["km_intraestatal"] == pytest.approx(20)
    assert a["densidad_km_1000km2"] == pytest.approx(70 / 10_000 * 1000)
    assert a["operadores_n"] == 2 and bool(a["conectado_henry_hub"])
    assert pd.isna(a["km_recoleccion"])  # la capa no trae recolección: no se inventa
    v = gold.validar(km, red, m, CRS)
    assert v["km_red_total"] == pytest.approx(130)
    assert v["km_fuera_de_estados"] == pytest.approx(10)
    assert v["suma_metricas_igual_interseccion"] and v["estados_sin_km"] == []


def test_alcance_henry_hub_marca_lo_que_no_esta(estados, red):
    km = gold.km_por_estado(red, estados, CRS)
    con = pd.DataFrame({"gasoducto": ["Hub", "Ausente"], "operador_en_capa": ["Op Hub", None],
                        "nota": [None, "no figura"]})
    a = gold.alcance_henry_hub(km, con).set_index("gasoducto")
    assert a.loc["Hub", "km"] == pytest.approx(100) and a.loc["Hub", "estados_n"] == 2
    assert not a.loc["Ausente", "en_capa"] and a.loc["Ausente", "km"] == 0


def test_distancia_geodesica():
    # un grado de latitud ~ 110,6 km cerca de 30°N
    assert gold.distancia_km(-92, 29.5, -92, 30.5) == pytest.approx(110.9, abs=0.5)


def test_geojson_liviano_orienta_y_redondea(tmp_path):
    cfg = load_geo(data_dir=tmp_path)
    g = gpd.GeoDataFrame({"k": ["X"]}, geometry=[box(-100, 30, -99, 31)], crs=4326)
    fc = gold.geojson_liviano(g, ["k"], cfg)
    anillo = fc["features"][0]["geometry"]["coordinates"][0]
    # sentido horario (área con signo negativa) y 3 decimales
    area2 = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anillo, anillo[1:], strict=False))
    assert area2 < 0
    assert all(len(str(c).split(".")[-1]) <= cfg.decimales for p in anillo for c in p)
    json.dumps(fc)


def test_silver_rechaza_tipos_inesperados():
    g = gpd.GeoDataFrame({"TYPEPIPE": ["Raro"], "Operator": ["X"], "Status": ["Operating"]},
                         geometry=[LineString([(0, 0), (1, 1)])], crs=4326)
    with pytest.raises(silver.GeoSilverError):
        silver.silver_gasoductos(g)


def test_silver_puntos_numeros_con_guiones():
    g = gpd.GeoDataFrame({"Facility": ["T"], "Operator": ["O"], "City": ["C"], "State": ["S"],
                          "Functions": ["Export"], "Liq_Bcfd": [" 1.78"], "Regas_Bcfd": ["-"],
                          "Stora_Bcf": [10.1], "Period": ["As of August 2023"]},
                         geometry=[Point(-93, 30)], crs=4326)
    p = silver.silver_puntos("gnl", g).iloc[0]
    assert p["licuefaccion_bcfd"] == pytest.approx(1.78) and pd.isna(p["regasificacion_bcfd"])


def test_flujos_cierran_y_rol():
    filas = [{"duoarea": "SLA", "period": "2024", "process": p, "value": v}
             for p, v in (("MIR", 100), ("MID", 300), ("MIN", -200))]
    filas += [{"duoarea": "STX", "period": "2024", "process": p, "value": v}
              for p, v in (("MIR", 500), ("MID", 100), ("MIN", 999))]  # no cierra
    f = gold.flujos_estado(filas, {"LA", "TX"}).set_index("estado_key")
    assert f.loc["LA", "rol"] == "exportador neto" and bool(f.loc["LA", "cierre_ok"])
    assert not bool(f.loc["TX", "cierre_ok"])
    assert gold.flujos_estado([], {"LA"}).empty


def test_centrales_distancia_a_la_red(red):
    filas = [{"plantid": "1", "plantName": "Cerca", "stateid": "AA",
              "nameplate-capacity-mw": "100", "latitude": "0", "longitude": "0"}]
    c = gold.centrales_a_red(filas, red, CRS, 25, {"AA"})
    assert len(c) == 1 and c.loc[0, "distancia_red_km"] >= 0
    assert gold.centrales_a_red([], red, CRS, 25, {"AA"}).empty
