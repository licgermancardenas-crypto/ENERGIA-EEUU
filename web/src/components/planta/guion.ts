// Recorrido del modo grabación de /planta (?record=1), ~20 s. Documentado en
// docs/guion-video-3d.md: si cambiás algo acá, actualizá también el documento.
import type { Zona } from "./tipos";

export interface PasoPlanta {
  t: number;
  zona: Zona;
  /** giro de la cámara alrededor de la zona, en grados (0 = vista isométrica base) */
  giro: number;
  titulo?: boolean;
}

export const GUION_PLANTA: PasoPlanta[] = [
  { t: 0, zona: "general", giro: 0 },
  { t: 2.5, zona: "costa", giro: -20 },
  { t: 6.5, zona: "refineria", giro: 10 },
  { t: 10.5, zona: "almacenamiento", giro: 25 },
  { t: 14, zona: "campo", giro: 40 },
  { t: 17, zona: "general", giro: 60 },
  { t: 18.5, zona: "general", giro: 60, titulo: true },
];
