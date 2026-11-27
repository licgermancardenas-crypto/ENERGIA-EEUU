// Indicadores que muestran las tarjetas: los mismos que las medidas del informe de Power BI.
// Salen del último dato de cada serie y de los valores ya calculados en destacados.json.
import type { Datos, Punto } from "./tipos";

function valorFrase(d: Datos, sector: "petroleo" | "gas", i: number, clave: string): number | null {
  const v = d.destacados[sector]?.frases[i]?.valores[clave];
  return typeof v === "number" ? v : null;
}

/** Valor del mismo mes del año anterior (series mensuales). */
function interanual(serie: Punto[] | undefined): number | null {
  if (!serie?.length) return null;
  const [f, v] = serie[serie.length - 1];
  const previo = serie.find(([g]) => g.slice(0, 7) === `${Number(f.slice(0, 4)) - 1}${f.slice(4, 7)}`);
  return previo ? v / previo[1] - 1 : null;
}

export interface Indicadores {
  wti: number | null; brent: number | null; diferencial: number | null;
  wtiVsProm: number | null; hh: number | null; hhVsProm: number | null;
  crudo: number | null; crudoVsAnio: number | null; spr: number | null; crudoSemanal: number | null;
  gas: number | null; gasVsAnio: number | null; inyeccion: number | null;
  generacion: number | null; produccion: number | null; produccionInteranual: number | null;
  gasSeco: number | null; consumoTotal: number | null; mesProduccion: string | null;
  fuentesAlDia: number; fuentesTotal: number; maxAtraso: number; calculadoAl: string;
}

export function indicadores(d: Datos): Indicadores {
  const u = (k: string) => d.ultimo[k]?.valor ?? null;
  const f = d.frescura.datasets;
  return {
    wti: u("RWTC_D"), brent: u("RBRTE_D"),
    diferencial: valorFrase(d, "petroleo", 1, "diferencial"),
    wtiVsProm: valorFrase(d, "petroleo", 0, "variacion_pct"),
    hh: u("RNGWHHD_D"), hhVsProm: valorFrase(d, "gas", 0, "variacion_pct"),
    crudo: u("WCESTUS1_W"), crudoVsAnio: valorFrase(d, "petroleo", 2, "variacion_pct"),
    spr: u("WCSSTUS1_W"), crudoSemanal: d.ultimo.WCESTUS1_W?.variacion_abs ?? null,
    gas: u("NW2_EPG0_SWO_R48_BCF_W"), gasVsAnio: valorFrase(d, "gas", 1, "variacion_pct"),
    inyeccion: d.ultimo.NW2_EPG0_SWO_R48_BCF_W?.variacion_abs ?? null,
    generacion: valorFrase(d, "gas", 2, "participacion"),
    produccion: u("MCRFPUS2_M"), produccionInteranual: interanual(d.hechos.MCRFPUS2_M),
    gasSeco: u("N9070US2_M"), consumoTotal: u("N9140US2_M"),
    mesProduccion: d.ultimo.MCRFPUS2_M?.fecha ?? null,
    fuentesAlDia: f.filter((x) => x.estado === "al_dia").length, fuentesTotal: f.length,
    maxAtraso: Math.max(...f.map((x) => x.dias_atraso)), calculadoAl: d.frescura.calculado_al,
  };
}

export function estadoDatos(i: Indicadores): { texto: string; ok: boolean } {
  const ok = i.fuentesAlDia === i.fuentesTotal;
  const [a, m, dd] = i.calculadoAl.split("-");
  return {
    ok,
    texto: `${ok ? "Todas las fuentes al día" : `${i.fuentesTotal - i.fuentesAlDia} fuentes atrasadas`}` +
      ` · calculado al ${dd}/${m}/${a}`,
  };
}
