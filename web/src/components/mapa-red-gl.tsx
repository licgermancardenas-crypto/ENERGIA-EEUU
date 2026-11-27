"use client";

// Mapa interactivo de la red (página Red): MapLibre GL sobre un mapa base OpenStreetMap
// (OpenFreeMap, sin clave). Zoom hasta nivel de ciudad, nombres de estados y ciudades del
// mapa base, gasoductos con detalle de ~100 m y ficha por operador al pasar el mouse.
import "maplibre-gl/dist/maplibre-gl.css";

import type { ExpressionSpecification, GeoJSONSource, Map as MapaGL, MapLayerMouseEvent, Popup } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { num } from "@/lib/formato";
import type { EstadoGeo, Punto2 } from "@/lib/tipos";

import { AZULES, type Capa, rampa } from "./mapas";

const ESTILO = "https://tiles.openfreemap.org/styles/positron";
const VISTAS = {
  "48 estados": [[-125, 24], [-66.5, 49.5]],
  Alaska: [[-170, 51], [-129, 71.5]],
  Hawái: [[-160.5, 18.8], [-154.6, 22.4]],
  "Costa del Golfo": [[-98, 27.5], [-87.5, 32.5]],
} as const;

type Puntos = { hubs: Punto2[]; gnl: Punto2[]; reserva: Punto2[] };

function coleccion(ps: Punto2[], extra: (p: Punto2) => Record<string, unknown> = () => ({})) {
  return {
    type: "FeatureCollection" as const,
    features: ps.map((p) => ({ type: "Feature" as const, properties: { nombre: p.nombre, ...extra(p) },
      geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] } })),
  };
}

