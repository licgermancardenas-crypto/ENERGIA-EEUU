"""Gold -> JSON para el dashboard web (Next.js, export estático).

Todos los números que muestra la web salen de estas tablas Gold: el exportador no consulta
la API ni Silver. Las frases clave se generan acá (no en el navegador) para que sean
deterministas, testeables y trazables a la tabla de origen.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

TABLAS = {
    "diarios": ["fact_precios_diarios"],
    "semanales": ["fact_precio_surtidor_semanal", "fact_inventarios_semanales",
                  "fact_almacenamiento_gas_semanal"],
    "mensuales": ["fact_precios_mensuales", "fact_consumo_gas_mensual",
                  "fact_produccion_mensual"],
}

# Qué serie protagoniza cada bloque del dashboard (todas deben existir en dim_serie).
BANNER = {
    "petroleo": {"principal": "RWTC_D", "indicadores": ["RBRTE_D", "WCESTUS1_W"]},
    "gas": {"principal": "RNGWHHD_D", "indicadores": ["NW2_EPG0_SWO_R48_BCF_W", "N9070US2_M"]},
}
BARRAS = {
    "petroleo": {"titulo": "Precio en surtidor por combustible", "categoria": "precio_surtidor"},
    "gas": {"titulo": "Consumo de gas por sector", "categoria": "consumo",
            "excluir": ["N9140US2_M"]},
}
TOTAL_CONSUMO_GAS = "N9140US2_M"


class ExportError(RuntimeError):
    """Gold incompleto o inconsistente para armar el dashboard."""


@dataclass
class ResultadoExport:
    destino: Path
    archivos: dict[str, int]  # nombre -> bytes


# --------------------------------------------------------------------------- formato
def num(x: float, decimales: int = 2) -> str:
    """Número con formato rioplatense: 1.234,56."""
    s = f"{x:,.{decimales}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x: float, decimales: int = 1) -> str:
    return f"{num(abs(x) * 100, decimales)} %"


def fecha_larga(d: date, frecuencia: str) -> str:
    if frecuencia == "monthly":
        return f"{MESES[d.month - 1]} de {d.year}"
    return d.strftime("%d/%m/%Y")


def _iso(v) -> str | None:
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).date().isoformat()


def _float(v) -> float | None:
    return None if v is None or pd.isna(v) else round(float(v), 6)


# --------------------------------------------------------------------------- lectura
def leer_gold(gold_dir: Path) -> dict[str, pd.DataFrame]:
    base = gold_dir / "parquet"
    if not base.exists():
        raise ExportError(f"No hay Gold en {gold_dir}: corré `python -m eia_pulso run` antes")
    nombres = ["dim_serie", "dim_region", "fact_ultimo_dato", "frescura",
               *[t for ts in TABLAS.values() for t in ts]]
    faltan = [n for n in nombres if not (base / f"{n}.parquet").exists()]
    if faltan:
        raise ExportError(f"Faltan tablas Gold: {faltan}")
    return {n: pd.read_parquet(base / f"{n}.parquet") for n in nombres}


def _serie(gold: dict[str, pd.DataFrame], tabla: str, key: str) -> pd.DataFrame:
    df = gold[tabla]
    s = df[df["serie_key"] == key][["fecha", "valor"]].copy()
    s["fecha"] = pd.to_datetime(s["fecha"])
    return s.sort_values("fecha").reset_index(drop=True)


# --------------------------------------------------------------------------- bloques
def construir_series(gold: dict[str, pd.DataFrame]) -> list[dict]:
    regiones = gold["dim_region"].set_index("region_key")["nombre"].to_dict()
    ds = gold["dim_serie"].sort_values(["sector", "categoria", "orden"])
    return [{"key": r.serie_key, "serie_eia": r.serie_eia, "nombre": r.nombre,
             "unidad": r.unidad, "frecuencia": r.frecuencia, "sector": r.sector,
             "categoria": r.categoria, "dataset": r.dataset, "tabla_gold": r.tabla_gold,
             "region": regiones.get(r.region_key, r.region_key),
             "descripcion_eia": r.descripcion_eia} for r in ds.itertuples()]


def construir_ultimo(gold: dict[str, pd.DataFrame]) -> dict[str, dict]:
    return {r.serie_key: {"fecha": _iso(r.fecha), "valor": _float(r.valor),
                          "fecha_anterior": _iso(r.fecha_anterior),
                          "valor_anterior": _float(r.valor_anterior),
                          "variacion_abs": _float(r.variacion_abs),
                          "variacion_pct": _float(r.variacion_pct)}
            for r in gold["fact_ultimo_dato"].itertuples()}


def construir_hechos(gold: dict[str, pd.DataFrame], tablas: list[str]) -> dict[str, list]:
    """{serie_key: [[fecha, valor], ...]} ordenado por fecha (formato compacto)."""
    out: dict[str, list] = {}
    for t in tablas:
        df = gold[t].sort_values(["serie_key", "fecha"])
        for key, g in df.groupby("serie_key", sort=True):
            out[key] = [[_iso(f), _float(v)] for f, v in zip(g["fecha"], g["valor"], strict=True)]
    return out


def construir_frescura(gold: dict[str, pd.DataFrame]) -> dict:
    f = gold["frescura"]
    return {
        "calculado_al": _iso(f["calculado_al"].max()) if len(f) else None,
        "datasets": [{"dataset": r.dataset, "sector": r.sector, "categoria": r.categoria,
                      "frecuencia": r.frecuencia, "ultimo_periodo": _iso(r.ultimo_periodo),
                      "fin_periodo": _iso(r.fin_periodo), "dias_atraso": int(r.dias_atraso),
                      "umbral_dias": int(r.umbral_dias), "estado": r.estado,
                      "filas": int(r.filas_silver)} for r in f.itertuples()],
    }


def _vs_promedio_12m(s: pd.DataFrame) -> tuple[pd.Series, float]:
    ultimo = s.iloc[-1]
    ventana = s[s["fecha"] > ultimo["fecha"] - pd.DateOffset(years=1)]
    return ultimo, float(ventana["valor"].mean())


def _vs_anio_anterior(s: pd.DataFrame, tolerancia_dias: int = 4) -> tuple[pd.Series, pd.Series]:
    """Último dato y el dato más cercano a un año antes (para series semanales)."""
    ultimo = s.iloc[-1]
    objetivo = ultimo["fecha"] - pd.DateOffset(years=1)
    dist = (s["fecha"] - objetivo).abs()
    i = dist.idxmin()
    if dist[i] > pd.Timedelta(days=tolerancia_dias):
        raise ExportError(f"No hay dato de hace un año cerca de {objetivo.date()}")
    return ultimo, s.loc[i]


def _frase_precio(nombre: str, unidad_txt: str, s: pd.DataFrame, origen: str) -> dict:
    ultimo, prom = _vs_promedio_12m(s)
    dif = ultimo["valor"] / prom - 1
    sentido = "por encima" if dif >= 0 else "por debajo"
    return {
        "texto": (f"{nombre} cerró en US$ {num(ultimo['valor'])} {unidad_txt} el "
                  f"{fecha_larga(ultimo['fecha'].date(), 'daily')}, un {pct(dif)} {sentido} "
                  f"de su promedio de los últimos 12 meses (US$ {num(prom)})."),
        "valores": {"ultimo": round(float(ultimo["valor"]), 4), "promedio_12m": round(prom, 4),
                    "variacion_pct": round(dif, 6)},
        "fecha": _iso(ultimo["fecha"]), "origen": origen,
    }


def _frase_stock(texto_inicio: str, s: pd.DataFrame, divisor: float, unidad_txt: str,
                 decimales: int, origen: str) -> dict:
    ultimo, previo = _vs_anio_anterior(s)
    dif = ultimo["valor"] / previo["valor"] - 1
    sentido = "más" if dif >= 0 else "menos"
    return {
        "texto": (f"{texto_inicio} {num(ultimo['valor'] / divisor, decimales)} {unidad_txt} "
                  f"al {fecha_larga(ultimo['fecha'].date(), 'weekly')}: un {pct(dif)} {sentido} "
                  f"que en la misma semana del año anterior."),
        "valores": {"ultimo": float(ultimo["valor"]), "anio_anterior": float(previo["valor"]),
                    "variacion_pct": round(dif, 6)},
        "fecha": _iso(ultimo["fecha"]), "origen": origen,
    }


def frases_petroleo(gold: dict[str, pd.DataFrame]) -> list[dict]:
    wti = _serie(gold, "fact_precios_diarios", "RWTC_D")
    brent = _serie(gold, "fact_precios_diarios", "RBRTE_D")
    comun = wti.merge(brent, on="fecha", suffixes=("_wti", "_brent"))
    if comun.empty:
        raise ExportError("WTI y Brent no comparten fechas")
    u = comun.iloc[-1]
    spread = float(u["valor_brent"] - u["valor_wti"])
    sentido = "por encima" if spread >= 0 else "por debajo"
    return [
        _frase_precio("El WTI", "por barril", wti, "fact_precios_diarios · RWTC_D"),
        {"texto": (f"El Brent cotizó US$ {num(abs(spread))} {sentido} del WTI el "
                   f"{fecha_larga(u['fecha'].date(), 'daily')}: es la prima del crudo "
                   f"marítimo internacional sobre el de Cushing."),
         "valores": {"wti": float(u["valor_wti"]), "brent": float(u["valor_brent"]),
                     "diferencial": round(spread, 4)},
         "fecha": _iso(u["fecha"]), "origen": "fact_precios_diarios · RBRTE_D − RWTC_D"},
        _frase_stock("Los inventarios comerciales de crudo suman",
                     _serie(gold, "fact_inventarios_semanales", "WCESTUS1_W"), 1000,
                     "millones de barriles", 1, "fact_inventarios_semanales · WCESTUS1_W"),
    ]


def frases_gas(gold: dict[str, pd.DataFrame]) -> list[dict]:
    consumo = gold["fact_consumo_gas_mensual"]
    ultima = consumo[consumo["serie_key"] == TOTAL_CONSUMO_GAS]["fecha"].max()
    mes = consumo[consumo["fecha"] == ultima].set_index("serie_key")["valor"]
    total = float(mes[TOTAL_CONSUMO_GAS])
    sectores = mes.drop(TOTAL_CONSUMO_GAS)
    top = sectores.idxmax()
    nombre = gold["dim_serie"].set_index("serie_key").loc[top, "nombre"]
    share = float(sectores[top]) / total
    return [
        _frase_precio("El Henry Hub", "por millón de BTU",
                      _serie(gold, "fact_precios_diarios", "RNGWHHD_D"),
                      "fact_precios_diarios · RNGWHHD_D"),
        _frase_stock("El gas almacenado en los 48 estados contiguos suma",
                     _serie(gold, "fact_almacenamiento_gas_semanal", "NW2_EPG0_SWO_R48_BCF_W"),
                     1, "Bcf", 0, "fact_almacenamiento_gas_semanal · R48"),
        {"texto": (f"{nombre} fue el principal destino del gas en "
                   f"{fecha_larga(pd.Timestamp(ultima).date(), 'monthly')}: "
                   f"{pct(share)} del consumo total del país."),
         "valores": {"sector": top, "consumo": float(sectores[top]), "total": total,
                     "participacion": round(share, 6)},
         "fecha": _iso(ultima),
         "origen": f"fact_consumo_gas_mensual · {top} / {TOTAL_CONSUMO_GAS}"},
    ]


def construir_barras(gold: dict[str, pd.DataFrame], ultimo: dict[str, dict]) -> dict:
    ds = gold["dim_serie"].sort_values("orden")
    out = {}
    for sector, cfg in BARRAS.items():
        filas = ds[(ds["sector"] == sector) & (ds["categoria"] == cfg["categoria"])
                   & ~ds["serie_key"].isin(cfg.get("excluir", []))]
        items = [{"key": r.serie_key, "nombre": r.nombre, **ultimo[r.serie_key]}
                 for r in filas.itertuples()]
        fechas = {i["fecha"] for i in items}
        out[sector] = {"titulo": cfg["titulo"], "unidad": filas["unidad"].iloc[0],
                       "fecha": max(fechas), "fechas_distintas": len(fechas) > 1,
                       "items": sorted(items, key=lambda i: -(i["valor"] or 0))}
    return out


def construir_destacados(gold: dict[str, pd.DataFrame], ultimo: dict[str, dict]) -> dict:
    claves = set(gold["dim_serie"]["serie_key"])
    for cfg in BANNER.values():
        faltan = {cfg["principal"], *cfg["indicadores"]} - claves
        if faltan:
            raise ExportError(f"Series del banner ausentes en Gold: {sorted(faltan)}")
    barras = construir_barras(gold, ultimo)
    frases = {"petroleo": frases_petroleo(gold), "gas": frases_gas(gold)}
    return {s: {"banner": BANNER[s], "frases": frases[s], "barras": barras[s]} for s in BANNER}


# --------------------------------------------------------------------------- escritura
def exportar(gold_dir: Path, destino: Path) -> ResultadoExport:
    gold = leer_gold(gold_dir)
    ultimo = construir_ultimo(gold)
    resumen_path = gold_dir / "resumen.json"
    rezago_path = gold_dir / "analisis_rezago.json"
    if not rezago_path.exists() or not resumen_path.exists():
        raise ExportError("Faltan analisis_rezago.json o resumen.json en Gold")
    resumen = json.loads(resumen_path.read_text(encoding="utf-8"))

    archivos = {
        "meta": {"gold_generado_utc": resumen["generado_utc"],
                 "calculado_al": resumen["calculado_al"], "conteos": resumen["conteos"],
                 "fuente": "U.S. Energy Information Administration (EIA), API v2",
                 "fuente_url": "https://www.eia.gov/opendata/"},
        "series": construir_series(gold),
        "ultimo_dato": ultimo,
        **{k: construir_hechos(gold, ts) for k, ts in TABLAS.items()},
        "frescura": construir_frescura(gold),
        "rezago": json.loads(rezago_path.read_text(encoding="utf-8")),
        "destacados": construir_destacados(gold, ultimo),
    }
    destino.mkdir(parents=True, exist_ok=True)
    tamanios = {}
    for nombre, obj in archivos.items():
        texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        (destino / f"{nombre}.json").write_text(texto + "\n", encoding="utf-8")
        tamanios[nombre] = len(texto.encode("utf-8"))
    log.info("JSON web exportados a %s", destino)
    return ResultadoExport(destino, tamanios)
