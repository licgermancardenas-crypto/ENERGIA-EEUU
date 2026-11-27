import { BarrasH, Lineas } from "@/components/graficos";
import { Icono, Kpi, Pagina, Panel } from "@/components/marco";
import { cargarDatos } from "@/lib/datos";
import { num } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const PET = "#c4531a", GAS = "#1f6fd1", OCRE = "#a87d00";
const v = (x: number | null, dec = 0) => (x == null ? "—" : num(x, dec));

function Nota({ icono, color, texto }: { icono: string; color: string; texto: string }) {
  return <span className="flex items-center gap-1.5 text-xs" style={{ color }}><Icono nombre={icono} color={color} tam={15} />{texto}</span>;
}

export default function Petroleo() {
  const d = cargarDatos();
  const i = indicadores(d);
  const surtidor = d.destacados.petroleo.barras.items.map((x) => ({
    nombre: x.nombre, valor: x.valor, color: /di[eé]sel/i.test(x.nombre) ? OCRE : PET }));
  return (
    <Pagina activa="Petróleo" titulo="Petróleo: precios, inventarios y producción"
      bajada="Precios diarios, inventarios semanales y producción mensual" ind={i}>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="WTI" nota="US$ por barril" valor={v(i.wti, 2)} color={PET} icono="gota" />
        <Kpi etiqueta="Crudo comercial" nota="miles de barriles" valor={v(i.crudo)} color={PET} icono="tanque" />
        <Kpi etiqueta="Reserva estratégica" nota="miles de barriles" valor={v(i.spr)} color={PET} icono="boveda" />
        <Kpi etiqueta="Variación semanal" nota="miles de barriles"
          valor={i.crudoSemanal == null ? "—" : `${i.crudoSemanal > 0 ? "+" : ""}${num(i.crudoSemanal, 0)}`}
          color={PET} icono={i.crudoSemanal != null && i.crudoSemanal < 0 ? "tendencia-baja" : "tendencia-sube"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Panel titulo="Precio spot WTI y Brent" nota="US$ por barril">
          <Lineas conAnio decimales={2} series={[
            { nombre: "Precio WTI", color: GAS, datos: d.hechos.RWTC_D },
            { nombre: "Precio Brent", color: PET, datos: d.hechos.RBRTE_D }]} />
        </Panel>
        <Panel titulo="Precio en surtidor" nota="US$ por galón · última semana · diésel en ocre" icono="surtidor" iconoColor={PET}>
          <BarrasH items={surtidor} decimales={3} />
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel titulo="Inventarios de crudo" nota="miles de barriles"
          accion={<Nota icono="alerta" color="#a35400" texto="2026: fuerte caída de la reserva estratégica" />}>
          <Lineas series={[
            { nombre: "Stock crudo comercial", color: GAS, datos: d.hechos.WCESTUS1_W },
            { nombre: "Stock SPR", color: PET, datos: d.hechos.WCSSTUS1_W }]} />
        </Panel>
        <Panel titulo="Producción de crudo" nota="miles de barriles por día"
          accion={<Nota icono="info" color="#4a5260" texto="2020: COVID, caída y rebote" />}>
          <Lineas series={[{ nombre: "Producción de crudo", color: PET, datos: d.hechos.MCRFPUS2_M }]} />
        </Panel>
      </div>
    </Pagina>
  );
}
