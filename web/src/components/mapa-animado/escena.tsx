"use client";

// Escena del mapa animado: MapLibre (mapa base oscuro de OpenFreeMap) + deck.gl por overlay.
// Este módulo solo se carga en el navegador (import dinámico desde ./index.tsx).
import "maplibre-gl/dist/maplibre-gl.css";

import { TripsLayer } from "@deck.gl/geo-layers";
import { GeoJsonLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl, { type Map as MapaGL } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { fechaCorta, num } from "@/lib/formato";
import type { Flujos, Refineria, Refinerias } from "@/lib/tipos";

import type { Modo } from "./index";
import { Conteo } from "./conteo";
import { GUION } from "./guion";
import { NOMBRE_REGION, type DatosMapa } from "./tipos";

const ESTILO_OSCURO = "https://tiles.openfreemap.org/styles/dark";
// 40 m por Bcf: la región más llena queda en ~50 km, por debajo de los arcos de flujo
const ALTURA_POR_BCF = 40;
const ENCIMA = { depthCompare: "always" } as never; // arcos y pulsos siempre visibles sobre el 3D
const LOWER48: [[number, number], [number, number]] = [[-125, 24], [-66.5, 49.5]];
const VUELOS = {
  "Vista nacional": { bounds: LOWER48 },
  "Henry Hub": { center: [-92.06, 29.9] as [number, number], zoom: 5.4, pitch: 40, bearing: -12 },
  Alaska: { bounds: [[-170, 51], [-129, 71.5]] as [[number, number], [number, number]] },
  Hawái: { bounds: [[-160.5, 18.8], [-154.6, 22.4]] as [[number, number], [number, number]] },
};
const CAPAS = ["Gasoductos", "Pulsos", "Flujos entre estados", "Almacenamiento", "Hubs", "GNL", "Refinerías"] as const;
type Capa = (typeof CAPAS)[number];

// Paleta sobre fondo oscuro: azul = gas; naranja solo para el Henry Hub (marcador HTML).
const AZUL_RED: [number, number, number] = [70, 150, 235];
const AZUL_PULSO: [number, number, number] = [225, 243, 255];
const RAMPA_ALM: [number, number, number][] = [[26, 58, 110], [33, 86, 160], [44, 116, 205], [77, 150, 230], [130, 190, 245]];

type Tramo = { path: [number, number][]; inter: boolean; operador: string };
type Pulso = [number, number, number][];
type Arco = { path: [number, number, number][]; tiempos: number[]; mmcf: number; o: string; d: string };
type FC = { type: "FeatureCollection"; features: { properties: Record<string, unknown>; geometry: { type: string; coordinates: unknown } }[] };

function tramos(red: FC): Tramo[] {
  const out: Tramo[] = [];
  for (const f of red.features) {
    const g = f.geometry;
    const lineas = (g.type === "LineString" ? [g.coordinates] : g.coordinates) as [number, number][][];
    for (const l of lineas) {
      out.push({ path: l, inter: f.properties.tipo === "interestatal", operador: String(f.properties.operador) });
    }
  }
  return out;
}

/** Arco 3D entre dos puntos: altura proporcional a la distancia, tiempos 0..1 más un desfase. */
function arco(a: [number, number], b: [number, number], desfase: number): { path: [number, number, number][]; tiempos: number[] } {
  const km = Math.hypot((b[0] - a[0]) * 85, (b[1] - a[1]) * 111);
  const h = km * 1000 * 0.3;
  const path: [number, number, number][] = [];
  const tiempos: number[] = [];
  for (let i = 0; i <= 32; i++) {
    const s = i / 32;
    path.push([a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s, Math.sin(Math.PI * s) * h]);
    tiempos.push(s + desfase);
  }
  return { path, tiempos };
}

function colorAlm(v: number, min: number, max: number): [number, number, number, number] {
  const i = max === min ? 2 : Math.min(4, Math.floor(((v - min) / (max - min)) * 4.999));
  return [...RAMPA_ALM[i], 255];
}

function balanceTexto(v: number | null) {
  if (v == null) return "no disponible";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v) / 1000, 1)} Bcf`;
}

export default function Escena({ datos, modo }: { datos: DatosMapa; modo: Modo }) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [listo, setListo] = useState(false);
  const [geo, setGeo] = useState<{ red: Tramo[]; regiones: FC; estados: FC; pulsos: { max_km: number; trayectos: Pulso[] }; flujos: Flujos; refinerias: Refinerias } | null>(null);
  const [capas, setCapas] = useState<Set<Capa>>(new Set(modo.grabacion ? ["Gasoductos", "Pulsos"] : CAPAS.filter((c) => c !== "Flujos entre estados")));
  const [tresD, setTresD] = useState(false);
  const [pitch, setPitch] = useState(0);
  const [anio, setAnio] = useState<number | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [titulo, setTitulo] = useState(false);
  const animar = !modo.movimientoReducido;

  // ---- datos (la geometría se baja acá, no en el HTML)
  useEffect(() => {
    let vivo = true;
    Promise.all(["mapa_red_detalle.geojson", "mapa_regiones.geojson", "mapa_estados.geojson", "pulsos.json", "flujos.json", "refinerias.json"]
      .map((n) => fetch(`/data/geo/${n}`).then((r) => r.json())))
      .then(([red, regiones, estados, pulsos, flujos, refinerias]) => {
        if (!vivo) return;
        setGeo({ red: tramos(red), regiones, estados, pulsos, flujos, refinerias });
        setAnio((flujos as Flujos).anios.at(-1) ?? null);
      });
    return () => { vivo = false; };
  }, []);

  // ---- mapa base + overlay de deck.gl
  useEffect(() => {
    if (!caja.current) return;
    const m = new maplibregl.Map({
      container: caja.current, style: ESTILO_OSCURO, bounds: LOWER48, fitBoundsOptions: { padding: 30 },
      maxPitch: 70, attributionControl: { compact: false }, maxZoom: 11,
    });
    mapa.current = m;
    if (!modo.grabacion) {
      m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
      m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    }
    const ov = new MapboxOverlay({ interleaved: false, layers: [] });
    overlay.current = ov;
    m.addControl(ov);
    m.on("pitch", () => setPitch(Math.round(m.getPitch())));
    // el estilo oscuro pide un ícono ("circle-11") que no trae su sprite: se reemplaza por uno vacío
    m.on("styleimagemissing", (e) => {
      if (!m.hasImage(e.id)) m.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) });
    });

    // Henry Hub: marcador HTML con anillo que late (CSS; se apaga con movimiento reducido)
    const hh = datos.hubs.find((h) => h.nombre === "Henry Hub");
    let marcador: maplibregl.Marker | null = null;
    if (hh) {
      const el = document.createElement("div");
      el.className = "hh-marcador";
      el.setAttribute("role", "img");
      el.setAttribute("aria-label", "Henry Hub, Erath, Luisiana");
      const anillo = document.createElement("span");
      anillo.className = "hh-anillo";
      const punto = document.createElement("span");
      punto.className = "hh-punto";
      const nota = document.createElement("span");
      nota.className = "hh-nota";
      const t1 = document.createElement("strong");
      t1.textContent = "Henry Hub";
      const t2 = document.createElement("span");
      t2.textContent = datos.precioHH != null ? `US$ ${num(datos.precioHH, 2)} por MMBtu` : "precio no disponible";
      const t3 = document.createElement("small");
      t3.textContent = datos.fechaHH ? `al ${fechaCorta(datos.fechaHH)}` : "";
      nota.append(t1, t2, t3);
      el.append(anillo, punto, nota);
      marcador = new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([hh.lon, hh.lat]).addTo(m);
    }
    m.on("load", () => setListo(true));
    return () => { marcador?.remove(); m.remove(); mapa.current = null; overlay.current = null; };
  }, [datos, modo.grabacion]);

  // ---- vuelo de entrada: del país al Golfo y el Henry Hub
  useEffect(() => {
    const m = mapa.current;
    if (!m || !listo || !geo || modo.grabacion || !animar) return;
    const t = setTimeout(() => m.flyTo({ ...VUELOS["Henry Hub"], zoom: 5.2, pitch: 35, duration: 5000, essential: false }), 1500);
    return () => clearTimeout(t);
  }, [listo, geo, modo.grabacion, animar]);

  // ---- flujos del año elegido (los N pares más grandes: evita la maraña de arcos)
  const centro = useMemo(() => new Map(datos.estados.map((e) => [e.k, e.centro])), [datos.estados]);
  const arcos = useMemo<{ lista: Arco[]; max: number }>(() => {
    if (!geo || anio == null) return { lista: [], max: 0 };
    const pares = geo.flujos.pares.filter((p) => p[2] === anio).sort((a, b) => b[3] - a[3])
      .slice(0, modo.bajaPotencia ? 40 : 80);
    const lista: Arco[] = [];
    pares.forEach(([o, d, , mmcf], i) => {
      const a = centro.get(o), b = centro.get(d);
      if (!a || !b) return;
      lista.push({ ...arco(a, b, (i * 0.37) % 1), mmcf, o, d });
    });
    return { lista, max: pares[0]?.[3] ?? 0 };
  }, [geo, anio, centro, modo.bajaPotencia]);

  const valores = Object.values(datos.gasRegion);
  const [aMin, aMax] = [Math.min(...valores), Math.max(...valores)];

  // ---- capas de deck.gl para un instante t (segundos)
  const construir = useRef<(t: number) => unknown[]>(() => []);
  const construirCapas = (t: number) => {
    if (!geo) return [];
    const on = (c: Capa) => capas.has(c);
    const periodo = geo.pulsos.max_km + 400;
    const vel = 750; // km "de animación" por segundo: ilustrativo, no es velocidad del gas
    const ondas = modo.bajaPotencia ? [0] : [0, 0.5];
    return [
      new GeoJsonLayer({
        id: "almacenamiento", data: geo.regiones as never, visible: on("Almacenamiento"),
        filled: true, stroked: false, extruded: tresD, pickable: false, opacity: tresD ? 0.42 : 0.13,
        getFillColor: (f: { properties: { region_key: string } }) => {
          const v = datos.gasRegion[f.properties.region_key];
          return v == null ? [0, 0, 0, 0] : colorAlm(v, aMin, aMax);
        },
        getElevation: (f: { properties: { region_key: string } }) => (datos.gasRegion[f.properties.region_key] ?? 0) * ALTURA_POR_BCF,
        material: { ambient: 0.6, diffuse: 0.5, shininess: 20 },
        transitions: { getElevation: animar ? 1200 : 0 },
        updateTriggers: { getElevation: tresD },
      }),
      new GeoJsonLayer({
        id: "estados", data: geo.estados as never, pickable: true, filled: true, stroked: true,
        getFillColor: (f: { properties: { estado_key: string } }) => (f.properties.estado_key === sel ? [95, 179, 230, 60] : [0, 0, 0, 0]),
        getLineColor: (f: { properties: { estado_key: string } }) => (f.properties.estado_key === sel ? [235, 245, 255, 230] : [140, 165, 200, 70]),
        lineWidthUnits: "pixels",
        getLineWidth: (f: { properties: { estado_key: string } }) => (f.properties.estado_key === sel ? 2 : 0.6),
        updateTriggers: { getFillColor: sel, getLineColor: sel, getLineWidth: sel },
      }),
      !modo.bajaPotencia && new PathLayer<Tramo>({
        id: "red-brillo", data: geo.red.filter((r) => r.inter), visible: on("Gasoductos"),
        getPath: (d) => d.path, getColor: [...AZUL_RED, 18], widthUnits: "pixels", getWidth: 5,
        capRounded: true, jointRounded: true,
      }),
      new PathLayer<Tramo>({
        id: "red", data: geo.red, visible: on("Gasoductos"), pickable: true,
        getPath: (d) => d.path, getColor: (d) => (d.inter ? [...AZUL_RED, 150] : [...AZUL_RED, 80]),
        widthUnits: "pixels", getWidth: (d) => (d.inter ? 1.4 : 0.7), capRounded: true, jointRounded: true,
      }),
      ...(animar ? ondas : []).map((o) => new TripsLayer<Pulso>({
        id: `pulsos-${o}`, data: geo.pulsos.trayectos, visible: on("Pulsos"),
        getPath: (d) => d.map((p) => [p[0], p[1]] as [number, number]),
        getTimestamps: (d) => d.map((p) => p[2]),
        getColor: AZUL_PULSO, widthUnits: "pixels", getWidth: 3, parameters: ENCIMA, capRounded: true, jointRounded: true,
        fadeTrail: true, trailLength: 380, currentTime: (t * vel + o * periodo) % periodo,
      })),
      new PathLayer<Arco>({
        id: "arcos-base", data: arcos.lista, visible: on("Flujos entre estados"),
        getPath: (d) => d.path, getColor: [170, 205, 245, 70], widthUnits: "pixels", parameters: ENCIMA,
        getWidth: (d) => 0.6 + 7 * (d.mmcf / (arcos.max || 1)), pickable: true,
      }),
      animar && new TripsLayer<Arco>({
        id: "arcos-cometa", data: arcos.lista, visible: on("Flujos entre estados"),
        getPath: (d) => d.path, getTimestamps: (d) => d.tiempos, getColor: [210, 235, 255], parameters: ENCIMA,
        widthUnits: "pixels", getWidth: (d) => 1 + 13 * (d.mmcf / (arcos.max || 1)),
        fadeTrail: true, trailLength: 0.35, currentTime: (t * 0.45) % 2, capRounded: true,
      }),
      new ScatterplotLayer({
        id: "hubs", data: datos.hubs.filter((h) => h.nombre !== "Henry Hub"), visible: on("Hubs"), pickable: true,
        getPosition: (d: { lon: number; lat: number }) => [d.lon, d.lat], radiusUnits: "pixels", getRadius: 3.5,
        getFillColor: [150, 195, 245, 230], stroked: true, getLineColor: [5, 8, 15], lineWidthUnits: "pixels", getLineWidth: 1,
      }),
      new ScatterplotLayer<Refineria>({
        id: "refinerias", data: geo.refinerias.refinerias.filter((r) => r.lon != null), visible: on("Refinerías"),
        pickable: true, getPosition: (d) => [d.lon!, d.lat!], radiusUnits: "pixels",
        getRadius: (d) => 2.5 + Math.sqrt(d.bcd) / 70, getFillColor: [240, 196, 92, 215],
        stroked: true, getLineColor: [5, 8, 15], lineWidthUnits: "pixels", getLineWidth: 1,
      }),
      new ScatterplotLayer({
        id: "gnl", data: datos.gnl, visible: on("GNL"), pickable: true,
        getPosition: (d: { lon: number; lat: number }) => [d.lon, d.lat], radiusUnits: "pixels", getRadius: 6,
        getFillColor: [40, 130, 230], stroked: true, getLineColor: [235, 245, 255], lineWidthUnits: "pixels", getLineWidth: 1.5,
      }),
    ].filter(Boolean);
  };
  // el bucle de animación lee siempre la última versión (capas, año, selección, 3D)
  useEffect(() => { construir.current = construirCapas; });

  // ---- tooltips y clic
  useEffect(() => {
    overlay.current?.setProps({
      getTooltip: ({ object, layer }: { object?: Record<string, unknown>; layer?: { id: string } | null }) => {
        if (!object || !layer) return null;
        const estilo = { background: "rgba(5,8,15,.92)", color: "#e8eef7", border: "1px solid #5fb3e6", borderRadius: "6px", fontSize: "12px", padding: "6px 8px" };
        if (layer.id === "red") {
          const o = object as unknown as Tramo;
          return { text: `${o.operador}\nGasoducto ${o.inter ? "interestatal" : "intraestatal"}`, style: estilo };
        }
        if (layer.id === "hubs") return { text: `Hub de gas: ${object.nombre}`, style: estilo };
        if (layer.id === "refinerias") {
          const r = object as unknown as Refineria;
          return { text: `Refinería: ${r.empresa}\n${r.sitio} (${r.estado})\n${num(r.bcd, 0)} barriles por día de destilación de crudo`, style: estilo };
        }
        if (layer.id === "gnl") return { text: `Terminal de GNL: ${object.nombre}\n${object.operador ?? ""} · ${object.funcion ?? ""}\n${object.ciudad ?? ""}, ${object.estado ?? ""}`, style: estilo };
        if (layer.id === "arcos-base") {
          const a = object as unknown as Arco;
          const n = (k: string) => datos.estados.find((e) => e.k === k)?.nombre ?? k;
          return { text: `${n(a.o)} → ${n(a.d)}\n${num(a.mmcf / 1000, 1)} Bcf entregados en ${anio}`, style: estilo };
        }
        if (layer.id === "estados") {
          const k = String((object.properties as Record<string, unknown>).estado_key);
          const e = datos.estados.find((x) => x.k === k);
          const r = e?.region ? datos.gasRegion[e.region] : undefined;
          return { text: `${e?.nombre ?? k}\n${num(e?.km ?? 0, 0)} km de gasoductos${r != null ? `\nRegión ${NOMBRE_REGION[e!.region!]}: ${num(r, 0)} Bcf almacenados` : ""}`, style: estilo };
        }
        return null;
      },
      onClick: ({ object, layer }: { object?: { properties?: { estado_key?: string } }; layer?: { id: string } | null }) => {
        if (layer?.id === "estados" && object?.properties?.estado_key) setSel(object.properties.estado_key);
      },
    });
  }, [datos, anio, listo]);

  // ---- bucle de animación (sin bucle con movimiento reducido: se dibuja una vez)
  useEffect(() => {
    if (!listo || !geo) return;
    const ov = overlay.current;
    if (!ov) return;
    if (!animar) { ov.setProps({ layers: construir.current(0) as never }); return; }
    let raf = 0;
    const t0 = performance.now();
    const paso = () => {
      ov.setProps({ layers: construir.current((performance.now() - t0) / 1000) as never });
      raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [listo, geo, animar]);
  // con movimiento reducido, redibuja cuando cambian los controles
  useEffect(() => {
    if (!animar && listo && geo) overlay.current?.setProps({ layers: construir.current(0) as never });
  }, [animar, listo, geo, capas, tresD, sel, arcos]);

  // ---- 3D: inclina y levanta el almacenamiento
  const alternar3D = (v: boolean) => {
    setTresD(v);
    if (v) setCapas((c) => new Set([...c, "Almacenamiento"]));
    mapa.current?.easeTo({ pitch: v ? 50 : 0, bearing: v ? -15 : 0, duration: animar ? 1200 : 0 });
  };
  const volar = (k: keyof typeof VUELOS) => {
    const m = mapa.current;
    if (!m) return;
    const v = VUELOS[k];
    if ("bounds" in v) {
      m.fitBounds(v.bounds, { padding: 30, pitch: tresD ? 50 : 0, bearing: tresD ? -15 : 0, duration: animar ? 2500 : 0 });
    }
    else m.flyTo({ ...v, duration: animar ? 3000 : 0 });
  };

  // ---- modo grabación: recorrido automático (guion en docs/guion-video.md)
  useEffect(() => {
    const m = mapa.current;
    if (!modo.grabacion || !listo || !geo || !m) return;
    // el guion está pensado para ~1100 px de ancho: en 4:5 o 1:1 se aleja lo necesario
    const dz = Math.log2(Math.max(320, m.getContainer().clientWidth) / 1100);
    const timers = GUION.map((p) => setTimeout(() => {
      if (p.camara) {
        if ("bounds" in p.camara) m.fitBounds(p.camara.bounds, { padding: 40, pitch: p.camara.pitch ?? 0, bearing: p.camara.bearing ?? 0, duration: p.duracion });
        else m.flyTo({ ...p.camara, zoom: p.camara.zoom + dz, duration: p.duracion, essential: true });
      }
      if (p.capas) setCapas(new Set(p.capas as Capa[]));
      if (p.tresD != null) setTresD(p.tresD);
      if (p.titulo) setTitulo(true);
    }, p.t * 1000));
    return () => timers.forEach(clearTimeout);
  }, [modo.grabacion, listo, geo]);

  // ---- detalle del estado elegido
  const det = useMemo(() => {
    if (!sel || !geo || anio == null) return null;
    const e = datos.estados.find((x) => x.k === sel);
    const f = geo.flujos.estados.find((x) => x[0] === sel && x[1] === anio);
    const sale = geo.flujos.pares.filter((p) => p[0] === sel && p[2] === anio).sort((a, b) => b[3] - a[3]).slice(0, 3);
    const entra = geo.flujos.pares.filter((p) => p[1] === sel && p[2] === anio).sort((a, b) => b[3] - a[3]).slice(0, 3);
    const ref = geo.refinerias.estados[sel] ?? null;
    const mayores = geo.refinerias.refinerias.filter((r) => r.estado === sel).sort((a, b) => b.bcd - a.bcd).slice(0, 3);
    return { e, recibe: f?.[2] ?? null, entrega: f?.[3] ?? null, neto: f?.[4] ?? null, sale, entra, ref, mayores };
  }, [sel, geo, anio, datos.estados]);
  const nombre = (k: string) => datos.estados.find((e) => e.k === k)?.nombre ?? k;

  const marco = modo.formato === "4x5" ? "aspect-[4/5] h-full max-h-screen" : modo.formato === "1x1" ? "aspect-square h-full max-h-screen" : "h-full w-full";
  return (
    <div className={modo.grabacion ? "fixed inset-0 z-50 grid place-items-center bg-black" : "relative h-full"}>
      <div className={`relative overflow-hidden ${modo.grabacion ? marco : "h-full"}`}>
        <div ref={caja} className="h-full w-full" role="region"
          aria-label="Mapa animado de la red de gasoductos de EE. UU. con el Henry Hub" />
        {!listo && <p className="absolute inset-0 grid place-items-center bg-[#05080f] text-sm text-[#c9d4e5]">Cargando el mapa…</p>}

        {/* aviso visible: la animación no es un dato */}
        <p className="pointer-events-none absolute bottom-9 left-2 z-10 max-w-[260px] rounded bg-[#05080f]/95 px-2 py-1 text-[11px] text-[#c9d4e5]">
          Pulsos: animación ilustrativa, no representa volúmenes. Los arcos sí usan volúmenes reales de la EIA.
        </p>

        {modo.grabacion && (
          <div className={`pointer-events-none absolute inset-x-0 top-0 z-10 p-5 transition-opacity duration-1000 ${titulo ? "opacity-0" : "opacity-100"}`}>
            <p className="text-[11px] font-semibold tracking-wide text-[#5fb3e6]">PULSO ENERGÉTICO DE EE. UU.</p>
            <p className="text-xl font-semibold text-white">La red de gas natural desde el Henry Hub</p>
          </div>
        )}
        {modo.grabacion && (
          <div className={`pointer-events-none absolute inset-0 z-20 grid place-items-center bg-[#05080f]/92 p-8 text-center transition-opacity duration-1000 ${titulo ? "opacity-100" : "opacity-0"}`}>
            <div>
              <p className="text-xs font-semibold tracking-wide text-[#5fb3e6]">PULSO ENERGÉTICO DE EE. UU.</p>
              <p className="mt-2 text-3xl font-semibold text-white">{num(datos.kmRed, 0)} km de gasoductos<br />y un precio de referencia</p>
              <p className="mt-3 text-sm text-[#c9d4e5]">Henry Hub: {datos.precioHH != null ? `US$ ${num(datos.precioHH, 2)} por MMBtu` : "no disponible"}{datos.fechaHH ? ` al ${fechaCorta(datos.fechaHH)}` : ""}</p>
              <p className="mt-6 text-[11px] text-[#9db7dd]">Fuente: EIA (API v2 y capas GIS vía HIFLD) · U.S. Census · Mapa base: OpenFreeMap, OpenMapTiles, OpenStreetMap<br />Pulsos ilustrativos; flujos interestatales reales de la EIA · Autor: Germán Cárdenas</p>
            </div>
          </div>
        )}
      </div>

      {!modo.grabacion && (
        <aside className="absolute right-3 top-3 bottom-3 z-10 w-[330px] overflow-y-auto rounded-xl border border-[#23446f] bg-[#05080f]/95 p-4 text-[#e8eef7] shadow-2xl backdrop-blur max-lg:static max-lg:mt-3 max-lg:w-full max-lg:bg-[#0b1f3a]"
          aria-label="Controles y detalle del mapa">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-[#c4531a]/60 p-2.5">
              <p className="text-[10px] font-semibold tracking-wide text-[#f08a4b]">HENRY HUB</p>
              <p className="cifra text-2xl font-semibold"><Conteo valor={datos.precioHH} decimales={2} animar={animar} prefijo="US$ " /></p>
              <p className="text-[10px] text-[#9db7dd]">por MMBtu{datos.fechaHH ? ` · ${fechaCorta(datos.fechaHH)}` : ""}</p>
            </div>
            <div className="rounded-lg border border-[#5fb3e6]/60 p-2.5">
              <p className="text-[10px] font-semibold tracking-wide text-[#5fb3e6]">GAS ALMACENADO</p>
              <p className="cifra text-2xl font-semibold"><Conteo valor={datos.gasTotal} decimales={0} animar={animar} /></p>
              <p className="text-[10px] text-[#9db7dd]">Bcf · Lower 48{datos.fechaGas ? ` · ${fechaCorta(datos.fechaGas)}` : ""}</p>
            </div>
          </div>

          <fieldset className="mt-4">
            <legend className="text-[11px] font-semibold tracking-wide text-[#9db7dd]">CAPAS</legend>
            <div className="mt-1.5 grid grid-cols-2 gap-1.5">
              {CAPAS.map((c) => (
                <label key={c} className={`flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 text-xs ${capas.has(c) ? "border-[#5fb3e6] bg-[#16335c]" : "border-[#23446f] text-[#9db7dd]"}`}>
                  <input type="checkbox" className="accent-[#5fb3e6]" checked={capas.has(c)}
                    onChange={() => setCapas((s) => { const n = new Set(s); if (n.has(c)) n.delete(c); else n.add(c); return n; })} />
                  {c}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-3 grid gap-2 text-xs">
            <label className="flex items-center justify-between gap-2">
              Año de los flujos
              <select value={anio ?? ""} onChange={(e) => setAnio(Number(e.target.value))} disabled={!geo}
                className="rounded-md border border-[#23446f] bg-[#0b1f3a] px-2 py-1">
                {geo?.flujos.anios.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
            <label className="flex items-center justify-between gap-2">
              <span>Inclinación <span className="cifra text-[#9db7dd]">{pitch}°</span></span>
              <input type="range" min={0} max={65} value={pitch} aria-label="Inclinación del mapa en grados"
                onChange={(e) => mapa.current?.setPitch(Number(e.target.value))} className="w-36 accent-[#5fb3e6]" />
            </label>
            <label className="flex cursor-pointer items-center gap-2">
              <input type="checkbox" className="accent-[#5fb3e6]" checked={tresD} onChange={(e) => alternar3D(e.target.checked)} />
              Almacenamiento en 3D (altura = Bcf de la región)
            </label>
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(VUELOS) as (keyof typeof VUELOS)[]).map((k) => (
                <button key={k} type="button" onClick={() => volar(k)}
                  className="rounded-md border border-[#23446f] px-2 py-1 hover:border-[#5fb3e6] hover:text-white">
                  {k === "Vista nacional" ? k : `Volar a ${k}`}
                </button>
              ))}
            </div>
          </div>

          <section className="mt-4 rounded-lg border border-[#23446f] p-3 text-xs" aria-live="polite">
            {det?.e ? (
              <>
                <div className="flex items-start justify-between">
                  <p className="text-sm font-semibold">{det.e.nombre}</p>
                  <button type="button" onClick={() => setSel(null)} className="text-[#9db7dd] underline">cerrar</button>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-2">
                  <div><dt className="text-[#9db7dd]">Gasoductos</dt><dd className="cifra font-semibold">{num(det.e.km, 0)} km</dd></div>
                  <div><dt className="text-[#9db7dd]">Operadores</dt><dd className="cifra font-semibold">{det.e.operadores ?? "—"}</dd></div>
                  <div><dt className="text-[#9db7dd]">Recibe ({anio})</dt><dd className="cifra font-semibold">{det.recibe == null ? "no disponible" : `${num(det.recibe / 1000, 1)} Bcf`}</dd></div>
                  <div><dt className="text-[#9db7dd]">Entrega ({anio})</dt><dd className="cifra font-semibold">{det.entrega == null ? "no disponible" : `${num(det.entrega / 1000, 1)} Bcf`}</dd></div>
                  <div className="col-span-2"><dt className="text-[#9db7dd]">Balance neto</dt>
                    <dd className="cifra font-semibold">{balanceTexto(det.neto)}{det.neto != null && (det.neto > 0 ? " · importador neto" : det.neto < 0 ? " · exportador neto" : "")}</dd></div>
                </dl>
                {det.sale.length > 0 && <p className="mt-2 text-[#c9d4e5]">Entrega sobre todo a: {det.sale.map((p) => `${nombre(p[1])} (${num(p[3] / 1000, 0)} Bcf)`).join(", ")}</p>}
                {det.entra.length > 0 && <p className="mt-1 text-[#c9d4e5]">Recibe sobre todo de: {det.entra.map((p) => `${nombre(p[0])} (${num(p[3] / 1000, 0)} Bcf)`).join(", ")}</p>}
                <p className="mt-2 border-t border-[#23446f] pt-2 text-[#f0c45c]">
                  {det.ref
                    ? `Refinerías (${geo?.refinerias.anio}): ${det.ref.n} · ${num(det.ref.bcd, 0)} barriles por día de capacidad`
                    : "Sin refinerías de crudo"}
                </p>
                {det.mayores.length > 0 && <p className="mt-1 text-[#c9d4e5]">Mayores: {det.mayores.map((r) => `${r.empresa.split(" ").slice(0, 2).join(" ")}, ${r.sitio} (${num(r.bcd / 1000, 0)} mil b/d)`).join(" · ")}</p>}
              </>
            ) : <p className="text-[#9db7dd]">Hacé clic en un estado para ver sus gasoductos y su balance de flujos.</p>}
          </section>

          <section className="mt-4 text-xs">
            <p className="text-[11px] font-semibold tracking-wide text-[#f08a4b]">CONEXIONES DEL HENRY HUB</p>
            <ul className="mt-1.5 grid gap-1">
              {datos.henryHub.map((h) => (
                <li key={h.gasoducto} className="flex justify-between gap-2 border-b border-[#23446f]/60 pb-1">
                  <span>{h.gasoducto}</span>
                  <span className="cifra text-[#9db7dd]">{h.en_capa ? `${num(h.km, 0)} km · ${h.estados_n} est.` : "no está en la capa"}</span>
                </li>
              ))}
            </ul>
            <p className="mt-1.5 text-[10px] text-[#9db7dd]">Esquema ilustrativo: según la fuente, el hub tiene entre 8 y 13 conexiones. Lista usada: {datos.fuentes.conexiones_henry_hub}.</p>
          </section>

          <section className="mt-4 text-[11px] text-[#c9d4e5]">
            <p className="font-semibold text-[#9db7dd]">REFERENCIAS</p>
            <p className="mt-1 flex items-center gap-2"><span className="inline-block h-0.5 w-6 bg-[#4696eb]" /> Gasoducto (más grueso: interestatal)</p>
            <p className="flex items-center gap-2"><span className="inline-block h-1 w-6 rounded bg-gradient-to-r from-transparent to-[#96d7ff]" /> Pulso ilustrativo desde el Henry Hub</p>
            <p className="flex items-center gap-2"><span className="inline-block h-1.5 w-6 bg-[#d2ebff]" /> Flujo entre estados: el más grueso = {arcos.max ? `${num(arcos.max / 1000, 0)} Bcf en ${anio}` : "—"}</p>
            <p className="flex items-center gap-2"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#f0c45c]" /> Refinería (tamaño = capacidad de destilación)</p>
            <p className="mt-1">Almacenamiento por región: {num(aMin, 0)} a {num(aMax, 0)} Bcf</p>
            <div className="mt-1 flex h-2 w-40 overflow-hidden rounded">{RAMPA_ALM.map((c) => <span key={c.join()} className="flex-1" style={{ background: `rgb(${c.join(",")})` }} />)}</div>
          </section>
        </aside>
      )}
    </div>
  );
}
