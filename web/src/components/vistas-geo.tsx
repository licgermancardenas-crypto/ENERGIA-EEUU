"use client";

import { num } from "@/lib/formato";
import type { Geo } from "@/lib/tipos";

import { BarrasH } from "./graficos";
import { MapaCondadosGL } from "./mapa-condados-gl";
import { MapaEstados, rampa } from "./mapas";
import { Icono, Panel } from "./marco";

const GAS = "#1f6fd1";

// ---------------------------------------------------------------- página Análisis
// Balance neto: ocre = exportador neto, azul = importador neto (escala raíz cuadrada).
const DIVERGENTE: [string, string][] = [["#8a6500", "gran exportador"], ["#d9bf6e", "exportador"],
  ["#f1eee7", "cerca de cero"], ["#a9c7ee", "importador"], ["#164e9c", "gran importador"]];
function divergente(v: number | null, max: number): string {
  if (v == null) return "#e4e0d8";
  const s = Math.sign(v) * Math.sqrt(Math.abs(v) / max);
  return DIVERGENTE[s < -0.55 ? 0 : s < -0.15 ? 1 : s <= 0.15 ? 2 : s <= 0.55 ? 3 : 4][0];
}

export function VistaAnalisis({ geo, umbralKm }: { geo: Geo; umbralKm: number }) {
  const dens = geo.estados.map((e) => e.densidad).filter((v) => v > 0);
  const [dmin, dmax] = [Math.min(...dens), Math.max(...dens)];
  const sinBalance = geo.estados.every((e) => e.balance == null);
  const maxBalance = Math.max(1, ...geo.estados.map((e) => Math.abs(e.balance ?? 0)));
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
          <MapaEstados estados={geo.estados} color={(e) => divergente(e?.balance ?? null, maxBalance)}
            titulo={(e, k) => `${e?.nombre ?? k}: ${e?.balance == null ? "sin dato" : `${e.balance > 0 ? "+" : ""}${num(e.balance / 1000, 1)} Bcf en ${e.anio_balance}`}`}
            aviso={sinBalance ? "No disponible: la EIA no publicó flujos interestatales" : undefined} />
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tinta-2">
            {DIVERGENTE.map(([c, t]) => (
              <li key={t} className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: c }} />{t}</li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-tinta-3">Recibe menos entrega, en Bcf. El mapa animado muestra de dónde viene y a dónde va.</p>
        </Panel>
        <Panel titulo="Hogares con gas de red por estado" nota="ACS 2020-2024 · % de hogares · propano aparte" icono="casa" iconoColor={GAS}>
          <BarrasH ancho={110} alto={360} decimales={1} items={[...geo.estados].filter((e) => e.pct_gas_red != null)
            .sort((a, b) => (b.pct_gas_red ?? 0) - (a.pct_gas_red ?? 0)).slice(0, 15)
            .map((e) => ({ nombre: e.nombre, valor: (e.pct_gas_red ?? 0) * 100, color: GAS }))} />
          <p className="mt-1 flex items-center gap-1.5 text-xs text-tinta-3"><Icono nombre="info" color="#7a8394" tam={14} />Los 15 estados con mayor proporción.</p>
        </Panel>
      </div>
      <RefinacionPorEstado geo={geo} />
    </>
  );
}

// ---------------------------------------------------------------- refinación por estado
const OCRE = "#a87d00";
const OCRES = ["#f3ead2", "#e3cf94", "#cfae55", "#a87d00", "#6e5200"];

function RefinacionPorEstado({ geo }: { geo: Geo }) {
  const { estados: tot, anio } = geo.refinerias;
  const caps = Object.values(tot).map((e) => e.bcd).filter((v) => v > 0);
  const max = Math.max(1, ...caps);
  // escala raíz cuadrada: Texas concentra un tercio del país y aplastaría al resto
  const color = (v: number | undefined) => {
    if (!v) return "#f1eee7";
    return OCRES[Math.min(4, Math.floor(Math.sqrt(v / max) * 4.999))];
  };
  const ranking = Object.entries(tot).sort((a, b) => b[1].bcd - a[1].bcd).slice(0, 12);
  const nombre = (k: string) => geo.estados.find((e) => e.k === k)?.nombre ?? k;
  const total = Object.values(tot).reduce((s, e) => s + e.bcd, 0);
  const nTotal = Object.values(tot).reduce((s, e) => s + e.n, 0);
  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <Panel titulo="Capacidad de refinación por estado" icono="fabrica" iconoColor={OCRE}
        nota={`Destilación de crudo operable al 1/1/${anio ?? "—"} · barriles por día calendario · EIA`}>
        <MapaEstados estados={geo.estados} color={(e) => color(e ? tot[e.k]?.bcd : undefined)}
          titulo={(e, k) => {
            const t = tot[k];
            return t ? `${e?.nombre ?? k}: ${t.n} refinerías · ${num(t.bcd, 0)} b/d` : `${e?.nombre ?? k}: sin refinerías de crudo`;
          }} />
        <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tinta-2">
          <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm bg-[#f1eee7] ring-1 ring-linea" />sin refinerías</li>
          {OCRES.map((c, i) => (
            <li key={c} className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: c }} />
              {i === 0 ? "menos" : i === 4 ? "más capacidad" : ""}</li>
          ))}
        </ul>
        <p className="mt-1 text-xs text-tinta-3">{nTotal} refinerías operables y {num(total / 1e6, 1)} millones de barriles por día en el país. Escala de raíz cuadrada.</p>
      </Panel>
      <Panel titulo="Estados con más capacidad" nota="miles de barriles por día" icono="fabrica" iconoColor={OCRE}>
        <BarrasH ancho={100} alto={360} items={ranking.map(([k, t]) => ({ nombre: `${nombre(k)} (${t.n})`, valor: t.bcd / 1000, color: OCRE }))} />
        <p className="mt-1 text-xs text-tinta-3">Entre paréntesis, la cantidad de refinerías. El mapa de gas y el de petróleo muestran cada una.</p>
      </Panel>
    </div>
  );
}
