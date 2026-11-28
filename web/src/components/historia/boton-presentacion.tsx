"use client";

// B4: lanza el modo presentación de la historia desde el hero de la portada.
import { FLAGS } from "@/lib/flags";

export function BotonPresentacion() {
  if (!FLAGS.modoPresentacion) return null;
  return (
    <button type="button" data-ocultar-en-presentacion onClick={() => window.dispatchEvent(new Event("historia:presentar"))}
      className="mx-auto rounded-xl px-4 py-2 text-sm font-semibold text-[#c9d4e5] ring-1 ring-white/30 hover:text-white hover:ring-white max-sm:hidden">
      Modo presentación ▶
    </button>
  );
}
