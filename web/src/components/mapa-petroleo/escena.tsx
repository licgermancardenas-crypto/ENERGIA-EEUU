"use client";

// Mapa de petróleo (/petroleo-red): hermano del mapa de gas, con el mismo mapa base, overlay de
// deck.gl y marcador que late (components/mapa-comun.ts). Naranja = petróleo.
import "maplibre-gl/dist/maplibre-gl.css";

import { TripsLayer } from "@deck.gl/geo-layers";
import { GeoJsonLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl, { type Map as MapaGL } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fechaCorta, num } from "@/lib/formato";
import type { Refineria } from "@/lib/tipos";

import { Conteo } from "../mapa-animado/conteo";
import { crearMapaOscuro, LOWER48, marcadorLatido, type Recuadro } from "../mapa-comun";
import type { ModoMapa } from "../modo-mapa";
import { NOMBRE_PADD, type DatosMapaPetroleo, type SeriesPetroleo } from "./tipos";

const NARANJA: [number, number, number] = [240, 138, 75];
const NARANJA_FUERTE: [number, number, number] = [196, 83, 26];
const PULSO: [number, number, number] = [255, 226, 190];
const RAMPA: [number, number, number][] = [[58, 34, 20], [110, 55, 25], [160, 75, 28], [205, 100, 40], [245, 150, 80]];
const ATAJOS: Record<string, Recuadro> = {
  "48 estados": LOWER48,
  "Costa del Golfo": [[-98, 27.3], [-88, 31.2]],
  Permian: [[-104.9, 30.6], [-100.5, 33.9]],
  Alaska: [[-170, 51], [-129, 71.5]],
};
const CAPAS = ["Oleoductos de crudo", "Pulsos ilustrativos", "Cushing", "Refinerías", "Poliductos",
  "Terminales", "Puertos", "Reserva estratégica", "Producción por estado", "Plays de shale",
  "Plataformas offshore"] as const;
type Capa = (typeof CAPAS)[number];
const POR_DEFECTO: Capa[] = ["Oleoductos de crudo", "Pulsos ilustrativos", "Cushing", "Refinerías"];

type FC = { type: "FeatureCollection"; features: { properties: Record<string, unknown>; geometry: { type: string; coordinates: unknown } }[] };
type Tramo = { path: [number, number][]; operador: string; nombre: string; km: number };
type Pulso = [number, number, number][];

function tramos(fc: FC): Tramo[] {
  const out: Tramo[] = [];
  for (const f of fc.features) {
    const g = f.geometry;
    const ls = (g.type === "LineString" ? [g.coordinates] : g.coordinates) as [number, number][][];
    for (const l of ls) out.push({ path: l, operador: String(f.properties.operador ?? "—"), nombre: String(f.properties.nombre ?? "—"), km: Number(f.properties.km ?? 0) });
  }
  return out;
}
const pts = (fc: FC) => fc.features.map((f) => ({ ...f.properties, xy: f.geometry.coordinates as [number, number] }));

