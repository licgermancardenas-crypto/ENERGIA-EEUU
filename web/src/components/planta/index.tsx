"use client";

// Punto de entrada de /planta: elige el modo y carga la escena 3D con import dinámico.
import dynamic from "next/dynamic";
import { useSyncExternalStore } from "react";

import { fechaCorta, num } from "@/lib/formato";

import type { DatosPlanta } from "./tipos";

export interface ModoPlanta {
  grabacion: boolean;
  formato: "libre" | "4x5" | "1x1";
  movimientoReducido: boolean;
  bajaPotencia: boolean;
  webgl: boolean;
}

const Escena = dynamic(() => import("./escena"), {
  ssr: false,
  loading: () => <p className="grid h-full min-h-[60vh] place-items-center text-sm text-tinta-3">Cargando la escena 3D…</p>,
});

function leerModo(): ModoPlanta {
  const q = new URLSearchParams(window.location.search);
  const f = q.get("formato");
  const canvas = document.createElement("canvas");
  const nav = navigator as Navigator & { deviceMemory?: number };
  return {
    grabacion: q.get("record") === "1",
    formato: f === "4x5" || f === "1x1" ? f : "libre",
    movimientoReducido: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    bajaPotencia: (nav.hardwareConcurrency ?? 8) <= 4 || (nav.deviceMemory ?? 8) <= 4
      || window.matchMedia("(max-width: 640px)").matches,
    webgl: !!(canvas.getContext("webgl2") || canvas.getContext("webgl")),
  };
}
let cache: ModoPlanta | null = null;
const suscribir = () => () => {};

/** Sin WebGL: mismos datos, en tarjetas. */
function SinWebGL({ datos }: { datos: DatosPlanta }) {
  return (
    <div className="grid h-full min-h-[60vh] place-items-center p-6 text-center text-sm text-tinta-2">
      <div className="max-w-xl">
        <p>Tu navegador no tiene WebGL activado, así que no podemos dibujar la escena 3D. Estos son los datos que la mueven:</p>
        <ul className="mt-4 grid grid-cols-2 gap-2 text-left">
          {Object.values(datos).map((i) => (
            <li key={i.key} className="tarjeta p-3">
              <p className="text-xs text-tinta-3">{i.nombre}</p>
              <p className="cifra font-semibold text-tinta">{i.valor == null ? "no disponible" : num(i.valor, 1)}</p>
              <p className="text-[11px] text-tinta-3">{i.unidad}{i.fecha ? ` · ${fechaCorta(i.fecha)}` : ""}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function Planta({ datos }: { datos: DatosPlanta }) {
  const modo = useSyncExternalStore(suscribir, () => (cache ??= leerModo()), () => null);
  if (!modo) return <p className="grid h-full min-h-[60vh] place-items-center text-sm text-tinta-3">Cargando la escena 3D…</p>;
  if (!modo.webgl) return <SinWebGL datos={datos} />;
  return <Escena datos={datos} modo={modo} />;
}
