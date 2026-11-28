"use client";

// Gráficos del hero cargados después del primer pintado (Recharts y d3 no van en la carga inicial).
// Cada espacio reserva su alto exacto para no mover el diseño (CLS).
import dynamic from "next/dynamic";

export const TendenciaHudDiferida = dynamic(() => import("./portada").then((m) => m.TendenciaHud), {
  ssr: false, loading: () => <div className="h-[150px]" aria-hidden />,
});
export const MiniRedHudDiferida = dynamic(() => import("./portada").then((m) => m.MiniRedHud), {
  ssr: false, loading: () => <div className="aspect-[960/560] w-full" aria-hidden />,
});
