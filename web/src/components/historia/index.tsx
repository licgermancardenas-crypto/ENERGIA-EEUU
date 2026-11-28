"use client";

// Scrollytelling "Del pozo al surtidor" (portada). Scroll normal del navegador: cada etapa es un
// bloque de texto; un IntersectionObserver marca la activa y el lienzo fijo (sticky) cambia foto,
// encuadre del mapa y dato. Nada se carga hasta que la sección está cerca del viewport.
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import type { EtapaHistoria } from "@/lib/historia";

import { Conteo } from "../mapa-animado/conteo";
import { useModoMapa } from "../modo-mapa";
// el mapa (y su CSS) se baja recién cuando la sección está cerca: no pesa en la portada
const MapaHistoria = dynamic(() => import("./mapa").then((m) => m.MapaHistoria), { ssr: false });

export interface CreditoImagen { titulo: string; pagina: string; autor: string; licencia: string; licencia_url: string }
export interface Placeholder { blur: string; anchos: number[] }

export function Historia({ etapas, creditos, placeholders }:
  { etapas: EtapaHistoria[]; creditos: Record<string, CreditoImagen>; placeholders: Record<string, Placeholder> }) {
  const modo = useModoMapa();
  const animar = !!modo && !modo.movimientoReducido;
  const seccion = useRef<HTMLElement>(null);
  const pasos = useRef<(HTMLElement | null)[]>([]);
  const [cerca, setCerca] = useState(false);
  const [activa, setActiva] = useState(0);

  // carga diferida: fotos y mapa recién cuando la sección está a ~1 pantalla
  useEffect(() => {
    const s = seccion.current;
    if (!s) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setCerca(true); io.disconnect(); } },
      { rootMargin: "800px 0px" });
    io.observe(s);
    return () => io.disconnect();
  }, []);

  // etapa activa: la que cruza la mitad de la pantalla
  useEffect(() => {
    const io = new IntersectionObserver((entradas) => {
      for (const e of entradas) if (e.isIntersecting) setActiva(Number((e.target as HTMLElement).dataset.i));
    }, { rootMargin: "-45% 0px -45% 0px" });
    pasos.current.forEach((p) => p && io.observe(p));
    return () => io.disconnect();
  }, [etapas.length]);

  const irA = useCallback((i: number) => {
    pasos.current[i]?.scrollIntoView({ behavior: animar ? "smooth" : "auto", block: "center" });
  }, [animar]);

  const e = etapas[activa];
  return (
    <section ref={seccion} id="historia" aria-labelledby="historia-titulo" className="relative bg-[#05080f] text-white">
      <h2 id="historia-titulo" className="sr-only">Del pozo al surtidor</h2>

      <div className="relative mx-auto grid max-w-[1280px] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
        {/* lienzo fijo: arriba en celular (45 % del alto), a la derecha en escritorio */}
        <div className="sticky top-0 z-10 h-[45vh] lg:order-2 lg:h-screen">
          <div className="relative h-full overflow-hidden">
            {cerca && etapas.map((et, i) => (
              <Foto key={et.id} clave={et.imagen.clave} alt={et.imagen.alt} visible={i === activa}
                animar={animar} ph={placeholders[et.imagen.clave]} />
            ))}
            <div className="absolute inset-0 bg-gradient-to-t from-[#05080f] via-[#05080f]/55 to-[#05080f]/35" aria-hidden />
            {cerca && (
              <div className="absolute bottom-[22%] right-4 h-[42%] w-[58%] overflow-hidden rounded-xl border border-white/20 shadow-2xl max-lg:bottom-3 max-lg:right-3 max-lg:h-[48%] max-lg:w-[46%]">
                <MapaHistoria etapa={e} animar={animar} />
              </div>
            )}
            <div className="absolute left-5 top-5 max-w-[60%] lg:left-8 lg:top-10" aria-live="polite">
              <p className="text-[11px] font-semibold tracking-wide text-[#f08a4b]">ETAPA {e.numero} DE {etapas.length}</p>
              <p className="text-2xl font-semibold lg:text-4xl">{e.titulo}</p>
              {e.dato && (
                <div className="mt-2 lg:mt-4">
                  <p className="cifra text-3xl font-semibold lg:text-6xl">
                    <Conteo key={`${e.id}-${activa}`} valor={e.dato.valor} decimales={e.dato.decimales} animar={animar} prefijo={e.dato.prefijo} />
                  </p>
                  <p className="text-xs text-[#e9dccf] lg:text-sm">{e.dato.unidad} · {e.dato.fecha}</p>
                  <p className="text-[10px] text-[#b9a999] lg:text-xs">Fuente: {e.dato.fuente}</p>
                </div>
              )}
            </div>
            {cerca && creditos[e.imagen.clave] && (
              <p className="absolute bottom-1 left-2 max-w-[50%] text-[9px] text-white/70 lg:text-[10px]">
                Imagen ilustrativa · {creditos[e.imagen.clave].autor} · {creditos[e.imagen.clave].licencia} (Wikimedia Commons)
              </p>
            )}
          </div>
        </div>

        {/* columna de texto: scroll normal */}
        <div className="relative z-0 px-5 lg:order-1 lg:px-10">
          {etapas.map((et, i) => (
            <article key={et.id} ref={(el) => { pasos.current[i] = el; }} data-i={i}
              className="flex min-h-[70vh] flex-col justify-center py-16 lg:min-h-screen" aria-label={`Etapa ${et.numero}: ${et.titulo}`}>
              <p className="text-[11px] font-semibold tracking-wide text-[#f08a4b]">{et.numero} · {et.titulo.toUpperCase()}</p>
              <p className="mt-3 text-lg leading-relaxed text-[#f3e9df] lg:text-xl">{et.texto}</p>
              {et.extra.map((x) => <p key={x} className="mt-3 text-sm text-[#d8c7b6]">{x}</p>)}
              {!et.dato && <p className="mt-3 text-sm text-[#b9a999]">Esta etapa no tiene una cifra publicada que podamos mostrar.</p>}
              {et.nota && <p className="mt-3 text-xs text-[#b9a999]">{et.nota}</p>}
            </article>
          ))}
          <div className="pb-24 text-sm text-[#d8c7b6]">
            <Link href="/resumen/" className="inline-block rounded-lg bg-[#1f6fd1] px-5 py-2.5 font-semibold text-white ring-1 ring-[#5fb3e6] hover:bg-[#2f7ddb]">
              Ir al tablero →
            </Link>
          </div>
        </div>
      </div>

      {/* barra de progreso lateral (teclado: Tab + Enter) */}
      <nav aria-label="Etapas de la historia" className="pointer-events-none sticky bottom-0 z-20 flex justify-center pb-3 lg:fixed lg:bottom-auto lg:left-3 lg:top-1/2 lg:block lg:-translate-y-1/2 lg:pb-0">
        <ol className="pointer-events-auto flex gap-2 rounded-full bg-[#05080f]/80 px-3 py-2 lg:flex-col lg:px-2 lg:py-3">
          {etapas.map((et, i) => (
            <li key={et.id}>
              <button type="button" onClick={() => irA(i)} aria-current={i === activa ? "step" : undefined}
                aria-label={`Ir a la etapa ${et.numero}: ${et.titulo}`}
                className={`block h-3 w-3 rounded-full border-2 transition-colors ${i === activa ? "border-[#f08a4b] bg-[#f08a4b]" : "border-white/60 bg-transparent hover:border-white"}`} />
            </li>
          ))}
        </ol>
      </nav>
      <Link href="/resumen/" className="fixed right-3 top-3 z-30 rounded-full bg-[#05080f]/85 px-3 py-1.5 text-xs font-semibold text-white ring-1 ring-white/30 hover:ring-white">
        Saltar al tablero
      </Link>
    </section>
  );
}

function Foto({ clave, alt, visible, animar, ph }:
  { clave: string; alt: string; visible: boolean; animar: boolean; ph?: Placeholder }) {
  const anchos = ph?.anchos ?? [640, 1280, 1920];
  const set = (fmt: string) => anchos.map((w) => `/historia/${clave}-${w}.${fmt} ${w}w`).join(", ");
  return (
    <picture>
      <source type="image/avif" srcSet={set("avif")} sizes="(min-width: 1024px) 58vw, 100vw" />
      <source type="image/webp" srcSet={set("webp")} sizes="(min-width: 1024px) 58vw, 100vw" />
      {/* export estático: next/image no optimiza; las variantes AVIF/WebP ya están generadas */}
      <img src={`/historia/${clave}-${anchos[0]}.webp`} alt={alt} loading="lazy" decoding="async"
        style={{ backgroundImage: ph ? `url(${ph.blur})` : undefined, backgroundSize: "cover" }}
        className={`absolute inset-0 h-full w-full object-cover ${animar ? "transition-opacity duration-700" : ""} ${visible ? "opacity-100" : "opacity-0"}`} />
    </picture>
  );
}
