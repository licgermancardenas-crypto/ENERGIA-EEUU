// Piezas comunes de todas las páginas, con el mismo diseño que el informe de Power BI.
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { estadoDatos, type Indicadores } from "@/lib/indicadores";

/** Ícono del set propio (public/icons), coloreado con CSS mask. */
export function Icono({ nombre, color = "currentColor", tam = 20, titulo }:
  { nombre: string; color?: string; tam?: number; titulo?: string }) {
  const estilo: CSSProperties = {
    width: tam, height: tam, backgroundColor: color, display: "inline-block", flex: "none",
    WebkitMask: `url(/icons/${nombre}.svg) center / contain no-repeat`,
    mask: `url(/icons/${nombre}.svg) center / contain no-repeat`,
  };
  return <span role={titulo ? "img" : undefined} aria-label={titulo} aria-hidden={!titulo}
    style={estilo} />;
}

export const PAGINAS = [
  { ruta: "/resumen/", menu: "Resumen", icono: "pulso" },
  { ruta: "/petroleo/", menu: "Petróleo", icono: "gota" },
  { ruta: "/gas/", menu: "Gas", icono: "llama" },
  { ruta: "/rezago/", menu: "Rezago", icono: "reloj" },
  { ruta: "/calidad/", menu: "Calidad", icono: "escudo-check" },
  { ruta: "/analisis/", menu: "Análisis", icono: "capas" },
  { ruta: "/mapa/", menu: "Mapa gas", icono: "mapa-pin" },
  { ruta: "/petroleo-red/", menu: "Mapa petróleo", icono: "gota" },
  { ruta: "/planta/", menu: "Planta", icono: "torre" },
] as const;

export type Menu = (typeof PAGINAS)[number]["menu"];

export function Encabezado({ activa, titulo, bajada, ind }:
  { activa: Menu; titulo: string; bajada: string; ind: Indicadores }) {
  const pagina = PAGINAS.find((p) => p.menu === activa)!;
  const estado = estadoDatos(ind);
  return (
    <header className="textura bg-navy text-white">
      <div className="mx-auto flex max-w-[1280px] flex-col gap-4 px-6 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold tracking-wide text-[#9db7dd]">
            <Link href="/" className="hover:text-white">PULSO ENERGÉTICO DE EE. UU.</Link>
            {"  ·  "}{activa.toUpperCase()}
          </p>
          <h1 className="mt-1 flex items-center gap-3 text-2xl font-semibold leading-tight sm:text-[26px]">
            <Icono nombre={pagina.icono} color="#fff" tam={26} />
            {titulo}
          </h1>
          <p className="mt-1 text-[13px] text-[#c9d4e5]">{bajada}</p>
        </div>
        <div className="flex flex-col gap-2 lg:w-[980px]">
          <nav aria-label="Páginas del tablero" className="grid grid-cols-3 gap-1.5 sm:grid-cols-5 xl:grid-cols-9">
            {PAGINAS.map((p) => {
              const on = p.menu === activa;
              return (
                <Link key={p.ruta} href={p.ruta} aria-current={on ? "page" : undefined}
                  className={`flex h-9 items-center justify-center gap-1.5 rounded-lg px-2 text-[13px] font-semibold transition-colors ${on
                    ? "bg-gas text-white ring-1 ring-[#9db7dd]"
                    : "bg-navy-2 text-[#c9d4e5] hover:bg-[#23446f] hover:text-white"}`}>
                  <Icono nombre={p.icono} color={on ? "#fff" : "#c9d4e5"} tam={15} />
                  {p.menu}
                </Link>
              );
            })}
          </nav>
          <p className={`rounded-full border border-[#9db7dd]/60 px-4 py-1 text-center text-[13px] ${estado.ok ? "text-[#8fd3a8]" : "text-[#f0a347]"}`}>
            ● {estado.texto}
          </p>
        </div>
      </div>
    </header>
  );
}

export function Pie({ geo = false }: { geo?: boolean }) {
  return (
    <footer className="mx-auto max-w-[1280px] px-6 pb-6 pt-2 text-xs text-tinta-3">
      {geo
        ? "Fuente: EIA (API v2 y capas geoespaciales vía HIFLD/DHS; copias públicas) · U.S. Census · Autor: Germán Cárdenas · La EIA no garantiza la exactitud de estos datos"
        : "Fuente: U.S. Energy Information Administration (EIA) · API v2 · Autor: Germán Cárdenas"}
      {" · "}
      <a className="underline underline-offset-2 hover:text-tinta" href="https://github.com/licgermancardenas-crypto/ENERGIA-EEUU">Código</a>
    </footer>
  );
}

export function Pagina({ children, ...enc }:
  { children: ReactNode; activa: Menu; titulo: string; bajada: string; ind: Indicadores;
    geo?: boolean }) {
  return (
    <>
      <Encabezado {...enc} />
      <main className="mx-auto grid max-w-[1280px] gap-4 px-6 py-5">{children}</main>
      <Pie geo={enc.geo} />
    </>
  );
}

/** Contenedor blanco con título, subtítulo y un ícono opcional arriba a la derecha. */
export function Panel({ titulo, nota, icono, iconoColor, children, className = "", accion }:
  { titulo: string; nota?: string; icono?: string; iconoColor?: string; children: ReactNode;
    className?: string; accion?: ReactNode }) {
  return (
    <section className={`tarjeta flex min-w-0 flex-col p-4 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-tinta">{titulo}</h2>
          {nota && <p className="mt-0.5 text-xs text-tinta-3">{nota}</p>}
        </div>
        <div className="flex items-center gap-3">
          {accion}
          {icono && <Icono nombre={icono} color={iconoColor} tam={22} />}
        </div>
      </div>
      <div className="mt-3 min-h-0 flex-1">{children}</div>
    </section>
  );
}

/** Tarjeta KPI: etiqueta en mayúsculas del color de la familia, nota gris y valor grande. */
export function Kpi({ etiqueta, nota, valor, color, icono, iconoColor, grande = true, extra }:
  { etiqueta: string; nota: string; valor: string; color: string; icono?: string;
    iconoColor?: string; grande?: boolean; extra?: ReactNode }) {
  return (
    <div className="tarjeta flex min-w-0 flex-col px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-semibold tracking-wide" style={{ color }}>{etiqueta.toUpperCase()}</p>
          <p className="truncate text-xs text-tinta-3">{nota}</p>
        </div>
        {icono && <Icono nombre={icono} color={iconoColor ?? color} tam={22} />}
      </div>
      <div className="mt-2 flex items-center justify-center gap-3">
        {extra}
        <p className={`cifra font-semibold text-tinta ${grande ? "text-[32px]" : "text-2xl"}`}>{valor}</p>
      </div>
    </div>
  );
}

export function Seccion({ texto, icono, color }: { texto: string; icono: string; color: string }) {
  return (
    <h2 className="flex items-center gap-2 text-sm font-semibold tracking-wide" style={{ color }}>
      <Icono nombre={icono} color={color} tam={18} /> {texto}
    </h2>
  );
}
