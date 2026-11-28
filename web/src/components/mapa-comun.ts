"use client";

// Piezas compartidas por los mapas oscuros de la web (gas en /mapa y petróleo en /petroleo-red):
// estilo base, encuadre, creación del mapa con el overlay de deck.gl y marcador que late.
// El modo de visualización está aparte, en modo-mapa.ts, para no arrastrar deck.gl.
import { MapboxOverlay } from "@deck.gl/mapbox";
import type maplibreglTipos from "maplibre-gl";

import { ESTILO_OSCURO, LOWER48, type Recuadro } from "./mapa-estilos";

export { ESTILO_OSCURO, LOWER48, type Recuadro };

type MaplibreGL = typeof maplibreglTipos;

/** Mapa oscuro de OpenFreeMap con controles y un overlay de deck.gl (no intercalado). */
export function crearMapaOscuro(gl: MaplibreGL, contenedor: HTMLElement,
  { controles = true, maxZoom = 11 }: { controles?: boolean; maxZoom?: number } = {}) {
  const mapa = new gl.Map({
    container: contenedor, style: ESTILO_OSCURO, bounds: LOWER48, fitBoundsOptions: { padding: 30 },
    maxPitch: 70, attributionControl: { compact: false }, maxZoom,
  });
  if (controles) {
    mapa.addControl(new gl.NavigationControl({ visualizePitch: true }), "top-left");
    mapa.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-right");
  }
  const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
  mapa.addControl(overlay);
  // el estilo oscuro pide un ícono ("circle-11") que no trae su sprite: se reemplaza por uno vacío
  mapa.on("styleimagemissing", (e) => {
    if (!mapa.hasImage(e.id)) mapa.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) });
  });
  return { mapa, overlay };
}

/** Marcador HTML con anillo que late (CSS .hh-*; se apaga con movimiento reducido). */
export function marcadorLatido(gl: MaplibreGL, mapa: maplibreglTipos.Map,
  { lon, lat, titulo, lineas, etiqueta }: { lon: number; lat: number; titulo: string; lineas: string[]; etiqueta: string }) {
  const el = document.createElement("div");
  el.className = "hh-marcador";
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", etiqueta);
  const anillo = document.createElement("span");
  anillo.className = "hh-anillo";
  const punto = document.createElement("span");
  punto.className = "hh-punto";
  const nota = document.createElement("span");
  nota.className = "hh-nota";
  const t = document.createElement("strong");
  t.textContent = titulo;
  nota.append(t, ...lineas.filter(Boolean).map((l, i) => {
    const s = document.createElement(i === lineas.length - 1 && lineas.length > 1 ? "small" : "span");
    s.textContent = l;
    return s;
  }));
  el.append(anillo, punto, nota);
  return new gl.Marker({ element: el, anchor: "center" }).setLngLat([lon, lat]).addTo(mapa);
}
