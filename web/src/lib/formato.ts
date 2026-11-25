// Formato rioplatense. Solo da forma a números que vienen de Gold: nunca calcula datos nuevos.

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];

export function num(x: number, decimales = 2): string {
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(x);
}

export function compacto(x: number): string {
  return new Intl.NumberFormat("es-AR", { notation: "compact", maximumFractionDigits: 1 }).format(x);
}

export function pctConSigno(x: number, decimales = 1): string {
  const signo = x > 0 ? "+" : x < 0 ? "−" : "±";
  return `${signo}${num(Math.abs(x) * 100, decimales)} %`;
}

/** "2026-11-17" -> "17/11/2026" (sin pasar por Date: evita corrimientos de zona horaria). */
export function fechaCorta(iso: string): string {
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

export function fechaEje(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES[Number(m) - 1]} ${a.slice(2)}`;
}

export function mesAnio(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES_LARGOS[Number(m) - 1]} ${a}`;
}

export function fechaSegunFrecuencia(iso: string, frecuencia: string): string {
  return frecuencia === "monthly" ? mesAnio(iso) : fechaCorta(iso);
}

const DECIMALES: Record<string, number> = {
  "$/BBL": 2, "$/MMBTU": 2, "$/GAL": 3, MBBL: 0, "MBBL/D": 0, BCF: 0, MMCF: 0,
};

export const UNIDADES: Record<string, { corta: string; larga: string }> = {
  "$/BBL": { corta: "US$/barril", larga: "dólares por barril" },
  "$/MMBTU": { corta: "US$/MMBtu", larga: "dólares por millón de BTU" },
  "$/GAL": { corta: "US$/galón", larga: "dólares por galón" },
  MBBL: { corta: "miles de barriles", larga: "miles de barriles" },
  "MBBL/D": { corta: "miles de barriles/día", larga: "miles de barriles por día" },
  BCF: { corta: "Bcf", larga: "miles de millones de pies cúbicos" },
  MMCF: { corta: "MMcf", larga: "millones de pies cúbicos" },
};

export function valor(x: number, unidad: string): string {
  return num(x, DECIMALES[unidad] ?? 2);
}

export function etiquetaFrecuencia(f: string): string {
  return { daily: "diaria", weekly: "semanal", monthly: "mensual" }[f] ?? f;
}

export function comparacion(frecuencia: string): string {
  return { daily: "vs. día hábil anterior", weekly: "vs. semana anterior", monthly: "vs. mes anterior" }[
    frecuencia
  ] ?? "vs. dato anterior";
}
