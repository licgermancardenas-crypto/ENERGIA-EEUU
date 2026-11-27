import { BarrasH, Columnas100, Lineas } from "@/components/graficos";
import { Icono, Kpi, Pagina, Panel } from "@/components/marco";
import { cargarDatos } from "@/lib/datos";
import { num, pctConSigno } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const GAS = "#1f6fd1";
const v = (x: number | null, dec = 0) => (x == null ? "—" : num(x, dec));
const SECTORES = [
  { k: "N3010US2_M", nombre: "Residencial", color: "#1f6fd1", icono: "casa" },
  { k: "N3020US2_M", nombre: "Comercial", color: "#c4531a", icono: "edificio" },
  { k: "N3035US2_M", nombre: "Industrial", color: "#7a45c2", icono: "fabrica" },
  { k: "N3045US2_M", nombre: "Generación eléctrica", color: "#a87d00", icono: "rayo" },
  { k: "N3025US2_M", nombre: "Vehicular", color: "#5b6770", icono: "auto" },
];
const REGIONES: [string, string][] = [["R31", "Este"], ["R32", "Medio Oeste"], ["R33", "Centro Sur"],
  ["R34", "Montaña"], ["R35", "Pacífico"]];

export default function Gas() {
  const d = cargarDatos();
  const i = indicadores(d);
  // consumo anual por sector (suma de los meses de cada año)
  const anual = new Map<string, Record<string, number | string>>();
  for (const s of SECTORES) {
    for (const [f, val] of d.hechos[s.k] ?? []) {
      const a = f.slice(0, 4);
      const fila = anual.get(a) ?? { anio: a };
      fila[s.nombre] = Number(fila[s.nombre] ?? 0) + val;
      anual.set(a, fila);
    }
  }
  const regiones = REGIONES.map(([r, nombre]) => ({
    nombre, valor: d.ultimo[`NW2_EPG0_SWO_${r}_BCF_W`]?.valor ?? 0, color: GAS }));
  return (
    <Pagina activa="Gas" titulo="Gas natural: precio, almacenamiento y consumo"
      bajada="Henry Hub diario, almacenamiento semanal y consumo mensual por sector" ind={i}>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="Henry Hub" nota="US$ por MMBtu" valor={v(i.hh, 2)} color={GAS} icono="llama" />
        <Kpi etiqueta="Gas almacenado" nota="Bcf · Lower 48" valor={v(i.gas)} color={GAS} icono="cilindro" />
        <Kpi etiqueta="Vs. año anterior" nota="misma semana" valor={i.gasVsAnio == null ? "—" : pctConSigno(i.gasVsAnio)}
          color={GAS} icono={i.gasVsAnio != null && i.gasVsAnio < 0 ? "tendencia-baja" : "tendencia-sube"} />
        <Kpi etiqueta="Inyección neta" nota="Bcf en la semana"
          valor={i.inyeccion == null ? "—" : `${i.inyeccion > 0 ? "+" : ""}${num(i.inyeccion, 0)}`}
          color={GAS} icono={i.inyeccion != null && i.inyeccion < 0 ? "flecha-baja" : "flecha-sube"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Panel titulo="Precio Henry Hub" nota="US$ por MMBtu"
          accion={<span className="flex items-center gap-1.5 text-xs text-gas"><Icono nombre="copo" color={GAS} tam={15} />picos con olas de frío</span>}>
          <Lineas conAnio decimales={2} series={[{ nombre: "Henry Hub", color: GAS, datos: d.hechos.RNGWHHD_D }]} />
        </Panel>
        <Panel titulo="Almacenamiento por región" nota="Bcf · última semana">
          <BarrasH items={regiones} ancho={92} />
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel titulo="Consumo de gas por sector" nota="participación anual">
          <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tinta-2">
            {SECTORES.map((s) => (
              <li key={s.k} className="flex items-center gap-1.5"><Icono nombre={s.icono} color={s.color} tam={15} />{s.nombre}</li>
            ))}
          </ul>
          <Columnas100 filas={[...anual.values()]} series={SECTORES.map((s) => ({ clave: s.nombre, color: s.color }))} />
        </Panel>
        <Panel titulo="Gas almacenado Lower 48" nota="Bcf · el ciclo de inyección y extracción"
          accion={<span className="flex items-center gap-3 text-xs text-tinta-2">
            <span className="flex items-center gap-1"><Icono nombre="sol" color="#a35400" tam={15} />inyección (abr–oct)</span>
            <span className="flex items-center gap-1"><Icono nombre="copo" color={GAS} tam={15} />extracción (nov–mar)</span></span>}>
          <Lineas series={[{ nombre: "Gas almacenado", color: GAS, datos: d.hechos.NW2_EPG0_SWO_R48_BCF_W }]} />
        </Panel>
      </div>
    </Pagina>
  );
}
