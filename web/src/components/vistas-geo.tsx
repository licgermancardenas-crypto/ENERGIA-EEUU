"use client";

import { useState } from "react";

import { num } from "@/lib/formato";
import type { Geo } from "@/lib/tipos";

import { BarrasH } from "./graficos";
import { MapaCondadosGL } from "./mapa-condados-gl";
import { MapaRedGL } from "./mapa-red-gl";
import { CAPAS, type Capa, MapaEstados, rampa } from "./mapas";
import { Icono, Panel } from "./marco";

const GAS = "#1f6fd1";

// ---------------------------------------------------------------- página Red
export function VistaRed({ geo, gasRegion, precioHH }:
  { geo: Geo; gasRegion: Record<string, number>; precioHH: number | null }) {
  const [visibles, setVisibles] = useState<Set<Capa>>(new Set(CAPAS.filter((c) => c !== "Centrales a gas")));
  const [sel, setSel] = useState<string | null>(null);
  const e = geo.estados.find((x) => x.k === sel);
  const alternar = (c: Capa) => setVisibles((v) => {
    const n = new Set(v); if (n.has(c)) n.delete(c); else n.add(c); return n;
  });
  const sinCentrales = geo.puntos.centrales.length === 0;
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
      <Panel titulo="Red de gasoductos de EE. UU." icono="red" iconoColor={GAS}
        nota="Zoom con la rueda o los botones · clic en un estado para ver sus números · pasá el mouse por un gasoducto para ver su operador">
        <fieldset className="mb-2 flex flex-wrap gap-2">
          <legend className="sr-only">Capas visibles</legend>
          {CAPAS.map((c) => {
            const off = c === "Centrales a gas" && sinCentrales;
            return (
              <label key={c} className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${visibles.has(c) && !off ? "border-gas bg-[#e8f0fb] text-gas" : "border-linea text-tinta-3"} ${off ? "cursor-not-allowed opacity-60" : ""}`}>
                <input type="checkbox" className="sr-only" checked={visibles.has(c)} disabled={off} onChange={() => alternar(c)} />
                {c}{off && " (no disponible)"}
              </label>
            );
          })}
        </fieldset>
        <MapaRedGL estados={geo.estados} puntos={geo.puntos} gasRegion={gasRegion} precioHH={precioHH}
          visibles={visibles} seleccion={sel} onSeleccion={setSel} />
        <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-tinta-2">
          <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-2 border-white bg-[#c4531a] ring-1 ring-[#c4531a]" />Henry Hub</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#164e9c]" />Hub de gas</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full bg-gas" />Terminal de GNL</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full bg-[#4a5260]" />Reserva estratégica</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-1 w-5 bg-[#3d4a5c]" />Gasoducto interestatal</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-[#8a6d3b]" />Gasoducto intraestatal</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-1 w-5 bg-[#c4531a]" />Operador resaltado</li>
        </ul>
      </Panel>
      <div className="grid content-start gap-4">
        <div className="tarjeta p-4">
          <p className="text-[11px] font-semibold tracking-wide text-gas">{e ? e.nombre.toUpperCase() : "TODO EL PAÍS"}</p>
          <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
            {(e
              ? [["Km de red", num(e.km, 0)], ["Densidad", `${num(e.densidad, 1)} km/1.000 km²`],
                ["Operadores", e.operadores == null ? "—" : num(e.operadores, 0)],
                ["Conectado al Henry Hub", e.hh ? "Sí" : "No"],
                ["Hogares con gas de red", e.pct_gas_red == null ? "—" : `${num(e.pct_gas_red * 100, 1)} %`],
                ["Gas en su región", e.region && gasRegion[e.region] != null ? `${num(gasRegion[e.region], 0)} Bcf` : "—"]]
              : [["Km de red", num(geo.validacion.km_red_total, 0)],
                ["Estados con el Henry Hub", `${geo.estados.filter((x) => x.hh).length}`],
                ["Hubs", `${geo.puntos.hubs.length}`], ["Terminales de GNL", `${geo.puntos.gnl.length}`],
                ["Reserva estratégica", `${geo.puntos.reserva.length} sitios`], ["Costa afuera", `${num(geo.validacion.pct_fuera, 1)} %`]]
            ).map(([k, v]) => (
              <div key={k}><dt className="text-xs text-tinta-3">{k}</dt><dd className="cifra text-lg font-semibold">{v}</dd></div>
            ))}
          </dl>
          {e && <button type="button" onClick={() => setSel(null)} className="mt-3 text-xs text-gas underline">Ver todo el país</button>}
        </div>
        <Panel titulo="Estados con más red" nota="km de gasoductos">
          <BarrasH ancho={96} alto={260} items={[...geo.estados].sort((a, b) => b.km - a.km).slice(0, 10)
            .map((x) => ({ nombre: x.nombre, valor: x.km, color: x.k === sel ? "#c4531a" : GAS }))} />
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- página Análisis
export function VistaAnalisis({ geo, umbralKm }: { geo: Geo; umbralKm: number }) {
  const dens = geo.estados.map((e) => e.densidad).filter((v) => v > 0);
  const [dmin, dmax] = [Math.min(...dens), Math.max(...dens)];
  const sinBalance = geo.estados.every((e) => e.balance == null);
  const alerta = Object.entries(geo.condados).filter(([, c]) => c[4] === 1)
    .sort((a, b) => (b[1][3] ?? 0) - (a[1][3] ?? 0));
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel titulo="Densidad de la red" nota="km de gasoducto cada 1.000 km² de superficie" icono="red" iconoColor={GAS}>
          <MapaEstados estados={geo.estados} color={(e) => rampa(e && e.densidad > 0 ? Math.log(e.densidad) : null, Math.log(dmin), Math.log(dmax))}
            titulo={(e, k) => `${e?.nombre ?? k}: ${num(e?.densidad ?? 0, 1)} km/1.000 km²`} />
          <p className="text-xs text-tinta-3">Escala logarítmica: de {num(dmin, 1)} a {num(dmax, 1)} km/1.000 km².</p>
        </Panel>
        <Panel titulo="Alcance del Henry Hub" nota="estados cruzados por los gasoductos conectados al hub (en azul)" icono="llama" iconoColor="#c4531a">
          <MapaEstados estados={geo.estados} hhDestacado color={(e) => (e?.hh ? "#a9c7ee" : "#f1eee7")}
            titulo={(e, k) => `${e?.nombre ?? k}: ${e?.hh ? `${num(e.km_hh, 0)} km de red conectada al Henry Hub` : "sin conexión directa"}`} />
          <p className="text-xs text-tinta-3">{geo.estados.filter((e) => e.hh).length} estados · {geo.henryHub.filter((h) => h.en_capa).length} de {geo.henryHub.length} gasoductos de la lista encontrados en la capa.</p>
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Panel titulo="Calefacción con gas de red por condado" icono="casa" iconoColor={GAS}
          nota={`ACS 2020-2024 (B25040) · borde ámbar: ≥ 50 % de hogares con gas de red y a más de ${umbralKm} km de un gasoducto`}>
          <MapaCondadosGL estados={geo.estados} umbralKm={umbralKm} />
        </Panel>
        <Panel titulo="Condados en alerta" nota={`${alerta.length} condados · ordenados por distancia a la red`} icono="alerta" iconoColor="#a35400">
          <div className="max-h-[420px] overflow-auto">
            <table className="cifra w-full text-left text-sm">
              <thead className="sticky top-0 bg-white text-xs text-tinta-3"><tr><th className="py-1">Condado</th><th className="text-right">Gas de red</th><th className="text-right">Km a la red</th></tr></thead>
              <tbody>
                {alerta.map(([k, c]) => (
                  <tr key={k} className="border-t border-linea/60">
                    <td className="py-1.5">{c[0]}</td>
                    <td className="text-right">{num((c[1] ?? 0) * 100, 1)} % <span className="text-xs text-tinta-3">± {num((c[2] ?? 0) * 100, 1)}</span></td>
                    <td className="text-right">{num(c[3] ?? 0, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel titulo="Balance interestatal de gas" nota="entradas menos salidas por estado (EIA, anual)" icono="flechas-opuestas" iconoColor={GAS}>
          <MapaEstados estados={geo.estados} color={() => "#f1eee7"} titulo={(e, k) => e?.nombre ?? k}
            aviso={sinBalance ? "No disponible: la API de flujos de la EIA no responde (error 504 del lado de la EIA)" : undefined} />
        </Panel>
        <Panel titulo="Hogares con gas de red por estado" nota="ACS 2020-2024 · % de hogares · propano aparte" icono="casa" iconoColor={GAS}>
          <BarrasH ancho={110} alto={360} decimales={1} items={[...geo.estados].filter((e) => e.pct_gas_red != null)
            .sort((a, b) => (b.pct_gas_red ?? 0) - (a.pct_gas_red ?? 0)).slice(0, 15)
            .map((e) => ({ nombre: e.nombre, valor: (e.pct_gas_red ?? 0) * 100, color: GAS }))} />
          <p className="mt-1 flex items-center gap-1.5 text-xs text-tinta-3"><Icono nombre="info" color="#7a8394" tam={14} />Los 15 estados con mayor proporción.</p>
        </Panel>
      </div>
    </>
  );
}
