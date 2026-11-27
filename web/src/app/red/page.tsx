import { Kpi, Pagina } from "@/components/marco";
import { VistaRed } from "@/components/vistas-geo";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { num } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const GAS = "#1f6fd1";

export default function Red() {
  const d = cargarDatos();
  const g = cargarGeo();
  const i = indicadores(d);
  // gas almacenado de la última semana por región de almacenamiento (R31..R35)
  const gasRegion = Object.fromEntries(["R31", "R32", "R33", "R34", "R35"]
    .map((r) => [r, d.ultimo[`NW2_EPG0_SWO_${r}_BCF_W`]?.valor])
    .filter(([, v]) => v != null)) as Record<string, number>;
  return (
    <Pagina activa="Red" titulo="La red de gas natural"
      bajada="Gasoductos, hubs, terminales de GNL, reserva estratégica y gas almacenado por región" ind={i} geo>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="Red de gasoductos" nota="km totales" valor={num(g.validacion.km_red_total, 0)} color={GAS} icono="red" />
        <Kpi etiqueta="Estados con el Henry Hub" nota="cruzados por la red conectada" valor={`${g.estados.filter((e) => e.hh).length}`} color={GAS} icono="llama" />
        <Kpi etiqueta="Terminales de GNL" nota="importación y exportación" valor={`${g.puntos.gnl.length}`} color={GAS} icono="torre" />
        <Kpi etiqueta="Henry Hub" nota="US$ por MMBtu" valor={i.hh == null ? "—" : num(i.hh, 2)} color="#c4531a" icono="llama" />
      </div>
      <VistaRed geo={g} gasRegion={gasRegion} precioHH={i.hh} />
    </Pagina>
  );
}
