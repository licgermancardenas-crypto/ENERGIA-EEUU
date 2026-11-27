import { Kpi, Pagina } from "@/components/marco";
import { VistaAnalisis } from "@/components/vistas-geo";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { num } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const GAS = "#1f6fd1";
const UMBRAL_KM = 25;

export default function Analisis() {
  const d = cargarDatos();
  const g = cargarGeo();
  const i = indicadores(d);
  const hogares = g.estados.reduce((s, e) => s + (e.hogares ?? 0), 0);
  const conGas = g.estados.reduce((s, e) => s + (e.hogares ?? 0) * (e.pct_gas_red ?? 0), 0);
  const alerta = Object.values(g.condados).filter((c) => c[4] === 1).length;
  const exportador = [...g.estados].filter((e) => e.balance != null).sort((a, b) => a.balance! - b.balance!)[0];
  const cs = g.puntos.centrales as unknown as { mw: number | null; cerca: boolean }[];
  const mwTotal = cs.reduce((s, c) => s + (c.mw ?? 0), 0);
  const mwCerca = cs.reduce((s, c) => s + (c.cerca ? c.mw ?? 0 : 0), 0);
  return (
    <Pagina activa="Análisis" titulo="Análisis geoespacial"
      bajada="Densidad de la red, alcance del Henry Hub y dependencia del gas de red para calefaccionar" ind={i} geo>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="Hogares con gas de red" nota="calefacción · total país" valor={hogares ? `${num((conGas / hogares) * 100, 1)} %` : "—"} color={GAS} icono="casa" />
        <Kpi etiqueta="Condados en alerta" nota={`≥ 50 % gas de red y > ${UMBRAL_KM} km`} valor={`${alerta}`} color="#a35400" icono="alerta" />
        <Kpi etiqueta="Mayor exportador neto" nota={exportador ? `${num(Math.abs(exportador.balance!) / 1000, 0)} Bcf en ${exportador.anio_balance}` : "flujos de la EIA"}
          valor={exportador?.nombre ?? "—"} color={GAS} icono="flechas-opuestas" grande={false} />
        <Kpi etiqueta="Centrales cerca de la red" nota={`% de la capacidad a ≤ ${UMBRAL_KM} km · EIA-860M`}
          valor={mwTotal ? `${num((mwCerca / mwTotal) * 100, 1)} %` : "—"} color={GAS} icono="rayo" />
      </div>
      <VistaAnalisis geo={{ ...g, puntos: { ...g.puntos, centrales: [] }, flujos: { anios: [], pares: [], estados: [] } }} umbralKm={UMBRAL_KM} />
    </Pagina>
  );
}
