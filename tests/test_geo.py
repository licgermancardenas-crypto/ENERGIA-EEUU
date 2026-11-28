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


def test_flujos_formato_api_v2_totales_y_pares():
    filas = [{"duoarea": "SIN-Z0S", "period": "2024", "process": p, "value": v}
             for p, v in (("MIR", 10), ("MID", 4), ("MIN", 6))]
    filas += [{"duoarea": "SIN-SKY", "period": "2024", "process": "MID", "value": "242255"},
              {"duoarea": "SIN-SKY", "period": "2024", "process": "MIR", "value": "140503"},
              {"duoarea": "SIN-R3FM", "period": "2024", "process": "MID", "value": "5"},
              {"duoarea": "SIN-SOH", "period": "2024", "process": "MID", "value": "0"}]
    e = gold.flujos_estado(filas, {"IN", "KY"}).set_index("estado_key")
    assert e.loc["IN", "neto_mmcf"] == 6 and bool(e.loc["IN", "cierre_ok"])
    p = gold.flujos_pares(filas, {"IN", "KY", "OH"})
    esperado = [{"origen": "IN", "destino": "KY", "anio": 2024, "mmcf": 242255.0}]
    assert p.to_dict("records") == esperado
    assert gold.flujos_pares([], {"IN"}).empty


def test_centrales_distancia_a_la_red(red):
    filas = [{"plantid": "1", "plantName": "Cerca", "stateid": "AA",
              "nameplate-capacity-mw": "100", "latitude": "0", "longitude": "0"}]
    c = gold.centrales_a_red(filas, red, CRS, 25, {"AA"})
    assert len(c) == 1 and c.loc[0, "distancia_red_km"] >= 0
    assert gold.centrales_a_red([], red, CRS, 25, {"AA"}).empty


def test_moe_de_proporcion_formula_census():
    import numpy as np
    # p = 0,5; radicando 10² - 0,5² * 30² = -125 < 0 -> el Census indica sumar
    m = gold.moe_proporcion(np.array([50.0]), np.array([10.0]), np.array([100.0]),
                            np.array([30.0]))
    assert m[0] == pytest.approx(np.sqrt(100 + 225) / 100)
    m2 = gold.moe_proporcion(np.array([50.0]), np.array([10.0]), np.array([100.0]),
                             np.array([4.0]))
    assert m2[0] == pytest.approx(np.sqrt(100 - 4) / 100)


def test_calefaccion_por_condado_y_estado(estados, red):
    cond = gpd.GeoDataFrame({"condado_key": ["01001", "02001"], "estado_key": ["AA", "BB"],
                             "nombre": ["C1", "C2"], "area_km2": [1.0, 1.0]},
                            geometry=[box(0, 0, 100_000, 100_000),
                                      box(500_000, 500_000, 600_000, 600_000)], crs=CRS)
    acs = pd.DataFrame({"condado_key": ["01001", "02001"], "hogares": [100.0, 200.0],
                        "hogares_moe": [5.0, 5.0], "gas_red": [80.0, 150.0],
                        "gas_red_moe": [4.0, 4.0], "propano": [5.0, 10.0],
                        "propano_moe": [1.0, 1.0]})
    df, val = gold.calefaccion_condado(cond, acs, red, CRS, 25, 0.5)
    d = df.set_index("condado_key")
    assert d.loc["01001", "distancia_red_km"] == pytest.approx(0)  # la red lo cruza
    assert d.loc["02001", "distancia_red_km"] > 25
    assert not d.loc["01001", "alta_dependencia_lejos"] and d.loc["02001", "alta_dependencia_lejos"]
    assert val["condados_sin_acs"] == [] and val["acs_sin_condado"] == []
    e = gold.calefaccion_estado(df).set_index("estado_key")
    assert e.loc["BB", "pct_gas_red"] == pytest.approx(0.75)
    assert e.loc["BB", "hogares_gas_red_lejos"] == pytest.approx(150)


def test_refinerias_union_capacidad_y_estados():
    from eia_pulso.geo import refinerias as rf

    excel = pd.DataFrame([
        {"STATE_NAME": "Texas", "SITE": "PORT ARTHUR", "COMPANY_NAME": "MOTIVA ENTERPRISES LLC",
         "CORPORATION": "SAUDI ARAMCO", "PADD": 3, "PRODUCT": "TOTAL OPERABLE CAPACITY",
         "SUPPLY": "Atmospheric Crude Distillation Capacity (barrels per calendar day)",
         "QUANTITY": 626000},
        {"STATE_NAME": "Texas", "SITE": "PORT ARTHUR", "COMPANY_NAME": "TOTALENERGIES PETROCHEM",
         "CORPORATION": "TOTALENERGIES SE", "PADD": 3, "PRODUCT": "TOTAL OPERABLE CAPACITY",
         "SUPPLY": "Atmospheric Crude Distillation Capacity (barrels per calendar day)",
         "QUANTITY": 238000},
        {"STATE_NAME": "Texas", "SITE": "PORT ARTHUR", "COMPANY_NAME": "MOTIVA ENTERPRISES LLC",
         "CORPORATION": "SAUDI ARAMCO", "PADD": 3, "PRODUCT": "TOTAL OPERABLE CAPACITY",
         "SUPPLY": "Atmospheric Crude Distillation Capacity (barrels per stream day)",
         "QUANTITY": 999999},  # día de corrida: no se suma
        {"STATE_NAME": "Ohio", "SITE": "LIMA", "COMPANY_NAME": "LIMA REFINING CO",
         "CORPORATION": "CENOVUS", "PADD": 2, "PRODUCT": "TOTAL OPERABLE CAPACITY",
         "SUPPLY": "Atmospheric Crude Distillation Capacity (barrels per calendar day)",
         "QUANTITY": 180000},
    ])
    cap = rf.silver_capacidad(excel)
    assert cap["capacidad_operable_bcd"].sum() == 626000 + 238000 + 180000
    puntos = pd.DataFrame([
        {"estado": "Texas", "sitio": "Port Arthur", "empresa": "TOTALENERGIES PETROCHEM & REFG",
         "lon": -93.88, "lat": 29.96},
        {"estado": "Texas", "sitio": "Port Arthur", "empresa": "MOTIVA ENTERPRISES LLC",
         "lon": -93.95, "lat": 29.89},
    ])
    estados = pd.DataFrame({"nombre": ["Texas", "Ohio"], "estado_key": ["TX", "OH"]})
    out, val = rf.unir(cap, puntos, estados)
    motiva = out[out["empresa"].str.startswith("MOTIVA")].iloc[0]
    assert motiva["lon"] == -93.95  # el desempate por empresa elige el punto correcto
    assert val["con_ubicacion"] == 2 and len(val["sin_ubicacion"]) == 1  # Lima no está en la capa
    def fila(area, anio, proc, unid, v):
        return {"duoarea": area, "period": anio, "process": proc, "units": unid, "value": v}

    filas = [fila("STX", "2026", "8D0", "B/CD", "864000"),
             fila("STX", "2026", "8O0", "COUNT", "2"), fila("STX", "2025", "8O0", "COUNT", "3"),
             fila("NUS", "2026", "8D0", "B/CD", "1044000")]
    e = rf.estado_refinacion(filas, {"TX"}).set_index("estado_key")
    assert e.loc["TX", "refinerias_operables"] == 2 and e.loc["TX", "anio"] == 2026
    assert rf.total_nacional_api(filas) == 1044000
