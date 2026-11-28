// Datos que mueven la escena 3D. Se calculan en el servidor a partir de los JSON de la web
// (los mismos que usan las demás páginas): nada se escribe a mano.
import type { Datos, Geo } from "@/lib/tipos";

export interface Indicador {
  /** serie de la EIA (clave de la web) */
  key: string;
  nombre: string;
  unidad: string;
  valor: number | null;
  fecha: string | null;
  variacion: number | null;
  /** mínimo y máximo de la historia que tiene la web, y desde cuándo */
  min: number;
  max: number;
  desde: string;
  /** posición del último valor dentro de ese rango: 0 = mínimo, 1 = máximo */
  norm: number | null;
}

/** Refinación por estado (EIA-820 y API v2 petroleum/pnp/cap1) para el selector de la escena. */
export interface EstadoRefinacion {
  k: string; nombre: string; n: number; bcd: number;
  mayores: { empresa: string; sitio: string; bcd: number }[];
}
export interface Refinacion { anio: number | null; maxBcd: number; estados: EstadoRefinacion[] }

export function refinacionPorEstado(g: Geo): Refinacion {
  const { estados, refinerias, anio } = g.refinerias;
  const lista = Object.entries(estados).map(([k, e]) => ({
    k, nombre: g.estados.find((x) => x.k === k)?.nombre ?? k, n: e.n, bcd: e.bcd,
    mayores: refinerias.filter((r) => r.estado === k).sort((a, b) => b.bcd - a.bcd).slice(0, 3)
      .map((r) => ({ empresa: r.empresa, sitio: r.sitio, bcd: r.bcd })),
  })).sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  return { anio, maxBcd: Math.max(1, ...lista.map((e) => e.bcd)), estados: lista };
}

export interface DatosPlanta {
  wti: Indicador;
  crudo: Indicador;
  spr: Indicador;
  gas: Indicador;
  produccion: Indicador;
  utilizacion: Indicador;
}

function indicador(d: Datos, key: string, nombre: string, unidad: string): Indicador {
  const serie = d.hechos[key] ?? [];
  const vals = serie.map(([, v]) => v);
  const min = vals.length ? Math.min(...vals) : 0;
  const max = vals.length ? Math.max(...vals) : 0;
  const u = d.ultimo[key];
  const valor = u?.valor ?? null;
  return {
    key, nombre, unidad, valor, fecha: u?.fecha ?? null, variacion: u?.variacion_abs ?? null,
    min, max, desde: serie[0]?.[0] ?? "",
    norm: valor == null || max === min ? null : (valor - min) / (max - min),
  };
}

export function datosPlanta(d: Datos): DatosPlanta {
  return {
    wti: indicador(d, "RWTC_D", "Precio WTI", "US$ por barril"),
    crudo: indicador(d, "WCESTUS1_W", "Crudo comercial", "miles de barriles"),
    spr: indicador(d, "WCSSTUS1_W", "Reserva estratégica (SPR)", "miles de barriles"),
    gas: indicador(d, "NW2_EPG0_SWO_R48_BCF_W", "Gas almacenado (Lower 48)", "Bcf"),
    produccion: indicador(d, "MCRFPUS2_M", "Producción de crudo", "miles de barriles por día"),
    utilizacion: indicador(d, "WPULEUS3_W", "Utilización de refinerías", "% de la capacidad operable"),
  };
}

/** Lo que cuenta cada instalación al pasar el mouse (o al elegirla con el teclado). */
export interface Ficha {
  id: string;
  titulo: string;
  representa: string;
  indicador: keyof DatosPlanta | null;
  zona: Zona;
}

export type Zona = "general" | "costa" | "refineria" | "almacenamiento" | "campo";
