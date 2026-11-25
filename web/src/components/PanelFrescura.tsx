import type { Frescura, Meta } from "@/lib/tipos";
import { etiquetaFrecuencia, fechaCorta, fechaSegunFrecuencia, num } from "@/lib/formato";

const NOMBRES: Record<string, string> = {
  precios_spot_diarios: "Precios spot de crudo (WTI, Brent)",
  henry_hub_diario: "Precio spot Henry Hub",
  precios_spot_mensuales: "Precios spot mensuales de crudo",
  henry_hub_mensual: "Henry Hub mensual",
  precio_surtidor_semanal: "Precios en surtidor",
  inventarios_semanales: "Inventarios de crudo y productos",
  almacenamiento_gas_semanal: "Almacenamiento de gas",
  produccion_crudo_mensual: "Producción de crudo",
  produccion_gas_mensual: "Producción de gas",
  consumo_gas_mensual: "Consumo de gas por sector",
};

export function PanelFrescura({ frescura, meta }: { frescura: Frescura; meta: Meta }) {
  const atrasados = frescura.datasets.filter((d) => d.estado !== "al_dia").length;
  return (
    <section aria-labelledby="t-frescura" className="rounded-2xl border border-linea bg-superficie p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="t-frescura" className="font-display text-xl font-semibold">Frescura de los datos</h2>
        <p className="text-sm text-tinta-2">
          Calculado al {fechaCorta(frescura.calculado_al)} ·{" "}
          {atrasados === 0 ? "todas las fuentes al día" : `${atrasados} fuente(s) atrasada(s)`}
        </p>
      </div>
      <p className="mt-1 max-w-3xl text-sm text-tinta-2">
        Cada fuente tiene su ritmo: la EIA publica precios diarios con unos días de demora, inventarios cada semana
        y producción y consumo con un par de meses de rezago. El atraso se mide desde el fin del período.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="cifra w-full min-w-[640px] text-left text-sm">
          <thead className="text-tinta-2">
            <tr className="border-b border-linea">
              <th scope="col" className="py-2 pr-3 font-medium">Fuente</th>
              <th scope="col" className="py-2 pr-3 font-medium">Frecuencia</th>
              <th scope="col" className="py-2 pr-3 font-medium">Último período</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Atraso / tolerancia</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Filas</th>
              <th scope="col" className="py-2 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {frescura.datasets.map((d) => {
              const ok = d.estado === "al_dia";
              return (
                <tr key={d.dataset} className="border-b border-linea last:border-0">
                  <th scope="row" className="py-2 pr-3 font-normal">{NOMBRES[d.dataset] ?? d.dataset}</th>
                  <td className="py-2 pr-3">{etiquetaFrecuencia(d.frecuencia)}</td>
                  <td className="py-2 pr-3">{fechaSegunFrecuencia(d.ultimo_periodo, d.frecuencia)}</td>
                  <td className="py-2 pr-3 text-right">{d.dias_atraso} / {d.umbral_dias} días</td>
                  <td className="py-2 pr-3 text-right">{num(d.filas, 0)}</td>
                  <td className="py-2">
                    <span className={`inline-flex items-center gap-1.5 font-medium ${ok ? "text-ok" : "text-alerta"}`}>
                      <span aria-hidden>{ok ? "●" : "▲"}</span>
                      {ok ? "Al día" : "Atrasado"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-tinta-2">
        Capa Gold generada el {fechaCorta(meta.gold_generado_utc)} (UTC) ·{" "}
        {num(Object.values(meta.conteos).reduce((a, b) => a + b, 0), 0)} filas en las tablas Gold.
      </p>
    </section>
  );
}
