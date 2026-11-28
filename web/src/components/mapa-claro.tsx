"use client";

// Utilidades de los mapas claros (MapLibre sobre OpenFreeMap, sin clave): estilo base, recuadro
// de una geometría y ficha HTML segura (textContent) para los popups. Las usa el mapa de condados.
import "maplibre-gl/dist/maplibre-gl.css";

export const ESTILO = "https://tiles.openfreemap.org/styles/positron";
/** Recuadro [oeste, sur, este, norte] de una geometría GeoJSON. */
export function recuadro(geom: { coordinates: unknown }): [number, number, number, number] {
  const b: [number, number, number, number] = [180, 90, -180, -90];
  const recorrer = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === "number") {
      const [x, y] = c as number[];
      if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y;
    } else if (Array.isArray(c)) c.forEach(recorrer);
  };
  recorrer(geom.coordinates);
  return b;
}

export function ficha(filas: [string, string][], titulo: string): HTMLElement {
  const div = document.createElement("div");
  div.className = "text-xs";
  const h = document.createElement("p");
  h.className = "mb-1 text-[13px] font-semibold text-[#1b1f24]";
  h.textContent = titulo;
  div.appendChild(h);
  for (const [k, v] of filas) {
    const p = document.createElement("p");
    p.className = "text-[#4a5260]";
    p.textContent = `${k}: ${v}`;
    div.appendChild(p);
  }
  return div;
}
