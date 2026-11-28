import { readFileSync } from "node:fs";
import path from "node:path";

import { Icono, Kpi, Pagina, Panel } from "@/components/marco";
import type { MetaPetroleo } from "@/components/mapa-petroleo/tipos";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { fechaCorta, num } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const OK = "#1d7a3b", ALERTA = "#a35400", GRIS = "#4a5260";
const FREC: Record<string, string> = { daily: "diaria", weekly: "semanal", monthly: "mensual" };

function Barra({ dias, umbral }: { dias: number; umbral: number }) {
  const pct = Math.min(100, (dias / umbral) * 100);
  const color = dias > umbral ? ALERTA : OK;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 overflow-hidden rounded bg-[#ece7dd]">
        <div className="h-full rounded" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="cifra text-xs text-tinta-2">{dias} / {umbral} días</span>
    </div>
  );
}

export default function Calidad() {
  const d = cargarDatos();
  const g = cargarGeo();
  const mp = JSON.parse(readFileSync(path.join(process.cwd(), "public/data/petroleo/meta.json"), "utf-8")) as MetaPetroleo;
  const NOMBRES: Record<string, string> = { oleoductos: "Oleoductos de crudo", poliductos: "Poliductos de derivados",
    pulsos: "Pulsos ilustrativos (derivado)", terminales: "Terminales de derivados", puertos: "Puertos principales",
    plays: "Plays de shale", plataformas: "Plataformas offshore del Golfo", cushing: "Cushing (punto)",
    series: "Series API: producción y comercio de crudo" };
  const i = indicadores(d);
  const filas = [...d.frescura.datasets].sort((a, b) => b.dias_atraso / b.umbral_dias - a.dias_atraso / a.umbral_dias);
  return (
    <Pagina activa="Calidad" titulo="Calidad y frescura de los datos"
      bajada="Cada fuente se compara con el umbral de atraso esperado para su frecuencia" ind={i} geo>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="Fuentes al día" nota="datasets de la API" valor={`${i.fuentesAlDia} de ${i.fuentesTotal}`}
          color={i.fuentesAlDia === i.fuentesTotal ? OK : ALERTA} icono={i.fuentesAlDia === i.fuentesTotal ? "check-circulo" : "alerta"} />
        <Kpi etiqueta="Mayor atraso" nota="días desde el último período" valor={num(i.maxAtraso, 0)} color={GRIS} icono="reloj" />
        <Kpi etiqueta="Calculado al" nota="última corrida del pipeline" valor={fechaCorta(i.calculadoAl)} color={GRIS} icono="calendario" grande={false} />
        <Kpi etiqueta="Capas geo disponibles" nota="estáticas y encuestas"
          valor={`${g.frescura.filter((c) => c.estado === "disponible").length} de ${g.frescura.length}`} color={GRIS} icono="capas" />
      </div>
      <Panel titulo="Frescura por fuente (API de la EIA)" nota="ordenadas por atraso relativo al umbral" icono="escudo-check" iconoColor={OK}>
        <div className="overflow-x-auto">
          <table className="cifra w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-linea text-xs text-tinta-3">
              <tr><th className="py-2"></th><th>Dataset</th><th>Sector</th><th>Frecuencia</th><th>Último período</th><th>Atraso</th><th className="text-right">Filas</th></tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.dataset} className="border-b border-linea/60">
                  <td className="py-2 pr-2"><Icono nombre={f.estado === "al_dia" ? "check-circulo" : "alerta"} color={f.estado === "al_dia" ? OK : ALERTA} tam={16} titulo={f.estado === "al_dia" ? "al día" : "atrasado"} /></td>
                  <td className="font-medium">{f.dataset.replaceAll("_", " ")}</td>
                  <td className="flex items-center gap-1.5 py-2"><Icono nombre={f.sector === "petroleo" ? "gota" : "llama"} color={f.sector === "petroleo" ? "#c4531a" : "#1f6fd1"} tam={14} />{f.sector === "petroleo" ? "Petróleo" : "Gas"}</td>
                  <td>{FREC[f.frecuencia]}</td>
                  <td>{fechaCorta(f.ultimo_periodo)}</td>
                  <td><Barra dias={f.dias_atraso} umbral={f.umbral_dias} /></td>
                  <td className="text-right">{num(f.filas, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel titulo="Capas geoespaciales" nota="origen, vintage y estado de cada capa" icono="capas" iconoColor={GRIS}>
        <div className="overflow-x-auto">
          <table className="cifra w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-linea text-xs text-tinta-3">
              <tr><th className="py-2"></th><th>Capa</th><th>Tipo</th><th>Origen</th><th>Vintage</th><th className="text-right">Registros</th></tr>
            </thead>
            <tbody>
              {g.frescura.map((c) => {
                const ok = c.estado === "disponible";
                return (
                  <tr key={c.capa} className="border-b border-linea/60 align-top">
                    <td className="py-2 pr-2"><Icono nombre={ok ? "check-circulo" : "x-circulo"} color={ok ? OK : "#7a8394"} tam={16} titulo={c.estado} /></td>
                    <td className="py-2 font-medium">{c.capa}</td>
                    <td className="py-2">{c.tipo}</td>
                    <td className="py-2 text-xs text-tinta-2">{c.origen}</td>
                    <td className="py-2">{c.vintage ?? "—"}</td>
                    <td className="py-2 text-right">{c.registros == null ? "—" : num(c.registros, 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-tinta-3">
          Red total: {num(g.validacion.km_red_total, 0)} km · {num(g.validacion.pct_fuera, 1)} % fuera de los estados (costa afuera) ·
          sin km de red: {g.validacion.estados_sin_km.join(", ")} (real) · Flujos y centrales quedan &quot;no disponible&quot; mientras la API de la EIA no responda.
        </p>
      </Panel>
      <Panel titulo="Mapa de petróleo: capas y series" nota={`Descargadas el ${fechaCorta(mp.fecha_descarga)} con scripts/preparar_mapa_petroleo.py`} icono="gota" iconoColor="#c4531a">
        <div className="overflow-x-auto">
          <table className="cifra w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-linea text-xs text-tinta-3">
              <tr><th className="py-2"></th><th>Capa</th><th>Origen</th><th>Dato al</th><th className="text-right">Elementos</th></tr>
            </thead>
            <tbody>
              {Object.entries(mp.capas).map(([k, c]) => (
                <tr key={k} className="border-b border-linea/60 align-top">
                  <td className="py-2 pr-2"><Icono nombre="check-circulo" color={OK} tam={16} titulo="disponible" /></td>
                  <td className="py-2 font-medium">{NOMBRES[k] ?? k}</td>
                  <td className="py-2 text-xs text-tinta-2">{c.origen ?? "API v2 de la EIA (crpdn, imp, exp)"}{c.nota ? ` · ${c.nota}` : ""}</td>
                  <td className="py-2">{c.vintage ?? (k === "series" ? "último año publicado" : "no informado")}</td>
                  <td className="py-2 text-right">{c.elementos == null ? "—" : num(c.elementos, 0)}</td>
                </tr>
              ))}
              {mp.no_disponibles.map((n) => (
                <tr key={n.capa} className="border-b border-linea/60 align-top">
                  <td className="py-2 pr-2"><Icono nombre="x-circulo" color="#7a8394" tam={16} titulo="no disponible" /></td>
                  <td className="py-2 font-medium">{n.capa}</td>
                  <td className="py-2 text-xs text-tinta-2" colSpan={3}>No disponible: {n.motivo}.</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </Pagina>
  );
}
