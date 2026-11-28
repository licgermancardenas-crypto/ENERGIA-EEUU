// Datos de la historia "Del pozo al surtidor" (portada). Todo sale de archivos que el sitio ya
// publica; si un dato falta, la etapa queda sin cifra (no se estima nada).
import { readFileSync } from "node:fs";
import path from "node:path";

import { cargarDatos, cargarGeo } from "./datos";

export interface DatoHistoria {
  valor: number; decimales: number; unidad: string; fecha: string; fuente: string; prefijo?: string;
}
export interface EtapaHistoria {
  id: string; numero: number; titulo: string; texto: string;
  dato: DatoHistoria | null;
  /** datos secundarios ya formateados por el servidor (con unidad, fecha y fuente) */
  extra: string[];
  imagen: { clave: string; alt: string };
  mapa: { recuadro: [[number, number], [number, number]]; capas: ("plataformas" | "oleoductos" | "refinerias" | "puertos")[] };
  nota?: string;
}

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const mes = (iso: string) => `${MESES[Number(iso.slice(5, 7)) - 1]} de ${iso.slice(0, 4)}`;
const dia = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
const n = (v: number, d = 0) => new Intl.NumberFormat("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);

function leer<T>(rel: string): T | null {
  try { return JSON.parse(readFileSync(path.join(process.cwd(), "public", rel), "utf-8")) as T; } catch { return null; }
}

export function etapasHistoria(): EtapaHistoria[] {
  const d = cargarDatos();
  const u = (k: string) => d.ultimo[k];
  const etapas: EtapaHistoria[] = [];

  // 1 · Pozo / plataforma: producción de crudo (serie mensual ya cargada)
  const prod = u("MCRFPUS2_M");
  etapas.push({
    id: "pozo", numero: 1, titulo: "El pozo",
    texto: "Todo empieza bajo tierra o bajo el mar. Buena parte del crudo de EE. UU. sale de la cuenca Permian, entre Texas y Nuevo México, y de las plataformas del Golfo de México.",
    dato: prod ? { valor: prod.valor, decimales: 0, unidad: "miles de barriles por día", fecha: mes(prod.fecha), fuente: "EIA, producción de crudo de EE. UU. (MCRFPUS2)" } : null,
    extra: [],
    imagen: { clave: "1-pozo", alt: "Bombas de varilla en un campo petrolero de Texas" },
    mapa: { recuadro: [[-106.5, 25.5], [-86.5, 34.5]], capas: ["plataformas"] },
  });
  // 2 · Oleoducto: km de la capa de la EIA (verificada y publicada en el mapa de petróleo)
  const mp = leer<{ fecha_descarga: string; capas: Record<string, { km_total?: number }> }>("data/petroleo/meta.json");
  const kmOle = mp?.capas.oleoductos?.km_total, kmPol = mp?.capas.poliductos?.km_total;
  etapas.push({
    id: "oleoducto", numero: 2, titulo: "El oleoducto",
    texto: "Del campo, el crudo viaja por oleoductos troncales hacia las refinerías y los puertos. Cushing, en Oklahoma, es uno de sus nudos y el punto de entrega del precio WTI.",
    dato: kmOle != null && mp ? { valor: kmOle, decimales: 0, unidad: "km de oleoductos de crudo en la capa de la EIA",
      fecha: `capa descargada el ${mp.fecha_descarga.split("-").reverse().join("/")}`, fuente: "EIA, Crude Oil Trunk Pipelines (largo calculado en EPSG:5070)" } : null,
    extra: kmPol != null ? [`Además, ${n(kmPol, 0)} km de poliductos de derivados en la misma fuente. Es lo que mapea la EIA, no el total de la red del país.`] : [],
    imagen: { clave: "2-oleoducto", alt: "Oleoducto elevado sobre la tundra al atardecer" },
    mapa: { recuadro: [[-106, 26.5], [-82, 42]], capas: ["oleoductos"] },
    nota: "En el mapa, los pulsos que recorren los oleoductos son una animación ilustrativa: la EIA no publica el flujo por ducto.",
  });
  // 3 · Refinería: utilización (semanal) y capacidad (EIA-820, 1/1 del año)
  const g = cargarGeo();
  const util = u("WPULEUS3_W");
  const capTotal = Object.values(g.refinerias.estados).reduce((s, e) => s + e.bcd, 0);
  etapas.push({
    id: "refineria", numero: 3, titulo: "La refinería",
    texto: "En la refinería el crudo se separa y se transforma en gasolina, diésel y otros productos. Buena parte de la capacidad del país está sobre la Costa del Golfo.",
    dato: util ? { valor: util.valor, decimales: 1, unidad: "% de la capacidad operable en uso", fecha: `semana al ${dia(util.fecha)}`,
      fuente: "EIA, utilización de refinerías (WPULEUS3)" } : null,
    extra: capTotal > 0 ? [`Capacidad de destilación de crudo: ${n(capTotal, 0)} barriles por día en ${g.refinerias.refinerias.length} refinerías, al 1/1/${g.refinerias.anio ?? ""} (EIA, Refinery Capacity Report).`] : [],
    imagen: { clave: "3-refineria", alt: "Vista aérea de una refinería junto al Golfo de México, cerca de Houston" },
    mapa: { recuadro: [[-98, 27.3], [-88, 31.2]], capas: ["refinerias"] },
  });
  return etapas;
}
