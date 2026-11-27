"use client";

import { geoAlbersUsa, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { useEffect, useMemo, useState } from "react";

import { num } from "@/lib/formato";
import type { CondadosGeo, EstadoGeo, Punto2 } from "@/lib/tipos";

// ---------------------------------------------------------------- geometría compartida
type Feature = { type: "Feature"; properties: Record<string, unknown>; geometry: GeoPermissibleObjects };
type Coleccion = { type: "FeatureCollection"; features: Feature[] };

const cache = new Map<string, Promise<Coleccion>>();
function cargar(nombre: string): Promise<Coleccion> {
  if (!cache.has(nombre)) {
    cache.set(nombre, fetch(`/data/geo/mapa_${nombre}.geojson`).then((r) => r.json()));
  }
  return cache.get(nombre)!;
}

function useCapas(nombres: string[]) {
  const [capas, setCapas] = useState<Record<string, Coleccion>>({});
  const clave = nombres.join(",");
  useEffect(() => {
    let vivo = true;
    Promise.all(clave.split(",").map((n) => cargar(n).then((c) => [n, c] as const)))
      .then((pares) => vivo && setCapas(Object.fromEntries(pares)));
    return () => { vivo = false; };
  }, [clave]);
  return capas;
}

const W = 960, H = 560;
function useProyeccion(estados?: Coleccion) {
  return useMemo(() => {
    const p = geoAlbersUsa();
    if (estados) p.fitExtent([[8, 8], [W - 8, H - 8]], estados as unknown as GeoPermissibleObjects);
    return { proy: p, path: geoPath(p) };
  }, [estados]);
}

export const AZULES = ["#dce8f8", "#a9c7ee", "#6fa0e0", "#3478d2", "#164e9c"];
export function rampa(v: number | null, min: number, max: number): string {
  if (v == null || !Number.isFinite(v)) return "#f1eee7";
  const i = max === min ? 2 : Math.min(4, Math.floor(((v - min) / (max - min)) * 4.999));
  return AZULES[i];
}

function Cargando() {
  return <p className="grid h-full min-h-48 place-items-center text-sm text-tinta-3">Cargando el mapa…</p>;
}

function Leyenda({ titulo, min, max, fmt }: { titulo: string; min: number; max: number; fmt: (v: number) => string }) {
  return (
    <div className="text-[11px] text-tinta-2">
      <p className="font-semibold">{titulo}</p>
      <div className="mt-1 flex h-2 w-40 overflow-hidden rounded">
        {AZULES.map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}
      </div>
      <div className="flex w-40 justify-between"><span>{fmt(min)}</span><span>{fmt(max)}</span></div>
    </div>
  );
}

// ---------------------------------------------------------------- mapa de la red
export const CAPAS = ["Gasoductos", "Hubs", "Terminales de GNL", "Centrales a gas",
  "Regiones de almacenamiento", "Reserva estratégica"] as const;
export type Capa = (typeof CAPAS)[number];

// ---------------------------------------------------------------- mapas por estado (análisis)
export function MapaEstados({ estados, color, titulo, hhDestacado = false, aviso }:
  { estados: EstadoGeo[]; color: (e: EstadoGeo | undefined) => string;
    titulo: (e: EstadoGeo | undefined, k: string) => string; hhDestacado?: boolean; aviso?: string }) {
  const capas = useCapas(hhDestacado ? ["estados", "red"] : ["estados"]);
  const { path } = useProyeccion(capas.estados);
  const porClave = useMemo(() => new Map(estados.map((e) => [e.k, e])), [estados]);
  if (!capas.estados || (hhDestacado && !capas.red)) return <Cargando />;
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Mapa de EE. UU. por estado">
        {capas.estados.features.map((f) => {
          const k = String(f.properties.estado_key);
          return <path key={k} d={path(f.geometry) ?? ""} fill={color(porClave.get(k))} stroke="#fff"
            strokeWidth={0.8}><title>{titulo(porClave.get(k), k)}</title></path>;
        })}
        {hhDestacado && capas.red?.features.map((f, i) => (
          <path key={i} d={path(f.geometry) ?? ""} fill="none" pointerEvents="none"
            stroke={f.properties.hh ? "#164e9c" : "#b9b3a8"} strokeOpacity={f.properties.hh ? 0.9 : 0.35}
            strokeWidth={f.properties.tipo === "interestatal" ? 1 : 0.5} />
        ))}
      </svg>
      {aviso && (
        <p className="absolute inset-0 grid place-items-center text-center text-sm font-semibold text-tinta-2">
          <span className="rounded bg-white/85 px-3 py-2">{aviso}</span>
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- calefacción por condado
export function MapaCondados({ condados, umbralKm }: { condados: CondadosGeo; umbralKm: number }) {
  const capas = useCapas(["estados", "condados", "red"]);
  const { path } = useProyeccion(capas.estados);
  if (!capas.condados || !capas.red || !capas.estados) return <Cargando />;
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img"
        aria-label="Mapa de condados por porcentaje de hogares que calefaccionan con gas de red">
        {capas.condados.features.map((f) => {
          const k = String(f.properties.condado_key);
          const c = condados[k];
          return <path key={k} d={path(f.geometry) ?? ""} fill={rampa(c?.[1] ?? null, 0, 0.8)}
            stroke="#fff" strokeWidth={0.15}>
            <title>{c ? `${c[0]}: ${num((c[1] ?? 0) * 100, 1)} % con gas de red (± ${num((c[2] ?? 0) * 100, 1)}) · ${num(c[3] ?? 0, 1)} km a la red` : k}</title>
          </path>;
        })}
        {capas.red.features.map((f, i) => (
          <path key={i} d={path(f.geometry) ?? ""} fill="none" stroke="#5b6770" strokeOpacity={0.35}
            strokeWidth={0.4} pointerEvents="none" />
        ))}
        {capas.condados.features.filter((f) => condados[String(f.properties.condado_key)]?.[4] === 1)
          .map((f) => (
            <path key={`a${f.properties.condado_key}`} d={path(f.geometry) ?? ""} fill="none"
              stroke="#a35400" strokeWidth={1.6} pointerEvents="none" />
          ))}
      </svg>
      <div className="absolute bottom-2 right-2 rounded bg-white/85 p-2">
        <Leyenda titulo="Hogares con gas de red" min={0} max={0.8} fmt={(v) => `${Math.round(v * 100)} %`} />
        <p className="mt-1 flex items-center gap-1 text-[11px] text-tinta-2">
          <span className="inline-block h-2.5 w-4 border-2 border-[#a35400]" /> ≥ 50 % y a más de {umbralKm} km de la red
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- mini mapa (portada)
export function MiniRed({ hh }: { hh: Punto2 | undefined }) {
  const capas = useCapas(["estados", "red"]);
  const { proy, path } = useProyeccion(capas.estados);
  if (!capas.estados || !capas.red) return <div className="h-full min-h-40" />;
  const xy = hh ? proy([hh.lon, hh.lat]) : null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" aria-hidden>
      {capas.estados.features.map((f, i) => (
        <path key={i} d={path(f.geometry) ?? ""} fill="#0b1f3a" fillOpacity={0.35} stroke="#23446f" strokeWidth={0.8} />
      ))}
      {capas.red.features.map((f, i) => (
        <path key={`r${i}`} d={path(f.geometry) ?? ""} fill="none" stroke="#5fb3e6" strokeOpacity={0.7} strokeWidth={0.7} />
      ))}
      {xy && <circle cx={xy[0]} cy={xy[1]} r={9} fill="#c4531a" stroke="#fff" strokeWidth={2} />}
    </svg>
  );
}
