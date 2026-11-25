"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Datos } from "@/lib/tipos";
import { compacto, fechaCorta, fechaEje, UNIDADES, valor } from "@/lib/formato";

import { TablaDatos } from "./TablaDatos";

// El color sigue a la serie (posición en la lista), nunca al ranking ni al filtro.
const COLORES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];

type Fila = { fecha: string } & Record<string, number | string | undefined>;

interface Props {
  titulo: string;
  nota: string;
  series: string[];
  datos: Datos;
  filtroAnio?: boolean;
}

export function GraficoLineas({ titulo, nota, series, datos, filtroAnio }: Props) {
  const filas = useMemo(() => {
    const porFecha = new Map<string, Fila>();
    for (const k of series) {
      for (const [f, v] of datos.hechos[k]) {
        const fila = porFecha.get(f) ?? { fecha: f };
        fila[k] = v;
        porFecha.set(f, fila);
      }
    }
    return [...porFecha.values()].sort((a, b) => a.fecha.localeCompare(b.fecha));
  }, [series, datos]);

  const anios = useMemo(() => [...new Set(filas.map((f) => f.fecha.slice(0, 4)))], [filas]);
  const [anio, setAnio] = useState<string>(filtroAnio ? anios[anios.length - 1] : "todo");
  const visibles = anio === "todo" ? filas : filas.filter((f) => f.fecha.startsWith(anio));

  const meta = series.map((k) => datos.series[k]);
  const unidad = meta[0].unidad;
  const unidadTxt = UNIDADES[unidad]?.corta ?? unidad;
  const idTitulo = `t-${series.join("-")}`;

  return (
    <section aria-labelledby={idTitulo} className="rounded-2xl border border-linea bg-superficie p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id={idTitulo} className="font-display text-xl font-semibold">{titulo}</h2>
          <p className="mt-1 text-sm text-tinta-2">{nota} Unidad: {unidadTxt}.</p>
        </div>
        {filtroAnio && (
          <div role="group" aria-label="Filtrar por año" className="flex flex-wrap gap-1">
            {[...anios, "todo"].map((a) => (
              <button
                key={a}
                type="button"
                aria-pressed={anio === a}
                onClick={() => setAnio(a)}
                className={`cifra min-h-9 rounded-full border px-3 text-sm transition-colors ${
                  anio === a ? "border-tinta bg-tinta text-fondo" : "border-linea text-tinta-2 hover:text-tinta"
                }`}
              >
                {a === "todo" ? "Todo" : a}
              </button>
            ))}
          </div>
        )}
      </div>

      {series.length > 1 && (
        <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm" aria-label="Leyenda">
          {meta.map((s, i) => (
            <li key={s.key} className="flex items-center gap-2">
              <span aria-hidden className="h-0.5 w-5 rounded" style={{ background: COLORES[i] }} />
              {s.nombre}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 h-72 sm:h-80" role="img" aria-label={`${titulo}: gráfico de líneas, ${visibles.length} observaciones. La tabla de datos está debajo.`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={visibles} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grilla)" vertical={false} />
            <XAxis
              dataKey="fecha"
              tickFormatter={fechaEje}
              minTickGap={48}
              tick={{ fill: "var(--tinta-2)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--linea)" }}
            />
            <YAxis
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => (Math.abs(v) >= 10000 ? compacto(v) : valor(v, unidad))}
              tick={{ fill: "var(--tinta-2)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            <Tooltip
              cursor={{ stroke: "var(--tinta-2)", strokeDasharray: "3 3" }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-linea bg-superficie px-3 py-2 text-sm shadow-lg">
                    <p className="font-medium">{fechaCorta(String(label))}</p>
                    {payload.map((p) => {
                      const i = series.indexOf(String(p.dataKey));
                      return (
                        <p key={String(p.dataKey)} className="cifra flex items-center gap-2">
                          <span aria-hidden className="size-2 rounded-full" style={{ background: COLORES[i] }} />
                          <span className="text-tinta-2">{meta[i].nombre}:</span>
                          {valor(Number(p.value), unidad)}
                        </p>
                      );
                    })}
                  </div>
                ) : null
              }
            />
            {series.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={COLORES[i]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--superficie)" }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <TablaDatos
        titulo={titulo}
        columnas={["Fecha", ...meta.map((s) => `${s.nombre} (${unidadTxt})`)]}
        filas={visibles
          .slice()
          .reverse()
          .map((f) => [fechaCorta(f.fecha), ...series.map((k) => (f[k] === undefined ? "—" : valor(Number(f[k]), unidad)))])}
      />
    </section>
  );
}
