// Datos de la historia "Del pozo al surtidor" (portada). Todo sale de archivos que el sitio ya
// publica; si un dato falta, la etapa queda sin cifra (no se estima nada).
import { cargarDatos } from "./datos";

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
  return etapas;
}
