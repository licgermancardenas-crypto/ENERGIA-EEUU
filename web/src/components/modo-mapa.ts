"use client";

// Modo de visualización de los mapas (movimiento reducido, baja potencia, WebGL, grabación).
// Archivo liviano: lo usan los puntos de entrada de las páginas, que NO cargan deck.gl.
import { useSyncExternalStore } from "react";

export interface ModoMapa {
  grabacion: boolean;
  formato: "libre" | "4x5" | "1x1";
  movimientoReducido: boolean;
  bajaPotencia: boolean;
  webgl: boolean;
}

function leerModo(): ModoMapa {
  const q = new URLSearchParams(window.location.search);
  const f = q.get("formato");
  const canvas = document.createElement("canvas");
  const nav = navigator as Navigator & { deviceMemory?: number };
  return {
    grabacion: q.get("record") === "1",
    formato: f === "4x5" || f === "1x1" ? f : "libre",
    movimientoReducido: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    // equipos chicos: menos capas animadas
    bajaPotencia: (nav.hardwareConcurrency ?? 8) <= 4 || (nav.deviceMemory ?? 8) <= 4
      || window.matchMedia("(max-width: 640px)").matches,
    webgl: !!(canvas.getContext("webgl2") || canvas.getContext("webgl")),
  };
}

let cache: ModoMapa | null = null;
const suscribir = () => () => {};

/** Modo leído una vez en el navegador; null durante el render del servidor. */
export function useModoMapa(): ModoMapa | null {
  return useSyncExternalStore(suscribir, () => (cache ??= leerModo()), () => null);
}
