// Recorrido del modo grabación (?record=1), ~20 s. Documentado en docs/guion-video.md:
// si cambiás tiempos o cámaras acá, actualizá también el documento.
type Camara =
  | { bounds: [[number, number], [number, number]]; pitch?: number; bearing?: number }
  | { center: [number, number]; zoom: number; pitch?: number; bearing?: number };

export interface Paso {
  /** segundo en que arranca */
  t: number;
  /** duración del movimiento de cámara, en ms */
  duracion: number;
  camara?: Camara;
  capas?: string[];
  tresD?: boolean;
  titulo?: boolean;
}

export const GUION: Paso[] = [
  // 0 s: país completo, la red se enciende y salen los primeros pulsos
  { t: 0, duracion: 0, camara: { bounds: [[-125, 24], [-66.5, 49.5]] }, capas: ["Gasoductos", "Pulsos"] },
  // 2 s: vuelo al Golfo de México y el Henry Hub
  { t: 2, duracion: 4000, camara: { center: [-92.06, 29.9], zoom: 5.6, pitch: 45, bearing: -15 } },
  // 6,5 s: los pulsos suben hacia el noreste
  { t: 6.5, duracion: 3500, camara: { center: [-81, 37.5], zoom: 4.9, pitch: 50, bearing: 20 } },
  // 10 s: Medio Oeste
  { t: 10, duracion: 3000, camara: { center: [-89, 41], zoom: 4.8, pitch: 50, bearing: -10 } },
  // 13 s: flujos reales entre estados y almacenamiento en 3D, vista nacional inclinada
  { t: 13, duracion: 3500, camara: { center: [-95, 37.5], zoom: 3.7, pitch: 55, bearing: -20 },
    capas: ["Gasoductos", "Pulsos", "Flujos entre estados", "Almacenamiento"], tresD: true },
  // 17,5 s: cierre con título y fuente
  { t: 17.5, duracion: 0, titulo: true },
];
