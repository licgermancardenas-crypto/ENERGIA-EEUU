"use client";

import { useEffect, useRef, useState } from "react";

import { num } from "@/lib/formato";

/** Número que sube desde 0 al entrar (1,6 s, desacelerando). Sin animación si animar = false. */
export function Conteo({ valor, decimales, animar, prefijo = "" }:
  { valor: number | null; decimales: number; animar: boolean; prefijo?: string }) {
  const [v, setV] = useState(animar ? 0 : valor ?? 0);
  const inicio = useRef<number | null>(null);
  useEffect(() => {
    if (valor == null || !animar) return;
    let raf = 0;
    const paso = (ahora: number) => {
      inicio.current ??= ahora;
      const s = Math.min(1, (ahora - inicio.current) / 1600);
      setV(valor * (1 - (1 - s) ** 3));
      if (s < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [valor, animar]);
  if (valor == null) return <>—</>;
  return <span aria-label={`${prefijo}${num(valor, decimales)}`}>{prefijo}{num(animar ? v : valor, decimales)}</span>;
}
