"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { EscenarioRezago, Rezago } from "@/lib/tipos";
import { mesAnio, num } from "@/lib/formato";

import { TablaDatos } from "./TablaDatos";

function meses(n: number | null) {
  if (n === null) return "sin resultado";
  return n === 1 ? "1 mes" : `${n} meses`;
}

function Resumen({ e }: { e: EscenarioRezago }) {
  return (
    <div className="rounded-xl border border-linea bg-superficie p-4">
      <p className="text-sm text-tinta-2">{e.etiqueta}</p>
      <p className="cifra mt-1 font-display text-3xl font-semibold">{meses(e.rezago_optimo_meses)}</p>
      <p className="cifra mt-1 text-sm text-tinta-2">
        r = {e.correlacion === null ? "—" : num(e.correlacion, 2)} · {e.n_obs ?? "—"} meses comparados
        {e.desde && e.hasta && ` · ${mesAnio(e.desde)} a ${mesAnio(e.hasta)}`}
      </p>
    </div>
  );
}

export function SeccionRezago({ rezago }: { rezago: Rezago }) {
  const [id, setId] = useState(rezago.escenarios[0].id);
  const esc = rezago.escenarios.find((e) => e.id === id) ?? rezago.escenarios[0];
  const [completo, sinPandemia] = rezago.escenarios;
  const datos = esc.detalle.filter((d) => d.correlacion !== null);

  return (
    <section aria-labelledby="t-rezago" className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-tinta-2">Petróleo · análisis</p>
        <h2 id="t-rezago" className="mt-1 font-display text-3xl font-semibold">
          ¿Cuánto tarda la producción en reaccionar al precio?
        </h2>
        <p className="mt-2 max-w-3xl text-tinta-2">
          Comparamos la variación mensual del WTI con la variación de la producción de crudo de 0 a 12 meses
          después, y buscamos el desfasaje donde más se parecen. Lo calculamos de dos maneras porque 2020 fue un
          año extremo: el precio y la producción se desplomaron y rebotaron casi a la vez.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {completo && <Resumen e={completo} />}
        {sinPandemia && <Resumen e={sinPandemia} />}
      </div>

      {completo && sinPandemia && completo.rezago_optimo_meses !== sinPandemia.rezago_optimo_meses && (
        <p className="max-w-3xl">
          Con la historia completa el mayor parecido aparece a {meses(completo.rezago_optimo_meses)}; sin
          2020-2021 se corre a {meses(sinPandemia.rezago_optimo_meses)}
          {sinPandemia.correlacion !== null && completo.correlacion !== null &&
            sinPandemia.correlacion < completo.correlacion &&
            ", con una relación más débil"}
          . La diferencia muestra cuánto pesa la pandemia en el resultado: ninguna de las dos cifras es una
          regla fija.
        </p>
      )}

      <div className="rounded-2xl border border-linea bg-superficie p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-display text-lg font-semibold">Correlación por desfasaje</h3>
          <div role="group" aria-label="Escenario" className="flex flex-wrap gap-1">
            {rezago.escenarios.map((e) => (
              <button
                key={e.id}
                type="button"
                aria-pressed={e.id === id}
                onClick={() => setId(e.id)}
                className={`min-h-9 rounded-full border px-3 text-sm transition-colors ${
                  e.id === id ? "border-tinta bg-tinta text-fondo" : "border-linea text-tinta-2 hover:text-tinta"
                }`}
              >
                {e.etiqueta}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-1 text-sm text-tinta-2">
          Barra resaltada: desfasaje con la mayor correlación ({meses(esc.rezago_optimo_meses)}). Valores de −1 a 1.
        </p>
        <div className="mt-4 h-64" role="img" aria-label={`Correlación entre WTI y producción según meses de desfasaje, escenario ${esc.etiqueta}. Máximo en ${meses(esc.rezago_optimo_meses)}.`}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={datos} margin={{ top: 8, right: 8, bottom: 16, left: 0 }} barCategoryGap={4}>
              <CartesianGrid stroke="var(--grilla)" vertical={false} />
              <XAxis
                dataKey="rezago_meses"
                tick={{ fill: "var(--tinta-2)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                label={{ value: "meses después del cambio de precio", position: "insideBottom", offset: -10, fill: "var(--tinta-2)", fontSize: 12 }}
              />
              <YAxis
                tickFormatter={(v: number) => num(v, 1)}
                tick={{ fill: "var(--tinta-2)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <ReferenceLine y={0} stroke="var(--tinta-2)" />
              <Tooltip
                cursor={{ fill: "var(--superficie-2)" }}
                content={({ active, payload }) => {
                  const p = active && payload?.[0]?.payload;
                  return p ? (
                    <div className="cifra rounded-lg border border-linea bg-superficie px-3 py-2 text-sm shadow-lg">
                      <p className="font-medium">Desfasaje de {meses(p.rezago_meses)}</p>
                      <p>r = {num(p.correlacion, 3)}</p>
                      <p className="text-tinta-2">{p.n_obs} meses comparados</p>
                    </div>
                  ) : null;
                }}
              />
              <Bar dataKey="correlacion" radius={[4, 4, 4, 4]} isAnimationActive={false}>
                {datos.map((d) => (
                  <Cell key={d.rezago_meses} fill={d.rezago_meses === esc.rezago_optimo_meses ? "var(--s2)" : "var(--apagado)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <TablaDatos
          titulo={`Correlación por desfasaje — ${esc.etiqueta}`}
          columnas={["Desfasaje", "Correlación", "Meses comparados"]}
          filas={esc.detalle.map((d) => [
            meses(d.rezago_meses),
            d.correlacion === null ? "—" : num(d.correlacion, 3),
            String(d.n_obs),
          ])}
        />
      </div>

      <aside role="note" aria-label="Advertencia" className="flex gap-3 rounded-xl border-l-4 bg-superficie-2 p-4" style={{ borderColor: "var(--alerta)" }}>
        <span aria-hidden className="text-lg leading-none text-alerta">⚠</span>
        <div className="text-sm leading-relaxed">
          <p className="font-medium">Correlación no es causalidad</p>
          <p className="mt-1">{rezago.advertencia}</p>
          <p className="mt-1 text-tinta-2">
            Método: {esc.metodo}; criterio: {esc.criterio}. Una correlación de {num(esc.correlacion ?? 0, 2)} es
            {Math.abs(esc.correlacion ?? 0) < 0.3 ? " débil" : " moderada"}: la producción también depende de costos,
            tecnología, infraestructura y decisiones de las empresas.
          </p>
        </div>
      </aside>
    </section>
  );
}
