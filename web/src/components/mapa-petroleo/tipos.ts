// Datos del mapa de petróleo que arma el servidor (KPIs y metadatos chicos). La geometría y las
// series se bajan en el navegador desde web/public/data/petroleo/ (scripts/preparar_mapa_petroleo.py).
export interface MetaCapa {
  origen: string | null; url: string | null; vintage: string | null; licencia: string | null;
  elementos: number | null; bytes: number; km_total?: number; nota?: string;
}
export interface MetaPetroleo {
  fecha_descarga: string;
  capas: Record<string, MetaCapa>;
  no_disponibles: { capa: string; motivo: string }[];
  cushing: { nombre: string; lon: number; lat: number; fuente: string };
}
export interface Kpi { valor: number | null; fecha: string | null }
export interface DatosMapaPetroleo {
  meta: MetaPetroleo;
  wti: Kpi; crudo: Kpi; utilizacion: Kpi; spr: Kpi;
  nombresEstados: Record<string, string>;
}
export interface SeriesPetroleo {
  unidad: string;
  produccion_estado: Record<string, Record<string, number>>;
  produccion_padd: Record<string, Record<string, number>>;
  offshore_golfo: Record<string, number>;
  produccion_nacional_mensual: [string, number][];
  comercio_crudo_padd: { importaciones: Record<string, Record<string, number>>; exportaciones: Record<string, Record<string, number>> };
  rutas: Record<string, string>;
}
export const NOMBRE_PADD: Record<string, string> = {
  R10: "PADD 1 · Costa Este", R20: "PADD 2 · Medio Oeste", R30: "PADD 3 · Costa del Golfo",
  R40: "PADD 4 · Montañas Rocosas", R50: "PADD 5 · Costa Oeste", NUS: "EE. UU.",
};
