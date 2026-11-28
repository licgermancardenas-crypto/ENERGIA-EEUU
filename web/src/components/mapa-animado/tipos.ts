import type { EstadoGeo, Geo, Punto2 } from "@/lib/tipos";

/** Lo que el servidor le pasa al mapa animado (la geometría se baja en el navegador). */
export interface DatosMapa {
  estados: Pick<EstadoGeo, "k" | "nombre" | "km" | "operadores" | "region" | "centro" | "hh" | "densidad" | "pct_gas_red">[];
  hubs: Punto2[];
  gnl: Punto2[];
  henryHub: Geo["henryHub"];
  fuentes: Geo["fuentes"];
  precioHH: number | null;
  fechaHH: string | null;
  /** gas almacenado de la última semana por región de la EIA (R31..R35), en Bcf */
  gasRegion: Record<string, number>;
  gasTotal: number | null;
  /** km totales de la capa de gasoductos (validación de Gold geo) */
  kmRed: number;
  fechaGas: string | null;
}

export const NOMBRE_REGION: Record<string, string> = {
  R31: "Este", R32: "Medio Oeste", R33: "Centro Sur", R34: "Montaña", R35: "Pacífico",
};
