"use client";

import { useRef } from "react";

import type { Sector } from "@/lib/tipos";

const OPCIONES: { id: Sector; etiqueta: string; color: string }[] = [
  { id: "petroleo", etiqueta: "Petróleo", color: "var(--acento-petroleo)" },
  { id: "gas", etiqueta: "Gas natural", color: "var(--acento-gas)" },
];

/** Selector de sector con patrón de radio group (flechas para moverse, como indica WAI-ARIA). */
export function SelectorSector({ sector, onCambiar }: { sector: Sector; onCambiar: (s: Sector) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const teclado = (e: React.KeyboardEvent, i: number) => {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    const sig = (i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1) + OPCIONES.length) % OPCIONES.length;
    onCambiar(OPCIONES[sig].id);
    refs.current[sig]?.focus();
  };

  return (
    <div role="radiogroup" aria-label="Sector" className="inline-flex rounded-full border border-linea bg-superficie p-1">
      {OPCIONES.map((o, i) => {
        const activo = o.id === sector;
        return (
          <button
            key={o.id}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="radio"
            aria-checked={activo}
            tabIndex={activo ? 0 : -1}
            onClick={() => onCambiar(o.id)}
            onKeyDown={(e) => teclado(e, i)}
            className={`flex min-h-11 items-center gap-2 rounded-full px-5 text-sm font-medium transition-colors ${
              activo ? "bg-tinta text-fondo" : "text-tinta-2 hover:text-tinta"
            }`}
          >
            <span aria-hidden className="size-2.5 rounded-full" style={{ background: o.color }} />
            {o.etiqueta}
          </button>
        );
      })}
    </div>
  );
}
