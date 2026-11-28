"use client";

// B3: foto del hero con parallax suave (máx. 20 px). Solo transform: no mueve el diseño (CLS 0).
// Apagado con prefers-reduced-motion, en pantallas de menos de 768 px o con FLAGS.parallax = false.
import { useEffect, useRef } from "react";

import { FLAGS } from "@/lib/flags";

const MAX_PX = 20;

export function FondoParallax({ src }: { src: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !FLAGS.parallax) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || window.innerWidth < 768) return;
    let raf = 0;
    const mover = () => {
      raf = 0;
      el.style.transform = `translate3d(0, ${Math.min(MAX_PX, window.scrollY * 0.05).toFixed(1)}px, 0)`;
    };
    const alScroll = () => { if (!raf) raf = requestAnimationFrame(mover); };
    window.addEventListener("scroll", alScroll, { passive: true });
    return () => { window.removeEventListener("scroll", alScroll); cancelAnimationFrame(raf); };
  }, []);
  // se extiende 20 px arriba y abajo para que el corrimiento no deje bordes vacíos
  return <div ref={ref} aria-hidden className="absolute inset-x-0 -bottom-5 -top-5 bg-cover bg-center will-change-transform"
    style={{ backgroundImage: `url(${src})` }} />;
}
