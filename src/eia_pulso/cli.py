"""CLI: python -m eia_pulso run --stage bronze|silver|gold|all  |  export-web --out DIR"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from eia_pulso.config import ConfigError, get_api_key, load_settings
from eia_pulso.log import configurar_logging

log = logging.getLogger("eia_pulso")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eia_pulso", description="Pulso Energético de EE. UU.")
    sub = p.add_subparsers(dest="comando", required=True)
    run = sub.add_parser("run", help="Ejecuta una o todas las capas del pipeline")
    run.add_argument("--stage", choices=["bronze", "silver", "gold", "all"], default="all")
    run.add_argument("--config", help="Ruta al YAML (default: config/pipeline.yaml)")
    run.add_argument("--data-dir", help="Carpeta de datos (default: data/)")
    run.add_argument("--datasets", help="Lista separada por comas (default: todos)")
    run.add_argument("--completo", action="store_true",
                     help="Bronze: ignora la carga incremental y pide desde la fecha de inicio")
    run.add_argument("--hoy", type=date.fromisoformat,
                     help="Fecha de referencia YYYY-MM-DD (para pruebas/reprocesos)")
    run.add_argument("-v", "--verbose", action="store_true")
    web = sub.add_parser("export-web", help="Exporta Gold a JSON para el dashboard web")
    web.add_argument("--config", help="Ruta al YAML (default: config/pipeline.yaml)")
    web.add_argument("--data-dir", help="Carpeta de datos (default: data/)")
    web.add_argument("--out", default="web/public/data", help="Carpeta destino de los JSON")
    web.add_argument("--solo-geo", action="store_true",
                     help="Exporta solo la capa geoespacial (no toca los JSON diarios)")
    web.add_argument("-v", "--verbose", action="store_true")
    geo = sub.add_parser("geo", help="Capa geoespacial (requiere el extra 'geo')")
    geo.add_argument("--stage", choices=["bronze", "bronze-api", "silver", "gold", "all"],
                     default="all",
                     help="bronze = capas estáticas; bronze-api = flujos y centrales")
    geo.add_argument("--config", help="Ruta al YAML (default: config/pipeline.yaml)")
    geo.add_argument("--data-dir", help="Carpeta de datos (default: data/)")
    geo.add_argument("-v", "--verbose", action="store_true")
    return p


def _geo(args: argparse.Namespace, settings) -> int:
    from eia_pulso.geo.config import load_geo

    cfg = load_geo(args.config, args.data_dir)
    etapas = (["bronze", "bronze-api", "silver", "gold"] if args.stage == "all"
              else [args.stage])
    if "bronze" in etapas:
        from eia_pulso.geo.bronze import bronze_capas

        _tabla("Bronze geo", {k: v.name for k, v in bronze_capas(cfg).items()})
    if "bronze-api" in etapas:
        from eia_pulso.api.client import EIAClient
        from eia_pulso.geo.bronze import bronze_api

        cliente = EIAClient(get_api_key(), settings.api_base, settings.tamanio_pagina,
                            settings.max_reintentos, settings.backoff_base_s, settings.timeout_s)
        _tabla("Bronze geo (API)", {k: v.name for k, v in bronze_api(cfg, settings,
                                                                      cliente).items()})
    if "silver" in etapas:
        from eia_pulso.geo.silver import run_silver

        _tabla("Silver geo", {k: f"{len(v):>6} filas" for k, v in run_silver(cfg).items()})
    if "gold" in etapas:
        from eia_pulso.geo.gold import run_gold

        r = run_gold(cfg)
        _tabla("Gold geo · validación", r["validacion"])
    return 0


def _tabla(titulo: str, filas: dict[str, object]) -> None:
    print(f"\n== {titulo} ==")
    ancho = max((len(k) for k in filas), default=10)
    for k, v in filas.items():
        print(f"  {k:<{ancho}}  {v}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    for flujo in (sys.stdout, sys.stderr):  # consola de Windows: forzar UTF-8 (acentos)
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    configurar_logging(args.verbose)
    try:
        settings = load_settings(args.config, args.data_dir)
        if args.comando == "geo":
            return _geo(args, settings)
        if args.comando == "export-web":
            from pathlib import Path

            from eia_pulso.web.export import exportar

            if not args.solo_geo:
                res = exportar(settings.gold_dir, Path(args.out))
                _tabla(f"JSON web en {res.destino}",
                       {k: f"{v:>9,} bytes" for k, v in res.archivos.items()})
            from eia_pulso.web.export_geo import exportar_geo

            geo = exportar_geo(settings.gold_dir / "geo", Path(args.out))
            if geo:
                _tabla("JSON geo", {k: f"{v:>9,} bytes" for k, v in geo.items()})
            return 0
        datasets = [d.strip() for d in args.datasets.split(",")] if args.datasets else None
        if datasets:
            faltan = set(datasets) - set(settings.datasets)
            if faltan:
                raise ConfigError(f"Datasets inexistentes: {sorted(faltan)}")
        etapas = ["bronze", "silver", "gold"] if args.stage == "all" else [args.stage]

        if "bronze" in etapas:
            from eia_pulso.api.client import EIAClient
            from eia_pulso.bronze.ingest import run_bronze

            key = get_api_key()
            configurar_logging(args.verbose, secretos=[key])
            cliente = EIAClient(key, settings.api_base, settings.tamanio_pagina,
                                settings.max_reintentos, settings.backoff_base_s,
                                settings.timeout_s)
            res = run_bronze(settings, cliente, datasets=datasets, completo=args.completo)
            _tabla("Bronze (filas descargadas)",
                   {r.dataset: f"{r.filas:>7}  desde {r.inicio}" for r in res})

        if "silver" in etapas:
            from eia_pulso.silver.transform import run_silver

            rs = run_silver(settings, hoy=args.hoy, datasets=datasets)
            _tabla("Silver (insertadas / total / descartes)", {
                d: f"{rs.insertadas[d]:>7} / {rs.total_silver[d]:>7}  {rs.descartes[d] or ''}"
                for d in rs.insertadas
            })
            print(f"  revisiones nuevas auditadas: {rs.revisiones_nuevas}")

        if "gold" in etapas:
            from eia_pulso.gold.build import run_gold

            rg = run_gold(settings, hoy=args.hoy)
            _tabla("Gold (filas por tabla)", {k: f"{v:>7}" for k, v in rg.conteos.items()})
            _tabla("Frescura", {
                f.dataset: f"{f.estado:<9} último={f.ultimo_periodo} atraso={f.dias_atraso}d"
                for f in rg.frescura.itertuples()
            })
            print("\n== Rezago WTI -> producción de crudo ==")
            for e in rg.rezago["escenarios"]:
                print(f"  {e['etiqueta']:<28} óptimo: {e['rezago_optimo_meses']} meses "
                      f"(r={e['correlacion']}, n={e['n_obs']})")
            print(f"  {rg.rezago['advertencia']}")
        return 0
    except ConfigError as exc:
        log.error("%s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI: mensaje claro y exit code != 0
        log.error("La corrida falló: %s", exc)
        if args.verbose:
            log.exception("Detalle")
        return 1


if __name__ == "__main__":
    sys.exit(main())
