"use client";

import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Barras } from "@/lib/tipos";
import { fechaCorta, mesAnio, pctConSigno, UNIDADES, valor } from "@/lib/formato";

import { TablaDatos } from "./TablaDatos";

export function BarrasSector({ barras }: { barras: Barras }) {
  const unidadTxt = UNIDADES[barras.unidad]?.corta ?? barras.unidad;
  const mensual = barras.unidad === "MMCF";
  const fecha = mensual ? mesAnio(barras.fecha) : `semana del ${fechaCorta(barras.fecha)}`;
  const datos = barras.items.map((i) => ({ ...i, etiqueta: valor(i.valor, barras.unidad) }));

  return (
    <section aria-labelledby="t-barras" className="h-full rounded-2xl border border-linea bg-superficie p-5 sm:p-6">
      <h2 id="t-barras" className="font-display text-xl font-semibold">{barras.titulo}</h2>
      <p className="mt-1 text-sm text-tinta-2">
        Último dato: {fecha}. Unidad: {unidadTxt}.
        {barras.fechas_distintas && " Algunas series tienen fechas distintas (ver tabla)."}
      </p>
      <div className="mt-4 h-72" role="img" aria-label={`${barras.titulo}: ${barras.items.map((i) => `${i.nombre} ${valor(i.valor, barras.unidad)}`).join("; ")}.`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} layout="vertical" margin={{ top: 0, right: 88, bottom: 0, left: 0 }} barCategoryGap={10}>
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="nombre"
              width={128}
              tick={{ fill: "var(--tinta)", fontSize: 13 }}
              tickLine={false}
              axisLine={{ stroke: "var(--linea)" }}
            />
            <Tooltip
              cursor={{ fill: "var(--superficie-2)" }}
              content={({ active, payload }) => {
                const p = active && payload?.[0]?.payload;
                return p ? (
                  <div className="cifra rounded-lg border border-linea bg-superficie px-3 py-2 text-sm shadow-lg">
                    <p className="font-medium">{p.nombre}</p>
                    <p>{valor(p.valor, barras.unidad)} {unidadTxt}</p>
                    {p.variacion_pct !== null && (
                      <p className="text-tinta-2">{pctConSigno(p.variacion_pct)} vs. período anterior</p>
                    )}
                  </div>
                ) : null;
              }}
            />
            <Bar dataKey="valor" fill="var(--s1)" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey="etiqueta" position="right" fill="var(--tinta)" fontSize={13} className="cifra" />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TablaDatos
        titulo={barras.titulo}
        columnas={["Serie", "Fecha", `Valor (${unidadTxt})`, "Variación"]}
        filas={barras.items.map((i) => [
          i.nombre,
          mensual ? mesAnio(i.fecha) : fechaCorta(i.fecha),
          valor(i.valor, barras.unidad),
          i.variacion_pct === null ? "—" : pctConSigno(i.variacion_pct),
        ])}
      />
    </section>
  );
}
