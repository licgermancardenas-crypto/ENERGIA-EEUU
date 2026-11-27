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
  return (
    <Pagina activa="Análisis" titulo="Análisis geoespacial"
      bajada="Densidad de la red, alcance del Henry Hub y dependencia del gas de red para calefaccionar" ind={i} geo>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="Hogares con gas de red" nota="calefacción · total país" valor={hogares ? `${num((conGas / hogares) * 100, 1)} %` : "—"} color={GAS} icono="casa" />
        <Kpi etiqueta="Condados en alerta" nota={`≥ 50 % gas de red y > ${UMBRAL_KM} km`} valor={`${alerta}`} color="#a35400" icono="alerta" />
        <Kpi etiqueta="Balance interestatal" nota="API de flujos de la EIA" valor="—" color="#7a8394" icono="flechas-opuestas" />
        <Kpi etiqueta="Centrales cerca de la red" nota="EIA-860M" valor="—" color="#7a8394" icono="rayo" />
      </div>
      <VistaAnalisis geo={g} umbralKm={UMBRAL_KM} />
    </Pagina>
  );
}
