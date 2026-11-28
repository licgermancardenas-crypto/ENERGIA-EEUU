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
  "Foto: USGS The National Map, ortoimágenes USDA NAIP (dominio público) · Límites: U.S. Census · " +
  "Nombres: OpenFreeMap, © colaboradores de OpenStreetMap · Ubicación y capacidad: EIA";
// nombres de estados y ciudades (vector tiles de OpenStreetMap, sin clave; mismo servicio que la página Red)
const NOMBRES_URL = "https://tiles.openfreemap.org/backup_planet";
const GLIFOS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
const TEXTO = ["coalesce", ["get", "name_en"], ["get", "name"]];
type Recuadro = [[number, number], [number, number]];
const LOWER48: [[number, number], [number, number]] = [[-125, 24], [-66.5, 49.5]];

/** Recuadro [[oeste, sur], [este, norte]] de una geometría GeoJSON. */
function recuadro(coords: unknown): Recuadro {
  const b: Recuadro = [[180, 90], [-180, -90]];
  const ir = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === "number") {
      const [x, y] = c as number[];
      b[0][0] = Math.min(b[0][0], x); b[0][1] = Math.min(b[0][1], y);
      b[1][0] = Math.max(b[1][0], x); b[1][1] = Math.max(b[1][1], y);
    } else if (Array.isArray(c)) c.forEach(ir);
  };
  ir(coords);
  return b;
}

export function FotoAerea({ refinerias, elegida, onElegir, animar, estado }:
  { refinerias: Refineria[]; elegida: Refineria | null; onElegir: (id: string) => void; animar: boolean;
    /** estado elegido (clave de 2 letras): resalta su límite y encuadra la cámara */
    estado: string }) {
  const recuadros = useRef(new Map<string, Recuadro>());
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
          glyphs: GLIFOS,
          sources: {
            foto: { type: "raster", tiles: [FOTO_TESELAS], tileSize: 256, maxzoom: 16, attribution: FOTO_ATRIBUCION },
            nombres: { type: "vector", url: NOMBRES_URL },
          },
          layers: [{ id: "fondo", type: "background", paint: { "background-color": "#0b1f3a" } },
            { id: "foto", type: "raster", source: "foto" }],
        },
      });
      mapa.current = m;
      m.addControl(new gl.NavigationControl({ visualizePitch: false }), "top-left");
      m.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-right");
      m.on("load", async () => {
        // límites de los estados (Census) y estado elegido resaltado
        const est = await fetch("/data/geo/mapa_estados.geojson").then((r) => r.json());
        if (!vivo) return;
        for (const f of est.features) recuadros.current.set(f.properties.estado_key, recuadro(f.geometry.coordinates));
        m.addSource("estados", { type: "geojson", data: est });
        m.addLayer({ id: "estado-elegido", type: "fill", source: "estados", filter: ["==", ["get", "estado_key"], ""],
          paint: { "fill-color": "#5fb3e6", "fill-opacity": 0.12 } });
        m.addLayer({ id: "limites", type: "line", source: "estados", paint: {
          "line-color": "#ffffff", "line-opacity": 0.85,
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.8, 8, 2] } });
        m.addLayer({ id: "limite-elegido", type: "line", source: "estados", filter: ["==", ["get", "estado_key"], ""],
          paint: { "line-color": "#f0c45c", "line-width": 3 } });
        // nombres de estados y ciudades: blancos con borde oscuro para leerse sobre la foto
        const etiqueta = (id: string, filtro: unknown[], minzoom: number, tam: unknown, fuente = "Noto Sans Regular") =>
          m.addLayer({ id, type: "symbol", source: "nombres", "source-layer": "place", minzoom,
            filter: filtro as never,
            layout: { "text-field": TEXTO as never, "text-font": [fuente], "text-size": tam as never,
              "text-max-width": 8 },
            paint: { "text-color": "#ffffff", "text-halo-color": "rgba(11,31,58,0.9)", "text-halo-width": 1.6 } });
        etiqueta("nombre-estado", ["==", ["get", "class"], "state"], 3.5,
          ["interpolate", ["linear"], ["zoom"], 3.5, 11, 7, 15], "Noto Sans Bold");
        etiqueta("nombre-ciudad", ["==", ["get", "class"], "city"], 4,
          ["interpolate", ["linear"], ["zoom"], 4, 10, 10, 15]);
        etiqueta("nombre-pueblo", ["==", ["get", "class"], "town"], 7.5, 12);
        etiqueta("nombre-barrio", ["in", ["get", "class"], ["literal", ["village", "suburb"]]], 11, 11);
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

  // estado elegido: resalta su límite
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    m.setFilter("estado-elegido", ["==", ["get", "estado_key"], estado]);
    m.setFilter("limite-elegido", ["==", ["get", "estado_key"], estado]);
  }, [estado, listo]);

  // cámara: la refinería elegida; si no, el estado; si no, el país
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    const dur = animar ? 3000 : 0;
    if (elegida?.lon != null && elegida.lat != null) {
      m.flyTo({ center: [elegida.lon, elegida.lat], zoom: 15.2, duration: dur, essential: true });
    } else if (estado && recuadros.current.has(estado)) {
      const b = estado === "AK" ? ([[-170, 51], [-129, 71.5]] as Recuadro) : recuadros.current.get(estado)!;
      m.fitBounds(b, { padding: 40, duration: dur });
    } else {
      m.fitBounds(LOWER48, { padding: 20, duration: dur });
    }
  }, [elegida, estado, listo, animar]);

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
