// Constantes livianas de los mapas oscuros (sin deck.gl): las usan los mapas y la historia de la portada.
export const ESTILO_OSCURO = "https://tiles.openfreemap.org/styles/dark";
export type Recuadro = [[number, number], [number, number]];
export const LOWER48: Recuadro = [[-125, 24], [-66.5, 49.5]];

// ------------------------------------------------------------------ B1: tono según la hora local
// Solo cambia el color del fondo y del agua del mapa base (nunca datos). Tonos apenas distintos del
// negro del estilo original: madrugada azulada, día gris azulado, atardecer cálido, noche neutra.
export type Momento = "amanecer" | "dia" | "atardecer" | "noche";
export function momentoDelDia(h: number): Momento {
  if (h >= 5 && h < 8) return "amanecer";
  if (h >= 8 && h < 17) return "dia";
  if (h >= 17 && h < 20) return "atardecer";
  return "noche";
}
export const TONOS: Record<Momento, { fondo: string; agua: string }> = {
  amanecer: { fondo: "#10121c", agua: "#1c2236" },
  dia: { fondo: "#11161d", agua: "#1a2633" },
  atardecer: { fondo: "#17110f", agua: "#2a1f22" },
  noche: { fondo: "#0c0c0c", agua: "#1b1b1d" },
};

/** Aplica el tono de la hora local al mapa (fundido de 1,2 s salvo movimiento reducido). */
export function aplicarTonoHorario(mapa: { setPaintProperty: (l: string, p: string, v: unknown) => void; getLayer: (id: string) => unknown },
  animar: boolean, ahora = new Date()) {
  const t = TONOS[momentoDelDia(ahora.getHours())];
  const dur = { duration: animar ? 1200 : 0, delay: 0 };
  if (mapa.getLayer("background")) {
    mapa.setPaintProperty("background", "background-color-transition", dur);
    mapa.setPaintProperty("background", "background-color", t.fondo);
  }
  if (mapa.getLayer("water")) {
    mapa.setPaintProperty("water", "fill-color-transition", dur);
    mapa.setPaintProperty("water", "fill-color", t.agua);
  }
}
