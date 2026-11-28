"use client";

// Mapa del lienzo de la historia: MapLibre sobre el mapa oscuro (sin deck.gl). Se carga con
// import dinámico cuando la sección está cerca; cada etapa cambia el encuadre (≤ 1,5 s) y las capas.
import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapaGL } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { EtapaHistoria } from "@/lib/historia";

import { FLAGS } from "@/lib/flags";

import { aplicarTonoHorario, ESTILO_OSCURO, LOWER48 } from "../mapa-estilos";

const CAPAS = ["plataformas", "oleoductos", "refinerias", "puertos"] as const;

export function MapaHistoria({ etapa, animar }: { etapa: EtapaHistoria; animar: boolean }) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const [listo, setListo] = useState(false);
  const animarRef = useRef(animar);
  useEffect(() => { animarRef.current = animar; }, [animar]);

  useEffect(() => {
    let vivo = true;
    (async () => {
      const gl = await import("maplibre-gl");
      if (!vivo || !caja.current) return;
      const m = new gl.Map({ container: caja.current, style: ESTILO_OSCURO, bounds: LOWER48, interactive: false,
        attributionControl: { compact: true }, fadeDuration: 0 });
      mapa.current = m;
      m.on("styleimagemissing", (e) => { if (!m.hasImage(e.id)) m.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
      m.on("load", async () => {
        if (FLAGS.diaNoche) aplicarTonoHorario(m, animarRef.current);
        const j = (u: string) => fetch(u).then((r) => r.json());
        const [plat, ole, ref, pue] = await Promise.all([j("/data/petroleo/plataformas.json"), j("/data/petroleo/oleoductos.json"),
          j("/data/geo/refinerias.json"), j("/data/petroleo/puertos.json")]);
        if (!vivo) return;
        m.addSource("plataformas", { type: "geojson", data: plat });
        m.addLayer({ id: "plataformas", type: "circle", source: "plataformas", layout: { visibility: "none" },
          paint: { "circle-radius": 2, "circle-color": "#f5a26b", "circle-opacity": 0.85 } });
        m.addSource("oleoductos", { type: "geojson", data: ole });
        m.addLayer({ id: "oleoductos", type: "line", source: "oleoductos", layout: { visibility: "none", "line-cap": "round" },
          paint: { "line-color": "#f08a4b", "line-width": 1.6, "line-opacity": 0.9 } });
        // pulsos ILUSTRATIVOS: trazo discontinuo que avanza (no es caudal medido)
        m.addLayer({ id: "oleoductos-pulso", type: "line", source: "oleoductos", layout: { visibility: "none" },
          paint: { "line-color": "#ffe2be", "line-width": 2.4, "line-dasharray": [0, 4, 3] } });
        m.addSource("refinerias", { type: "geojson", data: {
          type: "FeatureCollection",
          features: ref.refinerias.filter((r: { lon: number | null }) => r.lon != null).map((r: { lon: number; lat: number; bcd: number }) => ({
            type: "Feature", properties: { bcd: r.bcd }, geometry: { type: "Point", coordinates: [r.lon, r.lat] } })) } });
        m.addLayer({ id: "refinerias", type: "circle", source: "refinerias", layout: { visibility: "none" },
          paint: { "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "bcd"]], 0, 2, 800, 11],
            "circle-color": "#c4531a", "circle-stroke-color": "#ffe2be", "circle-stroke-width": 1 } });
        m.addSource("puertos", { type: "geojson", data: pue });
        m.addLayer({ id: "puertos", type: "circle", source: "puertos", layout: { visibility: "none" },
          paint: { "circle-radius": ["interpolate", ["linear"], ["sqrt", ["coalesce", ["get", "toneladas_total"], 0]], 0, 2, 16000, 14],
            "circle-color": "#7fb4e6", "circle-opacity": 0.75, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1 } });
        setListo(true);
      });
    })();
    return () => { vivo = false; mapa.current?.remove(); mapa.current = null; };
  }, []);

  // encuadre y capas de la etapa
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    for (const c of CAPAS) {
      const on = etapa.mapa.capas.includes(c) ? "visible" : "none";
      m.setLayoutProperty(c, "visibility", on);
      if (c === "oleoductos") m.setLayoutProperty("oleoductos-pulso", "visibility", animar ? on : "none");
    }
    m.fitBounds(etapa.mapa.recuadro, { padding: 12, duration: animar ? 1400 : 0 });
  }, [etapa, listo, animar]);

  // avance de los pulsos ilustrativos (se detiene con movimiento reducido)
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo || !animar || !etapa.mapa.capas.includes("oleoductos")) return;
    const pasos = [[0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0], [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5]];
    let i = 0;
    const t = setInterval(() => { m.setPaintProperty("oleoductos-pulso", "line-dasharray", pasos[i]); i = (i + 1) % pasos.length; }, 80);
    return () => clearInterval(t);
  }, [etapa, listo, animar]);

  return (
    <div className="relative h-full w-full">
      <div ref={caja} className="h-full w-full" role="img" aria-label={`Mapa: ${etapa.titulo}`} />
      {etapa.mapa.capas.includes("oleoductos") && (
        <p className="pointer-events-none absolute left-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-[9px] text-[#ffe2be]">
          Pulsos ilustrativos, no flujo medido
        </p>
      )}
      {etapa.mapa.capas.includes("puertos") && (
        <p className="pointer-events-none absolute left-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-[9px] text-[#cfe3f5]">
          Puertos: toneladas de todas las cargas (USACE 2023)
        </p>
      )}
    </div>
  );
}
