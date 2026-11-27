import Link from "next/link";

import { MiniRedHud, TendenciaHud } from "@/components/portada";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { num } from "@/lib/formato";
import { estadoDatos, indicadores } from "@/lib/indicadores";

function Hud({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="hud px-4 py-3">
      <p className="text-[11px] font-semibold tracking-wide text-cian">{etiqueta.toUpperCase()}</p>
      <p className="cifra mt-1 text-3xl font-semibold text-white">{valor}</p>
    </div>
  );
}

export default function Portada() {
  const d = cargarDatos();
  const g = cargarGeo();
  const i = indicadores(d);
  const estado = estadoDatos(i);
  const v = (x: number | null, dec = 0) => (x == null ? "—" : num(x, dec));
  return (
    <div className="relative min-h-screen overflow-hidden bg-navy text-white">
      {/* Foto: "Oil Refinery" (Porvoo), Carlos "Grury" Santos, Unsplash License */}
      <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: "url(/portada.jpg)" }} aria-hidden />
      <div className="relative mx-auto flex min-h-screen max-w-[1280px] flex-col gap-6 px-6 py-8 lg:px-12">
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div>
            <p className="text-xs font-semibold tracking-wide text-cian">PULSO ENERGÉTICO DE EE. UU.</p>
            <h1 className="mt-2 text-4xl font-semibold leading-tight sm:text-5xl">El pulso del petróleo<br />y el gas natural</h1>
            <p className="mt-3 text-sm text-[#c9d4e5]">Datos oficiales de la EIA · se actualizan a diario · Autor: Germán Cárdenas</p>
            <div className="mt-6 grid max-w-[460px] grid-cols-2 gap-3">
              <Hud etiqueta="WTI · US$/barril" valor={v(i.wti, 2)} />
              <Hud etiqueta="Henry Hub · US$/MMBtu" valor={v(i.hh, 2)} />
              <Hud etiqueta="Crudo comercial · miles bbl" valor={v(i.crudo)} />
              <Hud etiqueta="Gas almacenado · Bcf" valor={v(i.gas)} />
            </div>
          </div>
          <div className="grid content-start gap-3">
            <div className="hud px-4 py-3">
              <p className="text-[11px] font-semibold tracking-wide text-cian">ESTADO DE LOS DATOS</p>
              <p className={`mt-1 text-sm ${estado.ok ? "text-[#8fd3a8]" : "text-[#f0a347]"}`}>● {estado.texto}</p>
            </div>
            <Hud etiqueta="Fuentes al día" valor={`${i.fuentesAlDia} de ${i.fuentesTotal}`} />
          </div>
        </div>
        <div className="mt-auto grid items-end gap-4 lg:grid-cols-[1fr_auto_380px]">
          <div className="hud p-4">
            <p className="text-[11px] font-semibold tracking-wide text-cian">WTI · ÚLTIMOS 12 MESES</p>
            <p className="text-xs text-[#9db7dd]">US$ por barril</p>
            <TendenciaHud datos={d.hechos.RWTC_D} />
          </div>
          <Link href="/resumen/"
            className="mx-auto rounded-xl bg-gas px-8 py-3 text-base font-semibold text-white ring-1 ring-cian transition-colors hover:bg-[#2f7ddb]">
            Entrar al tablero →
          </Link>
          <div className="hud p-4">
            <p className="text-[11px] font-semibold tracking-wide text-cian">RED DE GASODUCTOS</p>
            <p className="text-xs text-[#9db7dd]">capa de la EIA · Henry Hub en naranja</p>
            <MiniRedHud hh={g.puntos.hubs.find((h) => h.nombre === "Henry Hub")} />
          </div>
        </div>
        <p className="text-[11px] text-[#9db7dd]">
          Fuente: EIA (API v2 y capas geoespaciales vía HIFLD/DHS; copias públicas) · U.S. Census · Autor: Germán Cárdenas ·
          La EIA no garantiza la exactitud de estos datos · Foto: Carlos &quot;Grury&quot; Santos (Unsplash)
        </p>
      </div>
    </div>
  );
}
