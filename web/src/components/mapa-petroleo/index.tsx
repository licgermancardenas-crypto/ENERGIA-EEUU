"use client";

// Punto de entrada de /petroleo-red: modo de visualización y carga diferida de la escena
// (MapLibre + deck.gl), solo en el navegador. Mismo esquema que el mapa de gas.
import dynamic from "next/dynamic";

import { useModoMapa } from "../modo-mapa";
import type { DatosMapaPetroleo } from "./tipos";

function Aviso({ texto }: { texto: string }) {
  return <p className="grid h-full min-h-[60vh] place-items-center bg-[#05080f] p-6 text-center text-sm text-[#e9dccf]">{texto}</p>;
}

const Escena = dynamic(() => import("./escena"), { ssr: false, loading: () => <Aviso texto="Cargando el mapa…" /> });

export function MapaPetroleo({ datos }: { datos: DatosMapaPetroleo }) {
  const modo = useModoMapa();
  if (!modo) return <Aviso texto="Cargando el mapa…" />;
  if (!modo.webgl) return <Aviso texto="Tu navegador no tiene WebGL activado: no podemos dibujar el mapa. Los mismos datos están en las páginas Petróleo y Calidad." />;
  return <Escena datos={datos} modo={modo} />;
}
