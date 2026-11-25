"use client";

import { useSyncExternalStore } from "react";

import type { Datos, Sector } from "@/lib/tipos";
import { fechaCorta } from "@/lib/formato";

import { Banner } from "./Banner";
import { BarrasSector } from "./BarrasSector";
import { FrasesClave } from "./FrasesClave";
import { GraficoLineas } from "./GraficoLineas";
import { PanelFrescura } from "./PanelFrescura";
import { SeccionRezago } from "./SeccionRezago";
import { SelectorSector } from "./SelectorSector";
import { TarjetasConcepto } from "./TarjetasConcepto";

const CONFIG: Record<Sector, {
  diario: { titulo: string; series: string[] };
  semanal: { titulo: string; series: string[]; nota: string };
}> = {
  petroleo: {
    diario: { titulo: "Precio spot diario del crudo", series: ["RWTC_D", "RBRTE_D"] },
    semanal: {
      titulo: "Inventarios semanales de crudo",
      series: ["WCESTUS1_W", "WCSSTUS1_W"],
      nota: "Stock comercial y Reserva Estratégica, en miles de barriles.",
    },
  },
  gas: {
    diario: { titulo: "Precio spot diario del gas natural", series: ["RNGWHHD_D"] },
    semanal: {
      titulo: "Gas en almacenamiento subterráneo",
      series: ["NW2_EPG0_SWO_R48_BCF_W"],
      nota: "Total de los 48 estados contiguos (Lower 48), en Bcf.",
    },
  },
};

// El sector vive en el hash de la URL (#petroleo / #gas), así el enlace se puede compartir.
function leerSector(): Sector {
  return window.location.hash === "#gas" ? "gas" : "petroleo";
}

function suscribir(aviso: () => void) {
  window.addEventListener("hashchange", aviso);
  return () => window.removeEventListener("hashchange", aviso);
}

export function Dashboard({ datos }: { datos: Datos }) {
  // El HTML estático sale con petróleo; al hidratar se respeta el hash.
  const sector = useSyncExternalStore<Sector>(suscribir, leerSector, () => "petroleo");

  const cambiar = (s: Sector) => {
    history.replaceState(null, "", `#${s}`);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  };

  const cfg = CONFIG[sector];
  const dest = datos.destacados[sector];

  return (
    <div data-sector={sector} className="min-h-dvh">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-superficie focus:px-3 focus:py-2">
        Saltar al contenido
      </a>

      <header className="border-b border-linea">
        <div className="mx-auto flex max-w-6xl flex-col gap-5 px-5 pb-6 pt-8 sm:px-8 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-tinta-2">
              Boletín de datos · EIA · actualizado al {fechaCorta(datos.meta.calculado_al)}
            </p>
            <h1 className="mt-2 font-display text-4xl font-semibold leading-tight sm:text-5xl">
              Pulso Energético <span className="whitespace-nowrap">de EE. UU.</span>
            </h1>
            <p className="mt-2 max-w-xl text-tinta-2">
              Cómo están hoy el petróleo y el gas natural: precios, inventarios, producción y consumo,
              y cuánto tarda la producción en reaccionar al precio.
            </p>
          </div>
          <SelectorSector sector={sector} onCambiar={cambiar} />
        </div>
        <div aria-hidden className="h-1 w-full" style={{ background: "var(--acento)" }} />
      </header>

      <main id="contenido" className="mx-auto max-w-6xl space-y-12 px-5 py-10 sm:px-8">
        <h2 className="sr-only">{sector === "petroleo" ? "Petróleo" : "Gas natural"}</h2>
        <Banner datos={datos} banner={dest.banner} />
        <FrasesClave frases={dest.frases} />
        <TarjetasConcepto sector={sector} datos={datos} />

        <div className="grid gap-8 lg:grid-cols-5">
          <div className="min-w-0 lg:col-span-3">
            <GraficoLineas
              key={`d-${sector}`}
              titulo={cfg.diario.titulo}
              nota="Precio de cierre por día hábil. Elegí un año o mirá la serie completa."
              series={cfg.diario.series}
              datos={datos}
              filtroAnio
            />
          </div>
          <div className="min-w-0 lg:col-span-2">
            <BarrasSector barras={dest.barras} />
          </div>
        </div>

        <GraficoLineas
          key={`s-${sector}`}
          titulo={cfg.semanal.titulo}
          nota={cfg.semanal.nota}
          series={cfg.semanal.series}
          datos={datos}
        />

        <SeccionRezago rezago={datos.rezago} />
        <PanelFrescura frescura={datos.frescura} meta={datos.meta} />
      </main>

      <footer className="border-t border-linea">
        <div className="mx-auto max-w-6xl space-y-2 px-5 py-8 text-sm text-tinta-2 sm:px-8">
          <p>
            Fuente: <a className="underline underline-offset-2" href={datos.meta.fuente_url}>{datos.meta.fuente}</a>.
            Todas las cifras salen de la capa Gold del pipeline (Bronze → Silver → Gold), generada el{" "}
            {fechaCorta(datos.meta.gold_generado_utc)}.
          </p>
          <p>
            Proyecto de portfolio de German Cardenas ·{" "}
            <a className="underline underline-offset-2" href="https://github.com/licgermancardenas-crypto/ENERGIA-EEUU">
              código en GitHub
            </a>
            . Inspirado en el trabajo de Edgar Saico Zea y Vicente Antonio Juan Magallanes.
          </p>
        </div>
      </footer>
    </div>
  );
}