export default function EscenaPetroleo({ datos, modo }: { datos: DatosMapaPetroleo; modo: ModoMapa }) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [listo, setListo] = useState(false);
  const [capas, setCapas] = useState<Set<Capa>>(new Set(POR_DEFECTO));
  const [geo, setGeo] = useState<null | {
    ole: Tramo[]; pol: Tramo[]; pulsos: { max_km: number; trayectos: Pulso[] }; term: ReturnType<typeof pts>;
    puertos: ReturnType<typeof pts>; plays: FC; plat: ReturnType<typeof pts>; estados: FC; refinerias: Refineria[];
    reserva: { nombre: string; lon: number; lat: number; capacidad_mmbbl?: number }[]; series: SeriesPetroleo }>(null);
  const [anio, setAnio] = useState<string>("");
  const [estadoSel, setEstadoSel] = useState<string>("");
  const animar = !modo.movimientoReducido;

  // ---- datos (se bajan acá, no en el HTML)
  useEffect(() => {
    let vivo = true;
    const j = (u: string) => fetch(u).then((r) => r.json());
    Promise.all([j("/data/petroleo/oleoductos.json"), j("/data/petroleo/poliductos.json"), j("/data/petroleo/pulsos.json"),
      j("/data/petroleo/terminales.json"), j("/data/petroleo/puertos.json"), j("/data/petroleo/plays.json"),
      j("/data/petroleo/plataformas.json"), j("/data/geo/mapa_estados.geojson"), j("/data/geo/refinerias.json"),
      j("/data/geo/puntos.json"), j("/data/petroleo/series.json")])
      .then(([ole, pol, pulsos, term, puertos, plays, plat, estados, ref, puntos, series]) => {
        if (!vivo) return;
        setGeo({ ole: tramos(ole), pol: tramos(pol), pulsos, term: pts(term), puertos: pts(puertos), plays,
          plat: pts(plat), estados, refinerias: (ref.refinerias as Refineria[]).filter((r) => r.lon != null),
          reserva: puntos.reserva, series });
        const anios = Object.keys((series as SeriesPetroleo).produccion_padd.R30 ?? {}).sort();
        setAnio(anios.at(-1) ?? "");
      });
    return () => { vivo = false; };
  }, []);

  // ---- mapa base + overlay + Cushing
  useEffect(() => {
    if (!caja.current) return;
    const { mapa: m, overlay: ov } = crearMapaOscuro(maplibregl, caja.current);
    mapa.current = m;
    overlay.current = ov;
    const c = datos.meta.cushing;
    const marcador = marcadorLatido(maplibregl, m, {
      lon: c.lon, lat: c.lat, titulo: "Cushing, Oklahoma", etiqueta: "Cushing, Oklahoma: punto de entrega del WTI",
      lineas: [datos.wti.valor != null ? `WTI US$ ${num(datos.wti.valor, 2)} por barril` : "WTI no disponible",
        datos.wti.fecha ? `al ${fechaCorta(datos.wti.fecha)}` : ""],
    });
    m.on("load", () => setListo(true));
    return () => { marcador.remove(); m.remove(); mapa.current = null; overlay.current = null; };
  }, [datos]);

  // ---- producción por estado del año elegido (dato por ESTADO, no por cuenca)
  const prodAnio = useMemo(() => {
    const out = new Map<string, number>();
    if (!geo) return out;
    for (const [k, s] of Object.entries(geo.series.produccion_estado)) if (s[anio] != null) out.set(k, s[anio]);
    return out;
  }, [geo, anio]);
  const maxProd = Math.max(1, ...prodAnio.values());

  // ---- capas de deck.gl para un instante t
  const construir = useRef<(t: number) => unknown[]>(() => []);
  const construirCapas = (t: number) => {
    if (!geo) return [];
    const on = (c: Capa) => capas.has(c);
    const periodo = geo.pulsos.max_km + 300;
    return [
      new GeoJsonLayer({
        id: "produccion", data: geo.estados as never, visible: on("Producción por estado"), pickable: true,
        filled: true, stroked: true, lineWidthUnits: "pixels", getLineWidth: 0.6, getLineColor: [255, 255, 255, 40],
        getFillColor: (f: { properties: { estado_key: string } }) => {
          const v = prodAnio.get(f.properties.estado_key);
          if (v == null || v <= 0) return [0, 0, 0, 0];
          const i = Math.min(4, Math.floor(Math.sqrt(v / maxProd) * 4.999));
          return [...RAMPA[i], 170];
        },
        updateTriggers: { getFillColor: [anio, maxProd] },
      }),
      new GeoJsonLayer({
        id: "plays", data: geo.plays as never, visible: on("Plays de shale"), pickable: true,
        filled: true, getFillColor: [240, 138, 75, 18], stroked: true, getLineColor: [240, 170, 110, 200],
        lineWidthUnits: "pixels", getLineWidth: 1.2,
      }),
      new PathLayer<Tramo>({
        id: "poliductos", data: geo.pol, visible: on("Poliductos"), pickable: true, getPath: (d) => d.path,
        getColor: [200, 190, 175, 120], widthUnits: "pixels", getWidth: 1, capRounded: true, jointRounded: true,
      }),
      !modo.bajaPotencia && new PathLayer<Tramo>({
        id: "oleoductos-brillo", data: geo.ole, visible: on("Oleoductos de crudo"), getPath: (d) => d.path,
        getColor: [...NARANJA, 30], widthUnits: "pixels", getWidth: 6, capRounded: true, jointRounded: true,
      }),
      new PathLayer<Tramo>({
        id: "oleoductos", data: geo.ole, visible: on("Oleoductos de crudo"), pickable: true, getPath: (d) => d.path,
        getColor: [...NARANJA, 210], widthUnits: "pixels", getWidth: 1.6, capRounded: true, jointRounded: true,
      }),
      animar && new TripsLayer<Pulso>({
        id: "pulsos", data: geo.pulsos.trayectos, visible: on("Pulsos ilustrativos") && on("Oleoductos de crudo"),
        getPath: (d) => d.map((p) => [p[0], p[1]] as [number, number]), getTimestamps: (d) => d.map((p) => p[2]),
        getColor: PULSO, widthUnits: "pixels", getWidth: 3, fadeTrail: true, trailLength: 350,
        currentTime: (t * 650) % periodo, capRounded: true, jointRounded: true,
      }),
      new ScatterplotLayer({
        id: "plataformas", data: geo.plat, visible: on("Plataformas offshore"), pickable: true,
        getPosition: (d: { xy: [number, number] }) => d.xy, radiusUnits: "pixels", getRadius: 2.5,
        getFillColor: (d: { anio_instalacion?: number | null }) => {
          const a = d.anio_instalacion;
          if (a == null) return [150, 150, 150, 200];
          const i = Math.min(4, Math.max(0, Math.floor((a - 1950) / 15)));
          return [...RAMPA[4 - i], 230]; // más viejas, más claras
        },
      }),
      new ScatterplotLayer({
        id: "terminales", data: geo.term, visible: on("Terminales"), pickable: true,
        getPosition: (d: { xy: [number, number] }) => d.xy, radiusUnits: "pixels", getRadius: 2.2,
        getFillColor: [230, 210, 180, 200],
      }),
      new ScatterplotLayer({
        id: "puertos", data: geo.puertos, visible: on("Puertos"), pickable: true,
        getPosition: (d: { xy: [number, number] }) => d.xy, radiusUnits: "pixels",
        getRadius: (d: { toneladas_total?: number }) => 3 + Math.sqrt((d.toneladas_total ?? 0) / 1e6) * 1.6,
        getFillColor: [120, 180, 230, 150], stroked: true, getLineColor: [255, 255, 255, 200], lineWidthUnits: "pixels", getLineWidth: 1,
      }),
      new ScatterplotLayer<{ nombre: string; lon: number; lat: number }>({
        id: "reserva", data: geo.reserva, visible: on("Reserva estratégica"), pickable: true,
        getPosition: (d) => [d.lon, d.lat], radiusUnits: "pixels", getRadius: 7,
        getFillColor: [90, 95, 105], stroked: true, getLineColor: [255, 226, 190], lineWidthUnits: "pixels", getLineWidth: 2,
      }),
      new ScatterplotLayer<Refineria>({
        id: "refinerias", data: geo.refinerias, visible: on("Refinerías"), pickable: true,
        getPosition: (d) => [d.lon!, d.lat!], radiusUnits: "pixels", getRadius: (d) => 2.5 + Math.sqrt(d.bcd) / 70,
        getFillColor: [...NARANJA_FUERTE, 220], stroked: true, getLineColor: [255, 226, 190], lineWidthUnits: "pixels", getLineWidth: 1,
      }),
    ].filter(Boolean);
  };
  useEffect(() => { construir.current = construirCapas; });

  // ---- fichas (solo atributos que trae cada fuente)
  useEffect(() => {
    overlay.current?.setProps({
      getTooltip: ({ object, layer }: { object?: Record<string, unknown>; layer?: { id: string } | null }) => {
        if (!object || !layer) return null;
        const est = { background: "rgba(5,8,15,.92)", color: "#f3e9df", border: "1px solid #f08a4b", borderRadius: "6px", fontSize: "12px", padding: "6px 8px" };
        const o = object as Record<string, unknown> & { properties?: Record<string, unknown> };
        const p = o.properties ?? {};
        const txt = (() => {
          switch (layer.id) {
            case "oleoductos": return `Oleoducto de crudo: ${o.nombre}\nOperador: ${o.operador}\nTramo: ${num(Number(o.km), 0)} km`;
            case "poliductos": return `Poliducto de derivados: ${o.nombre}\nOperador: ${o.operador}\nTramo: ${num(Number(o.km), 0)} km`;
            case "refinerias": return `Refinería: ${o.empresa}\n${o.sitio} (${o.estado})\n${num(Number(o.bcd), 0)} barriles por día (EIA, 2026)`;
            case "terminales": return `Terminal de derivados: ${o.sitio}\n${o.empresa}\n${o.ciudad}, ${o.estado} · PADD ${o.padd}`;
            case "puertos": return `Puerto: ${o.puerto}\nToneladas 2023 (todas las cargas): ${num(Number(o.toneladas_total), 0)}\nImportación: ${num(Number(o.toneladas_importacion), 0)} · Exportación: ${num(Number(o.toneladas_exportacion), 0)}`;
            case "reserva": return `Reserva Estratégica de Petróleo: ${o.nombre}`;
            case "plataformas": return `Plataforma offshore (BOEM) ${o.id}\nInstalada: ${o.anio_instalacion ?? "sin dato"}`;
            case "plays": return `Play: ${p.play}\nCuenca: ${p.cuenca} · ${p.litologia}`;
            case "produccion": {
              const k = String(p.estado_key);
              const v = prodAnio.get(k);
              return `${datos.nombresEstados[k] ?? k}\nProducción de crudo ${anio}: ${v == null ? "sin dato" : `${num(v, 0)} mil b/d`}`;
            }
            default: return null;
          }
        })();
        return txt ? { text: txt, style: est } : null;
      },
      onClick: ({ object, layer }: { object?: { properties?: { estado_key?: string } }; layer?: { id: string } | null }) => {
        if (layer?.id === "produccion" && object?.properties?.estado_key) setEstadoSel(object.properties.estado_key);
      },
    });
  }, [listo, prodAnio, anio, datos]);

  // ---- bucle de animación (sin bucle con movimiento reducido)
  useEffect(() => {
    if (!listo || !geo || !overlay.current) return;
    const ov = overlay.current;
    if (!animar) { ov.setProps({ layers: construir.current(0) as never }); return; }
    let raf = 0;
    const t0 = performance.now();
    const paso = () => { ov.setProps({ layers: construir.current((performance.now() - t0) / 1000) as never }); raf = requestAnimationFrame(paso); };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [listo, geo, animar]);
  useEffect(() => {
    if (!animar && listo && geo) overlay.current?.setProps({ layers: construir.current(0) as never });
  }, [animar, listo, geo, capas, anio, prodAnio]);

  const ir = (b: Recuadro) => mapa.current?.fitBounds(b, { padding: 30, duration: animar ? 2500 : 0 });
  const kmOle = datos.meta.capas.oleoductos?.km_total, kmPol = datos.meta.capas.poliductos?.km_total;
  const anios = geo ? Object.keys(geo.series.produccion_padd.R30 ?? {}).sort() : [];
  const serieGrafico = useMemo(() => {
    if (!geo) return [];
    if (estadoSel) return Object.entries(geo.series.produccion_estado[estadoSel] ?? {}).sort().map(([a, v]) => ({ x: a, v }));
    return geo.series.produccion_nacional_mensual.map(([f, v]) => ({ x: f, v }));
  }, [geo, estadoSel]);
  const comercio = useMemo(() => {
    if (!geo || !anio) return [];
    return ["R10", "R20", "R30", "R40", "R50"].map((k) => ({
      padd: k.replace("R", "").replace("0", ""), nombre: NOMBRE_PADD[k],
      imp: geo.series.comercio_crudo_padd.importaciones[k]?.[anio] ?? null,
      exp: geo.series.comercio_crudo_padd.exportaciones[k]?.[anio] ?? null,
    }));
  }, [geo, anio]);

  return (
    <div className="relative h-full">
      <div className="relative h-full overflow-hidden rounded-xl">
        <div ref={caja} className="h-full w-full" role="region" aria-label="Mapa de la infraestructura de petróleo de EE. UU." />
        {!listo && <p className="absolute inset-0 grid place-items-center bg-[#05080f] text-sm text-[#e9dccf]">Cargando el mapa…</p>}
        <p className="pointer-events-none absolute bottom-9 left-2 z-10 max-w-[280px] rounded bg-[#05080f]/95 px-2 py-1 text-[11px] text-[#e9dccf]">
          Pulsos: animación ilustrativa, no flujo medido (la EIA no publica volúmenes por ducto).
        </p>
      </div>

      <aside className="absolute right-3 top-3 bottom-3 z-10 w-[340px] overflow-y-auto rounded-xl border border-[#5a3a24] bg-[#0b0806]/95 p-4 text-[#f3e9df] shadow-2xl max-lg:static max-lg:mt-3 max-lg:w-full"
        aria-label="Indicadores, capas y fuentes del mapa de petróleo">
        <div className="grid grid-cols-2 gap-2">
          {([["WTI · US$/barril", datos.wti, 2], ["Crudo comercial · mil bbl", datos.crudo, 0],
            ["Refinerías · % de uso", datos.utilizacion, 1], ["Reserva estratégica · mil bbl", datos.spr, 0]] as const).map(([t, k, d]) => (
            <div key={t} className="rounded-lg border border-[#c4531a]/50 p-2">
              <p className="text-[10px] font-semibold tracking-wide text-[#f08a4b]">{t.toUpperCase()}</p>
              <p className="cifra text-xl font-semibold"><Conteo valor={k.valor} decimales={d} animar={animar} /></p>
              <p className="text-[10px] text-[#b9a999]">{k.fecha ? fechaCorta(k.fecha) : "no disponible"}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-[#d8c7b6]">
          Red mapeada: <strong className="cifra">{kmOle != null ? num(kmOle, 0) : "—"}</strong> km de oleoductos de crudo y{" "}
          <strong className="cifra">{kmPol != null ? num(kmPol, 0) : "—"}</strong> km de poliductos (calculado en EPSG:5070 sobre la capa de la EIA).
        </p>

        <fieldset className="mt-3">
          <legend className="text-[11px] font-semibold tracking-wide text-[#b9a999]">CAPAS</legend>
          <div className="mt-1.5 grid grid-cols-2 gap-1.5">
            {CAPAS.map((c) => (
              <label key={c} className={`flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 text-[11px] ${capas.has(c) ? "border-[#f08a4b] bg-[#3a1e0f]" : "border-[#4a3426] text-[#b9a999]"}`}>
                <input type="checkbox" className="accent-[#f08a4b]" checked={capas.has(c)}
                  onChange={() => setCapas((s) => { const n = new Set(s); if (n.has(c)) n.delete(c); else n.add(c); return n; })} />
                {c}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
          {Object.entries(ATAJOS).map(([k, b]) => (
            <button key={k} type="button" onClick={() => ir(b)} className="rounded-md border border-[#4a3426] px-2 py-1 hover:border-[#f08a4b]">{k}</button>
          ))}
        </div>

        <section className="mt-4 text-xs">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold tracking-wide text-[#f08a4b]">PRODUCCIÓN DE CRUDO</p>
            <label className="flex items-center gap-1 text-[#b9a999]">Año
              <select value={anio} onChange={(e) => setAnio(e.target.value)} className="rounded border border-[#4a3426] bg-[#0b0806] px-1 py-0.5">
                {anios.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
          </div>
          <p className="mt-1 text-[11px] text-[#b9a999]">
            {estadoSel ? `${datos.nombresEstados[estadoSel] ?? estadoSel}: promedio anual, mil b/d` : "EE. UU.: mensual, mil b/d"}
            {estadoSel && <button type="button" onClick={() => setEstadoSel("")} className="ml-2 underline">ver EE. UU.</button>}
          </p>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={serieGrafico} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#2a1d15" vertical={false} />
                <XAxis dataKey="x" tick={{ fontSize: 9, fill: "#b9a999" }} tickLine={false} axisLine={false} minTickGap={30} />
                <YAxis tick={{ fontSize: 9, fill: "#b9a999" }} tickLine={false} axisLine={false} width={42} tickFormatter={(v: number) => num(v, 0)} />
                <Tooltip formatter={(v) => `${num(Number(v), 0)} mil b/d`} contentStyle={{ background: "#0b0806", border: "1px solid #f08a4b", fontSize: 11 }} />
                <Line dataKey="v" stroke="#f08a4b" strokeWidth={1.8} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-[11px] text-[#b9a999]">
            La capa «Producción por estado» pinta cada estado con su producción del año (EIA, por estado: la EIA no publica
            una serie histórica comparable por cuenca). Los contornos de «Plays de shale» son solo referencia geográfica.
            Golfo offshore federal {anio}: {geo?.series.offshore_golfo[anio] != null ? `${num(geo.series.offshore_golfo[anio], 0)} mil b/d` : "sin dato"}.
          </p>
        </section>

        <section className="mt-4 text-xs">
          <p className="text-[11px] font-semibold tracking-wide text-[#f08a4b]">COMERCIO DE CRUDO POR PADD · {anio}</p>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comercio} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#2a1d15" vertical={false} />
                <XAxis dataKey="padd" tick={{ fontSize: 10, fill: "#b9a999" }} tickLine={false} axisLine={false} tickFormatter={(v: string) => `PADD ${v}`} />
                <YAxis tick={{ fontSize: 9, fill: "#b9a999" }} tickLine={false} axisLine={false} width={42} tickFormatter={(v: number) => num(v, 0)} />
                <Tooltip formatter={(v) => (v == null ? "no disponible" : `${num(Number(v), 0)} mil b/d`)} labelFormatter={(l) => NOMBRE_PADD[`R${l}0`] ?? l}
                  contentStyle={{ background: "#0b0806", border: "1px solid #f08a4b", fontSize: 11 }} />
                <Bar dataKey="imp" name="Importaciones" fill="#7fb4e6" isAnimationActive={false} />
                <Bar dataKey="exp" name="Exportaciones" fill="#f08a4b" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-[#b9a999]">Celeste: importaciones · naranja: exportaciones (mil b/d, promedio anual). Por PADD: la API no publica comercio por puerto.</p>
        </section>

        <details className="mt-4 rounded-lg border border-[#4a3426] p-2 text-[11px] text-[#d8c7b6]">
          <summary className="cursor-pointer font-semibold text-[#f08a4b]">Fuentes y límites</summary>
          <p className="mt-1">Descarga: {fechaCorta(datos.meta.fecha_descarga)}. Script: scripts/preparar_mapa_petroleo.py.</p>
          <ul className="mt-1 space-y-1">
            {Object.entries(datos.meta.capas).filter(([k]) => k !== "series" && k !== "cushing").map(([k, c]) => (
              <li key={k}><strong>{k}</strong>: {c.origen} · {c.licencia}{c.vintage ? ` · dato: ${c.vintage}` : " · vintage no informado"}{c.elementos != null ? ` · ${num(c.elementos, 0)} elementos` : ""}{c.nota ? ` · ${c.nota}` : ""}</li>
            ))}
            <li><strong>Cushing</strong>: {datos.meta.cushing.fuente}. El punto es el centro de la ciudad; los parques de tanques están en las afueras.</li>
            <li><strong>Refinerías y reserva</strong>: EIA (capa 2024, capacidad al 1/1/2026) y DOE vía EIA.</li>
            <li><strong>Series</strong>: API v2 de la EIA: petroleum/crd/crpdn (producción por estado, PADD y Golfo offshore, área R3FM), petroleum/move/imp y petroleum/move/exp (comercio de crudo por PADD).</li>
          </ul>
          <p className="mt-2 font-semibold">No disponible</p>
          <ul className="list-disc pl-4">{datos.meta.no_disponibles.map((n) => <li key={n.capa}>{n.capa}: {n.motivo}.</li>)}</ul>
        </details>
      </aside>
    </div>
  );
}
