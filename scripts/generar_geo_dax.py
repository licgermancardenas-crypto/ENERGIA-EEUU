"""Medidas DAX de la capa geoespacial: fuente única de dax/geo.dax y del modelo semántico.

Todas viven en la carpeta "Geoespacial" de dim_serie y solo leen las tablas geo_* (no tocan
medidas ni relaciones existentes; reutilizan [Último Henry Hub] y [Gas almacenado por región]).

Uso:  python scripts/generar_geo_dax.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DAX = RAIZ / "dax" / "geo.dax"
TABLA = "dim_serie"
CARPETA = "Geoespacial"
UMBRAL_KM = yaml.safe_load((RAIZ / "config" / "pipeline.yaml").read_text(encoding="utf-8"))[
    "geo"]["umbral_proximidad_km"]


@dataclass
class MedidaGeo:
    nombre: str
    expresion: str
    comentario: str
    formato: str | None = None


def medidas() -> list[MedidaGeo]:
    u = f"{UMBRAL_KM:g}"
    return [
        MedidaGeo("Km de red en estados", "SUM ( geo_estado_metricas[km_total] )",
                  "km de gasoducto dentro de los estados del contexto (sin tramos marinos)",
                  "#,0"),
        MedidaGeo("Km interestatal", "SUM ( geo_estado_metricas[km_interestatal] )",
                  "km de gasoducto interestatal", "#,0"),
        MedidaGeo("Km intraestatal", "SUM ( geo_estado_metricas[km_intraestatal] )",
                  "km de gasoducto intraestatal", "#,0"),
        MedidaGeo("Densidad de red",
                  "DIVIDE ( [Km de red en estados], SUM ( geo_dim_estado[area_km2] ) ) * 1000",
                  "km de gasoducto por cada 1.000 km² de superficie", "#,0.0"),
        MedidaGeo("Operadores en el estado",
                  "DISTINCTCOUNT ( geo_km_estado_operador[operador] )",
                  "operadores distintos cuya red cruza el contexto (no se suman entre estados)",
                  "0"),
        MedidaGeo("Estados conectados al Henry Hub",
                  "CALCULATE ( COUNTROWS ( geo_estado_metricas ), "
                  "geo_estado_metricas[conectado_henry_hub] = TRUE () ) + 0",
                  "estados que toca la huella de red de los operadores conectados al hub "
                  "(huella, no flujo físico)", "0"),
        MedidaGeo("Km huella Henry Hub", "SUM ( geo_estado_metricas[km_red_henry_hub] )",
                  "km de red de los operadores conectados al hub (huella, no flujo)", "#,0"),
        MedidaGeo("Conectado al Henry Hub",
                  "IF ( [Km huella Henry Hub] > 0, 1, 0 )",
                  "1 si el estado tiene red de algún operador conectado al hub", "0"),
        MedidaGeo("Gas almacenado región del estado",
                  "CALCULATE ( [Gas almacenado por región], TREATAS ( VALUES ( "
                  "geo_dim_estado[region_key] ), dim_region[region_key] ) )",
                  "reutiliza [Gas almacenado por región] para la región EIA del estado", "#,0"),
        MedidaGeo("Último año de flujos", "MAX ( geo_flujos_estado[anio] )",
                  "último año publicado de movimientos interestatales", "0"),
        MedidaGeo("Balance neto interestatal",
                  "VAR a = CALCULATE ( [Último año de flujos], REMOVEFILTERS ( geo_dim_estado ) )\n"
                  "RETURN\n    IF ( ISBLANK ( a ), BLANK (), CALCULATE ( SUM ( "
                  "geo_flujos_estado[neto_mmcf] ), geo_flujos_estado[anio] = a ) )",
                  "recepciones netas interestatales del último año (MMcf): > 0 recibe más de lo "
                  "que entrega", "#,0"),
        MedidaGeo("Balance neto (texto)",
                  "VAR v = [Balance neto interestatal]\nRETURN\n    IF ( ISBLANK ( v ), "
                  "\"No disponible\", FORMAT ( v, \"#,0\", \"es-AR\" ) & \" MMcf · \" & "
                  "IF ( v > 0, \"importador neto\", IF ( v < 0, \"exportador neto\", "
                  "\"neutro\" ) ) )",
                  "balance neto con su lectura; 'No disponible' si la EIA no publicó flujos",
                  None),
        MedidaGeo("Capacidad a gas", "SUM ( geo_centrales[capacidad_mw] )",
                  "capacidad nominal de las centrales a gas natural (MW, EIA-860M)", "#,0"),
        MedidaGeo("Centrales a gas", "COUNTROWS ( geo_centrales ) + 0",
                  "cantidad de plantas con generadores a gas natural", "#,0"),
        MedidaGeo("Capacidad cerca de la red %",
                  "DIVIDE ( CALCULATE ( [Capacidad a gas], geo_centrales[dentro_umbral] = "
                  "TRUE () ), [Capacidad a gas] )",
                  f"parte de la capacidad a gas a menos de {u} km de un gasoducto", "0.0 %"),
        MedidaGeo("Proximidad (texto)",
                  "VAR p = [Capacidad cerca de la red %]\nRETURN\n    IF ( ISBLANK ( p ), "
                  "\"No disponible: la API de la EIA no respondió\", FORMAT ( p, \"0.0 %\", "
                  f"\"es-AR\" ) & \" de la capacidad a gas está a menos de {u} km de la red\" )",
                  "lectura de la proximidad o aviso de dato no disponible", None),
        MedidaGeo("GNL más cercano al Henry Hub", "MIN ( geo_gnl[distancia_henry_hub_km] )",
                  "distancia geodésica de la terminal de GNL más cercana al hub (km)", "#,0"),
        MedidaGeo("Distancia GNL al Henry Hub", "MIN ( geo_gnl[distancia_henry_hub_km] )",
                  "para graficar por terminal (km)", "#,0"),
        MedidaGeo("Hogares con gas de red %",
                  "DIVIDE ( SUM ( geo_estado_calefaccion[hogares_gas_red] ), "
                  "SUM ( geo_estado_calefaccion[hogares] ) )",
                  "hogares que calefaccionan con gas de red (ACS B25040, estimación de encuesta)",
                  "0.0 %"),
        MedidaGeo("Hogares con propano %",
                  "DIVIDE ( SUM ( geo_estado_calefaccion[hogares_propano] ), "
                  "SUM ( geo_estado_calefaccion[hogares] ) )",
                  "hogares que calefaccionan con propano (llega en camión, no depende de la red)",
                  "0.0 %"),
        MedidaGeo("Condados con alta dependencia lejos de la red",
                  "SUM ( geo_estado_calefaccion[condados_alta_dependencia_lejos] ) + 0",
                  "condados con ≥ 50 % de hogares con gas de red y a más del umbral de la red "
                  "troncal mapeada", "0"),
        MedidaGeo("Hogares con gas de red lejos de la red",
                  "SUM ( geo_estado_calefaccion[hogares_gas_red_lejos] ) + 0",
                  "hogares con gas de red en esos condados (estimación ACS)", "#,0"),
        MedidaGeo("Distancia media de condados a la red",
                  "AVERAGE ( geo_condado_calefaccion[distancia_red_km] )",
                  "promedio simple de la distancia de cada condado a la red troncal (km)",
                  "#,0.0"),
        MedidaGeo("Gas de red % del condado",
                  "AVERAGE ( geo_condado_calefaccion[pct_gas_red] )",
                  "para el mapa por condado (una fila por condado)", "0.0 %"),
        MedidaGeo("Margen de error del condado",
                  "AVERAGE ( geo_condado_calefaccion[pct_gas_red_moe] )",
                  "margen de error ACS (90 %) del % de gas de red, en puntos", "0.0 %"),
        MedidaGeo("Distancia del condado a la red",
                  "AVERAGE ( geo_condado_calefaccion[distancia_red_km] )",
                  "km del condado a la red troncal mapeada (0 si la red lo cruza)", "#,0.0"),
        MedidaGeo("Condado alta dependencia lejos",
                  "IF ( CALCULATE ( COUNTROWS ( geo_condado_calefaccion ), "
                  "geo_condado_calefaccion[alta_dependencia_lejos] = TRUE () ) > 0, 1, 0 )",
                  "1 si el condado tiene ≥ 50 % de gas de red y está lejos de la red", "0"),
        MedidaGeo("Estado seleccionado",
                  "SELECTEDVALUE ( geo_dim_estado[nombre], \"Todos los estados\" )",
                  "nombre del estado elegido en el mapa o el segmentador", None),
        MedidaGeo("Capas visibles",
                  "CONCATENATEX ( VALUES ( geo_capas_mapa[capa] ), geo_capas_mapa[capa], \"|\" )",
                  "capas elegidas en el segmentador; el mapa (Deneb) las lee para mostrarlas",
                  None),
        MedidaGeo("Vintage capas",
                  "CONCATENATEX ( FILTER ( frescura_geo, frescura_geo[tipo] = \"estática\" && "
                  "NOT ISBLANK ( frescura_geo[vintage] ) ), frescura_geo[capa] & \" \" & "
                  "frescura_geo[vintage], \" · \" )",
                  "año de atributos de cada capa estática, para las notas del informe", None),
    ]


def a_dax(ms: list[MedidaGeo]) -> str:
    out = ["// Medidas de la capa geoespacial del informe Pulso Energético de EE. UU.",
           "// Generado por scripts/generar_geo_dax.py: no editar a mano.",
           "// Uso: Power BI Desktop → Vista de consultas DAX → pegar → 'Actualizar modelo con "
           "cambios'.", f"// Se alojan en la tabla '{TABLA}', carpeta '{CARPETA}'.", "", "DEFINE"]
    for m in ms:
        out += ["", f"    // {m.comentario}", f"    MEASURE '{TABLA}'[{m.nombre}] ="]
        out += [f"        {linea}" for linea in m.expresion.splitlines()]
    out += ["", "EVALUATE", "ROW ("]
    out.append(",\n".join(f'    "{m.nombre}", [{m.nombre}]' for m in ms))
    out += [")", ""]
    return "\n".join(out)


def generar() -> list[MedidaGeo]:
    ms = medidas()
    DAX.parent.mkdir(parents=True, exist_ok=True)
    DAX.write_text(a_dax(ms), encoding="utf-8")
    return ms


if __name__ == "__main__":
    ms = generar()
    print(f"{len(ms)} medidas -> {DAX.relative_to(RAIZ)}")
    sys.exit(0)
