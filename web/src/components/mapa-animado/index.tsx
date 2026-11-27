"use client";

// Punto de entrada de /mapa: decide el modo (normal, grabación, reducido, sin WebGL) y carga
// la escena pesada (MapLibre + deck.gl) con import dinámico, solo en el navegador.
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSyncExternalStore } from "react";

import { MiniRed } from "../mapas";
import type { DatosMapa } from "./tipos";

const Escena = dynamic(() => import("./escena"), {
  ssr: false,
  loading: () => <Aviso texto="Cargando el mapa…" />,
});

function Aviso({ texto, children }: { texto: string; children?: React.ReactNode }) {
  return (
    <div className="grid h-full min-h-[60vh] place-items-center bg-[#05080f] p-6 text-center text-sm text-[#c9d4e5]">
      <div>
        <p>{texto}</p>
        {children}
      </div>
    </div>
  );
}

export interface Modo {
  grabacion: boolean;
  formato: "libre" | "4x5" | "1x1";
  movimientoReducido: boolean;
  bajaPotencia: boolean;
  webgl: boolean;
}

function leerModo(): Modo {
  const q = new URLSearchParams(window.location.search);
  const f = q.get("formato");
  const canvas = document.createElement("canvas");
  const webgl = !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  const nav = navigator as Navigator & { deviceMemory?: number };
  return {
    grabacion: q.get("record") === "1",
    formato: f === "4x5" || f === "1x1" ? f : "libre",
    movimientoReducido: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    // equipos chicos: menos capas animadas
    bajaPotencia: (nav.hardwareConcurrency ?? 8) <= 4 || (nav.deviceMemory ?? 8) <= 4
      || window.matchMedia("(max-width: 640px)").matches,
    webgl,
  };
}

let modoCache: Modo | null = null;
const suscribir = () => () => {};
const modoCliente = () => (modoCache ??= leerModo());
const modoServidor = () => null;

export function MapaAnimado({ datos }: { datos: DatosMapa }) {
  const modo = useSyncExternalStore(suscribir, modoCliente, modoServidor);
  if (!modo) return <Aviso texto="Cargando el mapa…" />;
  if (!modo.webgl) {
    return (
      <Aviso texto="Tu navegador no tiene WebGL activado, así que mostramos una versión fija de la red.">
        <div className="mx-auto mt-4 max-w-2xl"><MiniRed hh={datos.hubs.find((h) => h.nombre === "Henry Hub")} /></div>
        <Link href="/red/" className="mt-3 inline-block text-[#5fb3e6] underline">Ver la página Red</Link>
      </Aviso>
    );
  }
  return <Escena datos={datos} modo={modo} />;
}
