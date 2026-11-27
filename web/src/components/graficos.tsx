"use client";

import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { fechaCorta, num } from "@/lib/formato";
import type { Punto } from "@/lib/tipos";

const EJE = { fontSize: 11, fill: "#7a8394" };
const fmtNum = (dec = 0) => (v: number) => num(v, dec);

/** Líneas con un selector de año opcional (igual que el segmentador "Año" del informe). */
export function Lineas({ series, alto = 240, decimales = 0, conAnio = false }:
  { series: { nombre: string; color: string; datos: Punto[] }[]; alto?: number;
    decimales?: number; conAnio?: boolean }) {
  const filas = useMemo(() => {
    const m = new Map<string, Record<string, number | string>>();
    for (const s of series) {
      for (const [f, v] of s.datos) {
        const fila = m.get(f) ?? { fecha: f };
        fila[s.nombre] = v;
        m.set(f, fila);
      }
    }
    return [...m.values()].sort((a, b) => String(a.fecha).localeCompare(String(b.fecha)));
  }, [series]);
  const anios = useMemo(() => [...new Set(filas.map((f) => String(f.fecha).slice(0, 4)))], [filas]);
  const [anio, setAnio] = useState("todos");
  const visibles = anio === "todos" ? filas : filas.filter((f) => String(f.fecha).startsWith(anio));
  return (
    <div>
      {conAnio && (
        <label className="mb-2 flex items-center gap-2 text-xs text-tinta-2">
          Año
          <select value={anio} onChange={(e) => setAnio(e.target.value)}
            className="rounded-md border border-linea bg-white px-2 py-1 text-xs">
            <option value="todos">Todos</option>
            {anios.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
      )}
      <ResponsiveContainer width="100%" height={alto}>
        <LineChart data={visibles} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#ece7dd" vertical={false} />
          <XAxis dataKey="fecha" tick={EJE} tickLine={false} axisLine={false} minTickGap={40}
            tickFormatter={(f: string) => (anio === "todos" ? f.slice(0, 4) : fechaCorta(f).slice(0, 5))} />
          <YAxis tick={EJE} tickLine={false} axisLine={false} width={64}
            tickFormatter={fmtNum(0)} domain={["auto", "auto"]} />
          <Tooltip formatter={(v) => num(Number(v), decimales)} labelFormatter={(f) => fechaCorta(String(f))}
            contentStyle={{ borderRadius: 8, border: "1px solid #e4ded2", fontSize: 12 }} />
          {series.length > 1 && <Legend verticalAlign="top" align="left" height={24} iconType="circle"
            wrapperStyle={{ fontSize: 12, color: "#4a5260" }} />}
          {series.map((s) => (
            <Line key={s.nombre} dataKey={s.nombre} stroke={s.color} strokeWidth={2} dot={false}
              isAnimationActive={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Barras horizontales con etiqueta de valor. */
export function BarrasH({ items, alto = 220, decimales = 0, ancho = 120 }:
  { items: { nombre: string; valor: number; color: string }[]; alto?: number;
    decimales?: number; ancho?: number }) {
  return (
    <ResponsiveContainer width="100%" height={alto}>
      <BarChart data={items} layout="vertical" margin={{ top: 0, right: 48, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#ece7dd" horizontal={false} />
        <XAxis type="number" tick={EJE} tickLine={false} axisLine={false} tickFormatter={fmtNum(0)} />
        <YAxis type="category" dataKey="nombre" tick={{ ...EJE, fill: "#4a5260" }} width={ancho}
          tickLine={false} axisLine={false} />
        <Tooltip formatter={(v) => num(Number(v), decimales)} cursor={{ fill: "#f4f1ea" }}
          contentStyle={{ borderRadius: 8, border: "1px solid #e4ded2", fontSize: 12 }} />
        <Bar dataKey="valor" radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {items.map((i) => <Cell key={i.nombre} fill={i.color} />)}
          <LabelList dataKey="valor" position="right" formatter={(v) => num(Number(v), decimales)}
            style={{ fontSize: 11, fill: "#4a5260" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Columnas apiladas al 100 % (participación anual por sector). */
export function Columnas100({ filas, series, alto = 240 }:
  { filas: Record<string, number | string>[]; series: { clave: string; color: string }[];
    alto?: number }) {
  return (
    <ResponsiveContainer width="100%" height={alto}>
      <BarChart data={filas} stackOffset="expand" margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#ece7dd" vertical={false} />
        <XAxis dataKey="anio" tick={EJE} tickLine={false} axisLine={false} minTickGap={16} />
        <YAxis tick={EJE} tickLine={false} axisLine={false} width={40}
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
        <Tooltip formatter={(v) => num(Number(v), 0) + " MMcf"} cursor={{ fill: "#f4f1ea" }}
          contentStyle={{ borderRadius: 8, border: "1px solid #e4ded2", fontSize: 12 }} />
        {series.map((s) => (
          <Bar key={s.clave} dataKey={s.clave} stackId="a" fill={s.color} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Correlación por rezago: naranja el óptimo, gris el resto (formato condicional del informe). */
export function ColumnasRezago({ detalle, optimo, alto = 230 }:
  { detalle: { rezago_meses: number; correlacion: number | null }[]; optimo: number | null;
    alto?: number }) {
  return (
    <ResponsiveContainer width="100%" height={alto}>
      <BarChart data={detalle} margin={{ top: 18, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#ece7dd" vertical={false} />
        <XAxis dataKey="rezago_meses" tick={EJE} tickLine={false} axisLine={false} />
        <YAxis tick={EJE} tickLine={false} axisLine={false} width={40} tickFormatter={fmtNum(1)} />
        <ReferenceLine y={0} stroke="#b9b3a8" />
        <Tooltip formatter={(v) => num(Number(v), 3)} labelFormatter={(m) => `${m} meses`}
          contentStyle={{ borderRadius: 8, border: "1px solid #e4ded2", fontSize: 12 }} />
        <Bar dataKey="correlacion" isAnimationActive={false}>
          {detalle.map((d) => (
            <Cell key={d.rezago_meses} fill={d.rezago_meses === optimo ? "#c4531a" : "#b9b3a8"} />
          ))}
          <LabelList dataKey="correlacion" position="top" formatter={(v) => num(Number(v), 3)}
            style={{ fontSize: 10, fill: "#4a5260" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
