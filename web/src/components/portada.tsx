"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fechaCorta, num } from "@/lib/formato";
import type { Punto, Punto2 } from "@/lib/tipos";

import { MiniRed } from "./mapas";

/** Tendencia del último año en cian sobre fondo oscuro (panel HUD). */
export function TendenciaHud({ datos }: { datos: Punto[] }) {
  const ultimo = datos.length ? new Date(datos[datos.length - 1][0]) : new Date();
  const desde = new Date(ultimo); desde.setFullYear(ultimo.getFullYear() - 1);
  const filas = datos.filter(([f]) => new Date(f) >= desde).map(([fecha, v]) => ({ fecha, v }));
  return (
    <ResponsiveContainer width="100%" height={150}>
      <AreaChart data={filas} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="cian" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#5fb3e6" stopOpacity={0.35} />
            <stop offset="1" stopColor="#5fb3e6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="fecha" tick={{ fontSize: 10, fill: "#9db7dd" }} tickLine={false}
          axisLine={false} minTickGap={50} tickFormatter={(f: string) => fechaCorta(f).slice(3)} />
        <YAxis tick={{ fontSize: 10, fill: "#9db7dd" }} tickLine={false} axisLine={false} width={34}
          domain={["dataMin - 5", "dataMax + 5"]} tickFormatter={(v: number) => num(v, 0)} />
        <Tooltip formatter={(v) => `US$ ${num(Number(v), 2)}`} labelFormatter={(f) => fechaCorta(String(f))}
          contentStyle={{ background: "#0b1f3a", border: "1px solid #5fb3e6", borderRadius: 6, color: "#fff", fontSize: 12 }} />
        <Area dataKey="v" stroke="#5fb3e6" strokeWidth={1.8} fill="url(#cian)" isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function MiniRedHud({ hh }: { hh: Punto2 | undefined }) {
  return <MiniRed hh={hh} />;
}
