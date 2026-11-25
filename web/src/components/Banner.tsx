import type { Datos, Destacado } from "@/lib/tipos";
import { comparacion, fechaSegunFrecuencia, UNIDADES, valor } from "@/lib/formato";

import { Variacion } from "./Variacion";

function Dato({ datos, k, principal }: { datos: Datos; k: string; principal?: boolean }) {
  const s = datos.series[k];
  const u = datos.ultimo[k];
  const unidad = UNIDADES[s.unidad]?.corta ?? s.unidad;
  return (
    <div className={principal ? "" : "border-t border-linea pt-4 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0"}>
      <p className="text-sm font-medium text-tinta-2">
        {s.nombre}
        <span className="font-normal"> · {fechaSegunFrecuencia(u.fecha, s.frecuencia)}</span>
      </p>
      <p className={`cifra mt-1 font-display font-semibold leading-none ${principal ? "text-6xl sm:text-7xl" : "text-3xl"}`}>
        {valor(u.valor, s.unidad)}
        <span className="ml-2 align-baseline font-sans text-base font-normal text-tinta-2">{unidad}</span>
      </p>
      <p className="mt-2 text-sm">
        <Variacion pct={u.variacion_pct} sufijo={comparacion(s.frecuencia)} />
      </p>
    </div>
  );
}

export function Banner({ datos, banner }: { datos: Datos; banner: Destacado["banner"] }) {
  return (
    <section aria-labelledby="t-banner" className="rounded-2xl border border-linea bg-superficie p-6 sm:p-8">
      <h2 id="t-banner" className="font-mono text-xs uppercase tracking-[0.18em] text-tinta-2">
        Último dato publicado
      </h2>
      <div className="mt-4 grid gap-6 sm:grid-cols-[1.4fr_1fr_1fr] sm:items-end">
        <Dato datos={datos} k={banner.principal} principal />
        {banner.indicadores.map((k) => (
          <Dato key={k} datos={datos} k={k} />
        ))}
      </div>
    </section>
  );
}
