"use client";

// Calefacción con gas de red por condado (página Análisis), con zoom sobre el mapa base.
// Mismos cortes fijos que el mapa estático (0–80 % en 5 clases); sin dato = gris propio.
import "maplibre-gl/dist/maplibre-gl.css";

import type { ExpressionSpecification, Map as MapaGL, Popup } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { num } from "@/lib/formato";
import type { EstadoGeo } from "@/lib/tipos";

import { ESTILO, ficha, recuadro } from "./mapa-red-gl";
import { AZULES } from "./mapas";

const CORTES = [0.16, 0.32, 0.48, 0.64]; // 5 clases iguales entre 0 y 80 %
const SIN_DATO = "#d9d6cf";
const COLOR = ["case", ["==", ["get", "pct"], null], SIN_DATO,
  ["step", ["get", "pct"], AZULES[0], CORTES[0], AZULES[1], CORTES[1], AZULES[2], CORTES[2], AZULES[3],
    CORTES[3], AZULES[4]]] as unknown as ExpressionSpecification;
const LOWER48: [[number, number], [number, number]] = [[-125, 24], [-66.5, 49.5]];

export function MapaCondadosGL({ estados, umbralKm }: { estados: EstadoGeo[]; umbralKm: number }) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const recuadros = useRef(new Map<string, [number, number, number, number]>());
  const [listo, setListo] = useState(false);
  const [estado, setEstado] = useState("");
  const [soloAlerta, setSoloAlerta] = useState(false);
  const [conRed, setConRed] = useState(true);

  useEffect(() => {
    let vivo = true;
    let popup: Popup | null = null;
    (async () => {
      const gl = await import("maplibre-gl");
      if (!vivo || !caja.current) return;
      const m = new gl.Map({ container: caja.current, style: ESTILO, bounds: LOWER48,
        fitBoundsOptions: { padding: 20 }, attributionControl: { compact: true }, maxZoom: 12 });
      mapa.current = m;
      m.addControl(new gl.NavigationControl({ visualizePitch: false }), "top-right");
      m.addControl(new gl.FullscreenControl(), "top-right");
      m.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-left");
      popup = new gl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "280px", offset: 8 });

      m.on("load", async () => {
        const [cond, est, red] = await Promise.all(["condados_detalle", "estados", "red_detalle"].map((n) =>
          fetch(`/data/geo/mapa_${n}.geojson`).then((r) => r.json())));
        if (!vivo) return;
        for (const f of est.features) recuadros.current.set(f.properties.estado_key, recuadro(f.geometry));
        const antes = m.getStyle().layers.find((l) => l.type === "symbol")?.id;

        m.addSource("condados", { type: "geojson", data: cond, promoteId: "k" });
        m.addLayer({ id: "condados", type: "fill", source: "condados", paint: {
          "fill-color": COLOR,
          "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, 0.78] } }, antes);
        m.addLayer({ id: "condados-borde", type: "line", source: "condados", minzoom: 4.5, paint: {
          "line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 4.5, 0.2, 9, 1] } }, antes);
        m.addSource("estados", { type: "geojson", data: est });
        m.addLayer({ id: "estados-borde", type: "line", source: "estados", paint: {
          "line-color": "#0b1f3a", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 9, 1.6] } }, antes);
        m.addSource("red", { type: "geojson", data: red });
        m.addLayer({ id: "red", type: "line", source: "red", paint: {
          "line-color": "#3d4a5c", "line-opacity": 0.55,
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.35, 9, 1.4] } }, antes);
        m.addLayer({ id: "alerta", type: "line", source: "condados", filter: ["==", ["get", "alerta"], true],
          paint: { "line-color": "#a35400", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.6, 9, 3.5] } });

        let hover: string | null = null;
        m.on("mousemove", "condados", (e) => {
          const f = e.features?.[0];
          if (!f) return;
          if (hover) m.setFeatureState({ source: "condados", id: hover }, { hover: false });
          hover = String(f.id);
          m.setFeatureState({ source: "condados", id: hover }, { hover: true });
          const p = f.properties;
          m.getCanvas().style.cursor = "pointer";
          popup!.setLngLat(e.lngLat).setDOMContent(ficha([
            ["Hogares con gas de red", p.pct == null ? "sin dato" : `${num(Number(p.pct) * 100, 1)} % (± ${num(Number(p.moe ?? 0) * 100, 1)})`],
            ["Distancia a un gasoducto", p.km == null ? "—" : `${num(Number(p.km), 1)} km`],
            ...(p.alerta === true || p.alerta === "true"
              ? [["Alerta", `≥ 50 % con gas de red y a más de ${umbralKm} km de la red`] as [string, string]] : []),
          ], `${p.nombre} (${p.estado})`)).addTo(m);
        });
        m.on("mouseleave", "condados", () => {
          if (hover) m.setFeatureState({ source: "condados", id: hover }, { hover: false });
          hover = null;
          m.getCanvas().style.cursor = "";
          popup!.remove();
        });
        setListo(true);
      });
    })();
    return () => { vivo = false; popup?.remove(); mapa.current?.remove(); mapa.current = null; };
  }, [umbralKm]);

  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    m.setFilter("condados", soloAlerta ? ["==", ["get", "alerta"], true] : null);
    m.setLayoutProperty("red", "visibility", conRed ? "visible" : "none");
  }, [soloAlerta, conRed, listo]);

  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    const b = estado === "AK" ? [-170, 51, -129, 71.5] as [number, number, number, number] : recuadros.current.get(estado);
    m.fitBounds(b ?? LOWER48, { padding: 30, duration: 900 });
  }, [estado, listo]);

  const ordenados = [...estados].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-tinta-2">
        <label className="flex items-center gap-2">
          Ir a
          <select value={estado} onChange={(e) => setEstado(e.target.value)} disabled={!listo}
            className="rounded-md border border-linea bg-white px-2 py-1">
            <option value="">48 estados</option>
            {ordenados.map((e) => <option key={e.k} value={e.k}>{e.nombre}</option>)}
          </select>
        </label>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input type="checkbox" checked={soloAlerta} onChange={(e) => setSoloAlerta(e.target.checked)} />
          Solo condados en alerta
        </label>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input type="checkbox" checked={conRed} onChange={(e) => setConRed(e.target.checked)} />
          Mostrar gasoductos
        </label>
      </div>
      <div className="relative">
        <div ref={caja} className="h-[560px] w-full overflow-hidden rounded-lg border border-linea"
          role="region" aria-label="Mapa interactivo de condados por porcentaje de hogares que calefaccionan con gas de red" />
        {!listo && <p className="absolute inset-0 grid place-items-center text-sm text-tinta-3">Cargando el mapa…</p>}
        <div className="pointer-events-none absolute bottom-8 right-2 rounded bg-white/90 p-2 text-[11px] text-tinta-2 shadow">
          <p className="font-semibold">Hogares con gas de red</p>
          <div className="mt-1 flex h-2 w-44 overflow-hidden rounded">
            {AZULES.map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}
          </div>
          <div className="cifra flex w-44 justify-between"><span>0</span><span>16</span><span>32</span><span>48</span><span>64</span><span>80+ %</span></div>
          <p className="mt-1 flex items-center gap-1"><span className="inline-block h-2.5 w-4" style={{ background: SIN_DATO }} /> sin dato</p>
          <p className="flex items-center gap-1"><span className="inline-block h-2.5 w-4 border-2 border-[#a35400]" /> ≥ 50 % y a más de {umbralKm} km</p>
        </div>
      </div>
    </div>
  );
}
