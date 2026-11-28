"use client";

// Punto de entrada de /mapa: decide el modo (normal, grabación, reducido, sin WebGL) y carga
// la escena pesada (MapLibre + deck.gl) con import dinámico, solo en el navegador.
import dynamic from "next/dynamic";
import Link from "next/link";

import { MiniRed } from "../mapas";
import { type ModoMapa, useModoMapa } from "../modo-mapa";
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

export type Modo = ModoMapa;

export function MapaAnimado({ datos }: { datos: DatosMapa }) {
  const modo = useModoMapa();
  if (!modo) return <Aviso texto="Cargando el mapa…" />;
  if (!modo.webgl) {
    return (
      <Aviso texto="Tu navegador no tiene WebGL activado, así que mostramos una versión fija de la red.">
        <div className="mx-auto mt-4 max-w-2xl"><MiniRed hh={datos.hubs.find((h) => h.nombre === "Henry Hub")} /></div>
        <Link href="/analisis/" className="mt-3 inline-block text-[#5fb3e6] underline">Ver los mapas de Análisis</Link>
      </Aviso>
    );
  }
  return <Escena datos={datos} modo={modo} />;
}
