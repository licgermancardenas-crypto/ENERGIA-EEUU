"use client";

// Modo "Refinería real": foto aérea de cada refinería del país sobre el mapa de imágenes del USGS
// (The National Map, ortofotos USDA NAIP; dominio público, sin clave). Las ubicaciones y la
// capacidad son de la EIA (refinerias.json).
import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapaGL } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { num } from "@/lib/formato";
import type { Refineria } from "@/lib/tipos";

export const FOTO_TESELAS =
  "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}";
export const FOTO_ATRIBUCION =
  "Foto: USGS The National Map, ortoimágenes USDA NAIP (dominio público) · Ubicación y capacidad: EIA";
const LOWER48: [[number, number], [number, number]] = [[-125, 24], [-66.5, 49.5]];

export function FotoAerea({ refinerias, elegida, onElegir, animar }:
  { refinerias: Refineria[]; elegida: Refineria | null; onElegir: (id: string) => void; animar: boolean }) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const [listo, setListo] = useState(false);
  const alElegir = useRef(onElegir);
  useEffect(() => { alElegir.current = onElegir; }, [onElegir]);

  useEffect(() => {
    let vivo = true;
    (async () => {
      const gl = await import("maplibre-gl");
      if (!vivo || !caja.current) return;
      const m = new gl.Map({
        container: caja.current, bounds: LOWER48, fitBoundsOptions: { padding: 20 }, maxZoom: 18,
        attributionControl: { compact: false },
        style: {
          version: 8,
          sources: {
            foto: { type: "raster", tiles: [FOTO_TESELAS], tileSize: 256, maxzoom: 16, attribution: FOTO_ATRIBUCION },
          },
          layers: [{ id: "fondo", type: "background", paint: { "background-color": "#0b1f3a" } },
            { id: "foto", type: "raster", source: "foto" }],
        },
      });
      mapa.current = m;
      m.addControl(new gl.NavigationControl({ visualizePitch: false }), "top-left");
      m.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-right");
      m.on("load", () => {
        m.addSource("refinerias", { type: "geojson", data: {
          type: "FeatureCollection",
          features: refinerias.filter((r) => r.lon != null).map((r) => ({
            type: "Feature", properties: { id: r.id, bcd: r.bcd },
            geometry: { type: "Point", coordinates: [r.lon!, r.lat!] } })) } });
        // a escala país se ven como puntos; al acercarse desaparecen para no tapar la foto
        m.addLayer({ id: "refinerias", type: "circle", source: "refinerias", maxzoom: 12, paint: {
          "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "bcd"]], 0, 3, 800, 12],
          "circle-color": "#f0c45c", "circle-stroke-color": "#0b1f3a", "circle-stroke-width": 1.2 } });
        m.on("click", "refinerias", (e) => {
          const id = e.features?.[0]?.properties?.id;
          if (id) alElegir.current(String(id));
        });
        m.on("mouseenter", "refinerias", () => { m.getCanvas().style.cursor = "pointer"; });
        m.on("mouseleave", "refinerias", () => { m.getCanvas().style.cursor = ""; });
        setListo(true);
      });
    })();
    return () => { vivo = false; mapa.current?.remove(); mapa.current = null; };
  }, [refinerias]);

  // vuelo a la refinería elegida
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    if (elegida?.lon != null && elegida.lat != null) {
      m.flyTo({ center: [elegida.lon, elegida.lat], zoom: 15.2, duration: animar ? 3500 : 0, essential: true });
    } else {
      m.fitBounds(LOWER48, { padding: 20, duration: animar ? 2000 : 0 });
    }
  }, [elegida, listo, animar]);

  return (
    <div className="relative h-full w-full">
      <div ref={caja} className="h-full w-full" role="region"
        aria-label={elegida ? `Foto aérea de la refinería ${elegida.empresa} en ${elegida.sitio}, ${elegida.estado}` : "Mapa de las refinerías de EE. UU. sobre foto aérea"} />
      {!listo && <p className="absolute inset-0 grid place-items-center bg-[#0b1f3a] text-sm text-white">Cargando la foto aérea…</p>}
      {elegida && listo && (
        <p className="pointer-events-none absolute left-14 top-3 rounded-md bg-white/90 px-2.5 py-1 text-xs font-semibold text-tinta shadow">
          {elegida.sitio}, {elegida.estado} · {num(elegida.bcd, 0)} b/d
        </p>
      )}
    </div>
  );
}
