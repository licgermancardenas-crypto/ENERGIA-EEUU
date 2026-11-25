"""Lectura/escritura de Silver en Parquet particionado por año y mes (append-only)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CLAVE = ["dataset", "serie", "periodo"]

ESQUEMA_SILVER = pa.schema(
    [
        ("dataset", pa.string()),
        ("serie", pa.string()),
        ("periodo", pa.date32()),
        ("valor", pa.float64()),
        ("frecuencia", pa.string()),
        ("unidad", pa.string()),
        ("descripcion", pa.string()),
        ("duoarea", pa.string()),
        ("area_nombre", pa.string()),
        ("producto", pa.string()),
        ("producto_nombre", pa.string()),
        ("proceso", pa.string()),
        ("proceso_nombre", pa.string()),
        ("archivo_bronze", pa.string()),
        ("extraido_utc", pa.string()),
        ("cargado_utc", pa.string()),
    ]
)

ESQUEMA_REVISIONES = pa.schema(
    [
        ("dataset", pa.string()),
        ("serie", pa.string()),
        ("periodo", pa.date32()),
        ("valor_cargado", pa.float64()),
        ("valor_nuevo", pa.float64()),
        ("archivo_bronze", pa.string()),
        ("extraido_utc", pa.string()),
        ("detectado_utc", pa.string()),
    ]
)

DIR_REVISIONES = "_auditoria_revisiones"


def _vacio(esquema: pa.Schema) -> pd.DataFrame:
    df = esquema.empty_table().to_pandas()
    df["periodo"] = pd.Series(dtype="datetime64[ns]")
    return df


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["periodo"] = pd.to_datetime(df["periodo"]).astype("datetime64[ns]")
    return df


def _sql_path(p: Path) -> str:
    return p.as_posix().replace("'", "''")


def leer_silver(silver_dir: Path, dataset: str | None = None) -> pd.DataFrame:
    """Lee todo Silver (o un dataset). Devuelve un DataFrame vacío con esquema si no hay datos."""
    patron = f"{dataset}/anio=*/mes=*/*.parquet" if dataset else "*/anio=*/mes=*/*.parquet"
    if not any(silver_dir.glob(patron)):
        return _vacio(ESQUEMA_SILVER)
    cols = ", ".join(ESQUEMA_SILVER.names)
    sql = (
        f"SELECT {cols} FROM read_parquet('{_sql_path(silver_dir)}/{patron}', "
        "hive_partitioning = true, union_by_name = true)"
    )
    with duckdb.connect() as con:
        df = con.execute(sql).df()
    return _normalizar(df)


def max_periodo(silver_dir: Path, dataset: str) -> pd.Timestamp | None:
    df = leer_silver(silver_dir, dataset)
    return None if df.empty else df["periodo"].max()


def escribir_particiones(df: pd.DataFrame, silver_dir: Path, run_id: str) -> list[Path]:
    """Escribe un archivo nuevo por dataset/año/mes. Nunca reescribe archivos existentes."""
    escritos: list[Path] = []
    if df.empty:
        return escritos
    df = _normalizar(df)
    df["_anio"] = df["periodo"].dt.year
    df["_mes"] = df["periodo"].dt.month
    for (dataset, anio, mes), grupo in df.groupby(["dataset", "_anio", "_mes"], sort=True):
        destino = silver_dir / str(dataset) / f"anio={anio}" / f"mes={mes:02d}"
        destino.mkdir(parents=True, exist_ok=True)
        archivo = destino / f"part-{run_id}.parquet"
        if archivo.exists():
            raise FileExistsError(f"Silver no se sobrescribe: {archivo}")
        datos = grupo.drop(columns=["_anio", "_mes"]).copy()
        datos["periodo"] = datos["periodo"].dt.date
        tabla = pa.Table.from_pandas(datos[ESQUEMA_SILVER.names], schema=ESQUEMA_SILVER,
                                     preserve_index=False)
        pq.write_table(tabla, archivo)
        escritos.append(archivo)
    return escritos


def leer_revisiones(silver_dir: Path) -> pd.DataFrame:
    carpeta = silver_dir / DIR_REVISIONES
    if not any(carpeta.glob("*.parquet")):
        return _vacio(ESQUEMA_REVISIONES)
    with duckdb.connect() as con:
        df = con.execute(
            f"SELECT * FROM read_parquet('{_sql_path(carpeta)}/*.parquet')"
        ).df()
    return _normalizar(df)


def escribir_revisiones(df: pd.DataFrame, silver_dir: Path, run_id: str) -> Path | None:
    if df.empty:
        return None
    carpeta = silver_dir / DIR_REVISIONES
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"part-{run_id}.parquet"
    if archivo.exists():
        raise FileExistsError(f"La auditoría no se sobrescribe: {archivo}")
    datos = _normalizar(df)
    datos["periodo"] = datos["periodo"].dt.date
    pq.write_table(
        pa.Table.from_pandas(datos[ESQUEMA_REVISIONES.names], schema=ESQUEMA_REVISIONES,
                             preserve_index=False),
        archivo,
    )
    return archivo
