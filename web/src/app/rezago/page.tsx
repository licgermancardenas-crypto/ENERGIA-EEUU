import { ColumnasRezago } from "@/components/graficos";
import { Icono, Kpi, Pagina, Panel } from "@/components/marco";
import { cargarDatos } from "@/lib/datos";
import { mesAnio, num } from "@/lib/formato";
import { indicadores } from "@/lib/indicadores";

const PET = "#c4531a", GRIS = "#4a5260";

export default function Rezago() {
  const d = cargarDatos();
  const i = indicadores(d);
  const [completo, sinPandemia] = d.rezago.escenarios;
  return (
    <Pagina activa="Rezago" titulo="¿Cuánto tarda la producción en seguir al precio?"
      bajada="Correlación entre el WTI mensual y la producción de crudo, desplazada entre 0 y 12 meses" ind={i}>
      <div className="tarjeta flex items-center gap-6 px-5 py-4">
        <svg viewBox="0 0 420 60" className="h-14 w-full max-w-[420px] flex-none" aria-label="Precio, rezago y producción">
          <circle cx={30} cy={30} r={22} fill="none" stroke={PET} strokeWidth={2.5} />
          <text x={30} y={35} textAnchor="middle" fontSize={13} fontWeight={700} fill={PET}>US$</text>
          <line x1={60} y1={30} x2={170} y2={30} stroke="#b9b3a8" strokeWidth={2} strokeDasharray="5 4" />
          <circle cx={210} cy={30} r={22} fill="none" stroke={GRIS} strokeWidth={2.5} />
          <text x={210} y={35} textAnchor="middle" fontSize={12} fontWeight={700} fill={GRIS}>
            {completo.rezago_optimo_meses ?? "?"} m
          </text>
          <line x1={240} y1={30} x2={350} y2={30} stroke="#b9b3a8" strokeWidth={2} strokeDasharray="5 4" />
          <polygon points="352,24 362,30 352,36" fill="#b9b3a8" />
          <circle cx={390} cy={30} r={22} fill="none" stroke={PET} strokeWidth={2.5} />
          <text x={390} y={35} textAnchor="middle" fontSize={11} fontWeight={700} fill={PET}>bbl/d</text>
        </svg>
        <p className="text-sm text-tinta-2">
          El precio se mueve primero; la producción responde meses después. El rezago óptimo es el
          desplazamiento con mayor correlación.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Kpi etiqueta="Rezago óptimo" nota="serie completa" valor={`${completo.rezago_optimo_meses ?? "—"} meses`} color={PET} icono="reloj" />
        <Kpi etiqueta="Correlación" nota="en el rezago óptimo" valor={completo.correlacion == null ? "—" : num(completo.correlacion, 3)} color={PET} icono="pulso" />
        <Kpi etiqueta="Rezago sin pandemia" nota={sinPandemia.etiqueta} valor={`${sinPandemia.rezago_optimo_meses ?? "—"} meses`} color={GRIS} icono="calendario" />
        <Kpi etiqueta="Meses analizados" nota="observaciones" valor={completo.n_obs == null ? "—" : num(completo.n_obs, 0)} color={GRIS} icono="info" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {d.rezago.escenarios.map((e) => (
          <Panel key={e.id} titulo={`Correlación por rezago · ${e.etiqueta}`}
            nota={`${e.desde ? mesAnio(e.desde) : ""} a ${e.hasta ? mesAnio(e.hasta) : ""} · en naranja, el óptimo`}>
            <ColumnasRezago detalle={e.detalle} optimo={e.rezago_optimo_meses} />
          </Panel>
        ))}
      </div>
      <p className="tarjeta flex items-start gap-2 px-4 py-3 text-sm text-tinta-2">
        <Icono nombre="alerta" color="#a35400" tam={18} />
        {d.rezago.advertencia}
      </p>
    </Pagina>
  );
}
