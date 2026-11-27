// Lectura de los JSON de Gold en tiempo de build (export estático): la página llega
// con los datos ya embebidos, sin llamadas a la API ni estados de carga.
import { readFileSync } from "node:fs";
import path from "node:path";

import type { Datos, Destacado, Geo, Frescura, Meta, Punto, Rezago, Sector, Serie, UltimoDato } from "./tipos";

const DIR = path.join(process.cwd(), "public", "data");

function leer<T>(nombre: string): T {
  return JSON.parse(readFileSync(path.join(DIR, `${nombre}.json`), "utf-8")) as T;
}

// Solo las series que grafica el dashboard (el resto queda disponible en /data/*.json).
export const SERIES_GRAFICADAS = [
  "RWTC_D", "RBRTE_D", "RNGWHHD_D",
  "WCESTUS1_W", "WCSSTUS1_W", "NW2_EPG0_SWO_R48_BCF_W",
] as const;

export function cargarDatos(): Datos {
  const series = leer<Serie[]>("series");
  const hechos = {
    ...leer<Record<string, Punto[]>>("diarios"),
    ...leer<Record<string, Punto[]>>("semanales"),
    ...leer<Record<string, Punto[]>>("mensuales"),
  };
  for (const k of SERIES_GRAFICADAS) {
    if (!hechos[k]) throw new Error(`Falta la serie ${k} en public/data`);
  }
  const usados = hechos;
  return {
    meta: leer<Meta>("meta"),
    series: Object.fromEntries(series.map((s) => [s.key, s])),
    ultimo: leer<Record<string, UltimoDato>>("ultimo_dato"),
    hechos: usados,
    frescura: leer<Frescura>("frescura"),
    rezago: leer<Rezago>("rezago"),
    destacados: leer<Record<Sector, Destacado>>("destacados"),
  };
}

// ---------------------------------------------------------------- capa geoespacial
function leerGeo<T>(nombre: string): T {
  return JSON.parse(readFileSync(path.join(DIR, "geo", `${nombre}.json`), "utf-8")) as T;
}

/** Tablas geo (métricas por estado, condados, puntos). La geometría se baja en el navegador. */
export function cargarGeo(): Geo {
  return {
    estados: leerGeo("estados"),
    condados: leerGeo("condados"),
    puntos: leerGeo("puntos"),
    henryHub: leerGeo("henry_hub"),
    frescura: leerGeo("frescura_geo"),
    flujos: leerGeo("flujos"),
    fuentes: leerGeo("fuentes_mapa"),
    validacion: leerGeo("validacion"),
  };
}
