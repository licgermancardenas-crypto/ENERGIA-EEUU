import { Lineas } from "@/components/graficos";
import { Kpi, Pagina, Panel, Seccion } from "@/components/marco";
import { cargarDatos } from "@/lib/datos";
import { num, pctConSigno } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const PET = "#c4531a", GAS = "#1f6fd1";
const v = (x: number | null, dec = 0) => (x == null ? "—" : num(x, dec));
const p = (x: number | null) => (x == null ? "—" : pctConSigno(x));
const tendencia = (x: number | null) => (x != null && x < 0 ? "tendencia-baja" : "tendencia-sube");

export default function Resumen() {
  const d = cargarDatos();
  const i = indicadores(d);
  return (
    <Pagina activa="Resumen" titulo="El pulso hoy" bajada="Último dato publicado de cada serie de la EIA" ind={i}>
      <Seccion texto="PETRÓLEO" icono="gota" color={PET} />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <Kpi etiqueta="WTI" nota="US$ por barril" valor={v(i.wti, 2)} color={PET} icono="gota" />
        <Kpi etiqueta="WTI vs. promedio 12 m" nota="variación" valor={p(i.wtiVsProm)} color={PET} icono={tendencia(i.wtiVsProm)} />
        <Kpi etiqueta="Brent − WTI" nota="US$ por barril" valor={v(i.diferencial, 2)} color={PET} icono="flechas-opuestas" />
        <Kpi etiqueta="Crudo comercial" nota="miles de barriles" valor={v(i.crudo)} color={PET} icono="tanque" />
        <Kpi etiqueta="Crudo vs. año anterior" nota="misma semana" valor={p(i.crudoVsAnio)} color={PET} icono={tendencia(i.crudoVsAnio)} />
      </div>
      <Seccion texto="GAS NATURAL" icono="llama" color={GAS} />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <Kpi etiqueta="Henry Hub" nota="US$ por MMBtu" valor={v(i.hh, 2)} color={GAS} icono="llama" />
        <Kpi etiqueta="Henry Hub vs. prom. 12 m" nota="variación" valor={p(i.hhVsProm)} color={GAS} icono={tendencia(i.hhVsProm)} />
        <Kpi etiqueta="Gas almacenado" nota="Bcf · Lower 48" valor={v(i.gas)} color={GAS} icono="cilindro" />
        <Kpi etiqueta="Inyección neta" nota="Bcf en la semana" valor={i.inyeccion == null ? "—" : `${i.inyeccion > 0 ? "+" : ""}${num(i.inyeccion, 0)}`}
          color={GAS} icono={i.inyeccion != null && i.inyeccion < 0 ? "flecha-baja" : "flecha-sube"} />
        <Kpi etiqueta="Generación eléctrica" nota="del consumo de gas" valor={i.generacion == null ? "—" : `${num(i.generacion * 100, 1)} %`} color={GAS} icono="rayo" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel titulo="Precio spot del crudo" nota="US$ por barril">
          <Lineas decimales={2} series={[
            { nombre: "Precio WTI", color: GAS, datos: d.hechos.RWTC_D },
            { nombre: "Precio Brent", color: PET, datos: d.hechos.RBRTE_D }]} />
        </Panel>
        <Panel titulo="Gas natural almacenado" nota="Bcf · Lower 48">
          <Lineas series={[{ nombre: "Gas almacenado", color: GAS, datos: d.hechos.NW2_EPG0_SWO_R48_BCF_W }]} />
        </Panel>
      </div>
    </Pagina>
  );
}