/** Recuadro [oeste, sur, este, norte] de una geometría GeoJSON. */
function recuadro(geom: { coordinates: unknown }): [number, number, number, number] {
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

function ficha(filas: [string, string][], titulo: string): HTMLElement {
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

export function MapaRedGL({ estados, puntos, gasRegion, precioHH, visibles, seleccion, onSeleccion }:
  { estados: EstadoGeo[]; puntos: Puntos; gasRegion: Record<string, number>; precioHH: number | null;
    visibles: Set<Capa>; seleccion: string | null; onSeleccion: (k: string | null) => void }) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const recuadros = useRef(new Map<string, [number, number, number, number]>());
  const [listo, setListo] = useState(false);
  const [operadores, setOperadores] = useState<{ op: string; km: number }[]>([]);
  const [operador, setOperador] = useState("");
  const porClave = useMemo(() => new Map(estados.map((e) => [e.k, e])), [estados]);
  const opRef = useRef("");
  const alSeleccionar = useRef(onSeleccion);
  useEffect(() => { alSeleccionar.current = onSeleccion; }, [onSeleccion]);

  // ---- creación del mapa (una sola vez)
  useEffect(() => {
    let vivo = true;
    let popup: Popup | null = null;
    (async () => {
      const gl = await import("maplibre-gl");
      if (!vivo || !caja.current) return;
      const m = new gl.Map({
        container: caja.current, style: ESTILO, bounds: VISTAS["48 estados"] as never,
        fitBoundsOptions: { padding: 20 }, attributionControl: { compact: true }, maxZoom: 13,
      });
      mapa.current = m;
      m.addControl(new gl.NavigationControl({ visualizePitch: false }), "top-right");
      m.addControl(new gl.FullscreenControl(), "top-right");
      m.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-left");
      popup = new gl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "260px", offset: 8 });

      m.on("load", async () => {
        const [est, reg, red] = await Promise.all(["estados", "regiones", "red_detalle"].map((n) =>
          fetch(`/data/geo/mapa_${n}.geojson`).then((r) => r.json())));
        if (!vivo) return;
        for (const f of est.features) recuadros.current.set(f.properties.estado_key, recuadro(f.geometry));
        const kmOp = new Map<string, number>();
        for (const f of red.features) kmOp.set(f.properties.operador, (kmOp.get(f.properties.operador) ?? 0) + f.properties.km);
        setOperadores([...kmOp].map(([op, km]) => ({ op, km })).sort((a, b) => b.km - a.km));

        // debajo de los nombres del mapa base, así las ciudades quedan legibles
        const antes = m.getStyle().layers.find((l) => l.type === "symbol")?.id;
        const vals = Object.values(gasRegion);
        const colorRegion = ["match", ["get", "region_key"],
          ...Object.entries(gasRegion).flatMap(([k, v]) => [k, rampa(v, Math.min(...vals), Math.max(...vals))]),
          "rgba(0,0,0,0)"] as unknown as ExpressionSpecification;

        m.addSource("regiones", { type: "geojson", data: reg });
        m.addLayer({ id: "regiones", type: "fill", source: "regiones",
          paint: { "fill-color": colorRegion, "fill-opacity": 0.45 } }, antes);
        m.addSource("estados", { type: "geojson", data: est, promoteId: "estado_key" });
        m.addLayer({ id: "estados-relleno", type: "fill", source: "estados", paint: {
          "fill-color": "#1f6fd1",
          "fill-opacity": ["case", ["boolean", ["feature-state", "sel"], false], 0.18,
            ["boolean", ["feature-state", "hover"], false], 0.08, 0] } }, antes);
        m.addLayer({ id: "estados-borde", type: "line", source: "estados", paint: {
          "line-color": ["case", ["boolean", ["feature-state", "sel"], false], "#0b1f3a", "#8a94a3"],
          "line-width": ["case", ["boolean", ["feature-state", "sel"], false], 2.2, 0.8] } }, antes);

        m.addSource("red", { type: "geojson", data: red });
        const ancho = (base: number) => ["interpolate", ["linear"], ["zoom"], 3, base, 7, base * 2.2, 11, base * 4] as unknown as ExpressionSpecification;
        m.addLayer({ id: "red", type: "line", source: "red", layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": ["case", ["==", ["get", "tipo"], "interestatal"], "#3d4a5c", "#8a6d3b"],
            // el zoom tiene que ser la expresión de afuera; el tipo de gasoducto va adentro de cada parada
            "line-width": ["interpolate", ["linear"], ["zoom"],
              ...[3, 7, 11].flatMap((z, i) => [z, ["case", ["==", ["get", "tipo"], "interestatal"],
                [0.9, 2, 3.6][i], [0.55, 1.2, 2.2][i]]])] as unknown as ExpressionSpecification,
            "line-opacity": 0.8 } }, antes);
        m.addLayer({ id: "red-resaltada", type: "line", source: "red", filter: ["==", ["get", "operador"], ""],
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#c4531a", "line-width": ancho(2.2) } }, antes);
        // área invisible más ancha para que pasar el mouse por una línea fina sea fácil
        m.addLayer({ id: "red-toque", type: "line", source: "red", paint: { "line-width": 10, "line-opacity": 0 } });

        m.addSource("reserva", { type: "geojson", data: coleccion(puntos.reserva, (p) => ({ cap: p.capacidad_mmbbl })) });
        m.addLayer({ id: "reserva", type: "circle", source: "reserva", paint: {
          "circle-radius": 6, "circle-color": "#4a5260", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
        const hubs = puntos.hubs.filter((h) => h.nombre !== "Henry Hub");
        m.addSource("hubs", { type: "geojson", data: coleccion(hubs) });
        m.addLayer({ id: "hubs", type: "circle", source: "hubs", paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 3.5, 8, 6], "circle-color": "#164e9c",
          "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
        m.addLayer({ id: "hubs-nombre", type: "symbol", source: "hubs", minzoom: 5.5, layout: {
          "text-field": ["get", "nombre"], "text-font": ["Noto Sans Regular"], "text-size": 11,
          "text-offset": [0, 1.1], "text-anchor": "top" },
          paint: { "text-color": "#164e9c", "text-halo-color": "#fff", "text-halo-width": 1.5 } });
        m.addSource("gnl", { type: "geojson", data: coleccion(puntos.gnl, (p) => ({
          funcion: p.funcion, operador: p.operador, ciudad: p.ciudad, estado: p.estado })) });
        m.addLayer({ id: "gnl", type: "circle", source: "gnl", paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 5, 8, 8], "circle-color": "#1f6fd1",
          "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
        const hh = puntos.hubs.filter((h) => h.nombre === "Henry Hub");
        m.addSource("hh", { type: "geojson", data: coleccion(hh) });
        m.addLayer({ id: "hh", type: "circle", source: "hh", paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 8, 9, 13], "circle-color": "#c4531a",
          "circle-stroke-color": "#fff", "circle-stroke-width": 2.5 } });
        m.addLayer({ id: "hh-nombre", type: "symbol", source: "hh", layout: {
          "text-field": `Henry Hub · US$ ${precioHH != null ? num(precioHH, 2) : "s/d"}`,
          "text-font": ["Noto Sans Bold"], "text-size": 13, "text-offset": [0.9, -0.9], "text-anchor": "bottom-left",
          "text-allow-overlap": true },
          paint: { "text-color": "#1b1f24", "text-halo-color": "#fff", "text-halo-width": 2 } });

        // ---- interacción
        let hover: string | null = null;
        const ponerHover = (k: string | null) => {
          if (hover) m.setFeatureState({ source: "estados", id: hover }, { hover: false });
          hover = k;
          if (k) m.setFeatureState({ source: "estados", id: k }, { hover: true });
        };
        m.on("mousemove", "estados-relleno", (e: MapLayerMouseEvent) => ponerHover(String(e.features?.[0]?.id ?? "")));
        m.on("mouseleave", "estados-relleno", () => ponerHover(null));
        m.on("click", (e) => {
          const enPunto = m.queryRenderedFeatures(e.point, { layers: ["hubs", "gnl", "reserva", "hh"] });
          if (enPunto.length) return;
          const f = m.queryRenderedFeatures(e.point, { layers: ["estados-relleno"] })[0];
          alSeleccionar.current(f ? String(f.id) : null);
        });

        const mostrar = (e: MapLayerMouseEvent, contenido: HTMLElement) => {
          m.getCanvas().style.cursor = "pointer";
          popup!.setLngLat(e.lngLat).setDOMContent(contenido).addTo(m);
        };
        const ocultar = () => { m.getCanvas().style.cursor = ""; popup!.remove(); };
        m.on("mousemove", "red-toque", (e) => {
          const p = e.features?.[0]?.properties;
          if (!p) return;
          m.setFilter("red-resaltada", ["==", ["get", "operador"], p.operador]);
          mostrar(e, ficha([["Tipo", String(p.tipo)], ["Red total del operador", `${num(Number(p.km), 0)} km`],
            ["Conectado al Henry Hub", p.hh === true || p.hh === "true" ? "sí" : "no"]], String(p.operador)));
        });
        m.on("mouseleave", "red-toque", () => {
          m.setFilter("red-resaltada", ["==", ["get", "operador"], opRef.current]);
          ocultar();
        });
        m.on("mousemove", "hubs", (e) => mostrar(e, ficha([], `Hub de gas: ${e.features?.[0]?.properties.nombre}`)));
        m.on("mousemove", "hh", (e) => mostrar(e, ficha([["Precio", precioHH != null ? `US$ ${num(precioHH, 2)} por MMBtu` : "s/d"]],
          "Henry Hub (Erath, Luisiana)")));
        m.on("mousemove", "gnl", (e) => {
          const p = e.features![0].properties;
          mostrar(e, ficha([["Operador", String(p.operador ?? "—")], ["Función", String(p.funcion ?? "—")],
            ["Ubicación", `${p.ciudad ?? ""}, ${p.estado ?? ""}`]], `Terminal de GNL: ${p.nombre}`));
        });
        m.on("mousemove", "reserva", (e) => {
          const p = e.features![0].properties;
          mostrar(e, ficha(p.cap != null ? [["Capacidad", `${num(Number(p.cap), 0)} millones de barriles`]] : [],
            `Reserva estratégica: ${p.nombre}`));
        });
        for (const capa of ["hubs", "hh", "gnl", "reserva"]) m.on("mouseleave", capa, ocultar);
        setListo(true);
      });
    })();
    return () => { vivo = false; popup?.remove(); mapa.current?.remove(); mapa.current = null; };
    // el mapa se crea una vez; las props cambiantes se aplican en los efectos de abajo
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- capas visibles
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    const ver = (ids: string[], on: boolean) => ids.forEach((id) => m.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    ver(["red", "red-resaltada", "red-toque"], visibles.has("Gasoductos"));
    ver(["hubs", "hubs-nombre"], visibles.has("Hubs"));
    ver(["gnl"], visibles.has("Terminales de GNL"));
    ver(["regiones"], visibles.has("Regiones de almacenamiento"));
    ver(["reserva"], visibles.has("Reserva estratégica"));
  }, [visibles, listo]);

  // ---- estado seleccionado: resalta y acerca
  const previo = useRef<string | null>(null);
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo) return;
    if (previo.current) m.setFeatureState({ source: "estados", id: previo.current }, { sel: false });
    previo.current = seleccion;
    if (seleccion) {
      m.setFeatureState({ source: "estados", id: seleccion }, { sel: true });
      const b = recuadros.current.get(seleccion);
      if (b) m.fitBounds(seleccion === "AK" ? (VISTAS.Alaska as never) : b, { padding: 40, maxZoom: 7.5, duration: 900 });
    }
  }, [seleccion, listo]);

  // ---- operador elegido en el buscador
  useEffect(() => {
    opRef.current = operador;
    const m = mapa.current;
    if (!m || !listo) return;
    m.setFilter("red-resaltada", ["==", ["get", "operador"], operador]);
    if (!operador) return;
    const fuente = m.getSource("red") as GeoJSONSource;
    fuente.getData().then((d) => {
      const fs = (d as unknown as { features: { properties: { operador: string }; geometry: { coordinates: unknown } }[] })
        .features.filter((f) => f.properties.operador === operador);
      const b = fs.map((f) => recuadro(f.geometry)).reduce((a, c) =>
        [Math.min(a[0], c[0]), Math.min(a[1], c[1]), Math.max(a[2], c[2]), Math.max(a[3], c[3])]);
      m.fitBounds(b, { padding: 50, maxZoom: 8, duration: 900 });
    });
  }, [operador, listo]);

  const e = seleccion ? porClave.get(seleccion) : undefined;
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-tinta-3">Ir a:</span>
        {Object.entries(VISTAS).map(([nombre, b]) => (
          <button key={nombre} type="button" disabled={!listo}
            onClick={() => { onSeleccion(null); mapa.current?.fitBounds(b as never, { padding: 20, duration: 900 }); }}
            className="rounded-md border border-linea bg-white px-2.5 py-1 text-tinta-2 hover:border-gas hover:text-gas">
            {nombre}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-tinta-2">
          Resaltar operador
          <select value={operador} onChange={(ev) => setOperador(ev.target.value)} disabled={!listo}
            className="max-w-[220px] rounded-md border border-linea bg-white px-2 py-1">
            <option value="">— ninguno —</option>
            {operadores.map((o) => <option key={o.op} value={o.op}>{o.op} ({num(o.km, 0)} km)</option>)}
          </select>
        </label>
      </div>
      <div className="relative">
        <div ref={caja} className="h-[620px] w-full overflow-hidden rounded-lg border border-linea"
          role="region" aria-label="Mapa interactivo de la red de gasoductos de EE. UU." />
        {!listo && <p className="absolute inset-0 grid place-items-center text-sm text-tinta-3">Cargando el mapa…</p>}
        {visibles.has("Regiones de almacenamiento") && listo && (
          <div className="pointer-events-none absolute bottom-8 right-2 rounded bg-white/90 p-2 text-[11px] text-tinta-2 shadow">
            <p className="font-semibold">Gas almacenado en la región (Bcf)</p>
            <div className="mt-1 flex h-2 w-40 overflow-hidden rounded opacity-70">
              {AZULES.map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}
            </div>
            <div className="cifra flex w-40 justify-between">
              <span>{num(Math.min(...Object.values(gasRegion)), 0)}</span><span>{num(Math.max(...Object.values(gasRegion)), 0)}</span>
            </div>
          </div>
        )}
        {e && (
          <p className="pointer-events-none absolute left-2 top-2 rounded bg-white/90 px-2 py-1 text-xs font-semibold text-navy shadow">
            {e.nombre} · {num(e.km, 0)} km de red
          </p>
        )}
      </div>
    </div>
  );
}
