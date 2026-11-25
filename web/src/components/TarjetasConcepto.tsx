"use client";

import { useState } from "react";

import type { Datos, Sector } from "@/lib/tipos";
import { fechaSegunFrecuencia, UNIDADES, valor } from "@/lib/formato";

interface Concepto {
  termino: string;
  bajada: string;
  explicacion: string;
  serie?: string; // si existe, el frente muestra su último valor (de Gold)
}

const CONCEPTOS: Record<Sector, Concepto[]> = {
  petroleo: [
    {
      termino: "WTI", bajada: "West Texas Intermediate", serie: "RWTC_D",
      explicacion: "Crudo liviano y de bajo azufre que se entrega en Cushing, Oklahoma. Es el precio de referencia del petróleo en Estados Unidos.",
    },
    {
      termino: "Brent", bajada: "Crudo del Mar del Norte", serie: "RBRTE_D",
      explicacion: "Mezcla de crudos europeos que funciona como referencia internacional: con él se fija el precio de buena parte del petróleo que se comercia por mar.",
    },
    {
      termino: "SPR", bajada: "Reserva Estratégica", serie: "WCSSTUS1_W",
      explicacion: "Crudo que el Gobierno federal guarda en cavernas de sal en Texas y Luisiana para usar ante cortes de suministro. Se cuenta aparte del stock comercial.",
    },
    {
      termino: "Destilados", bajada: "Diésel y gasoil", serie: "WDISTUS1_W",
      explicacion: "Combustibles medios que salen de la refinería: diésel para transporte y gasoil para calefacción. Su stock anticipa tensiones en camiones, campo e invierno.",
    },
    {
      termino: "Barriles por día", bajada: "Cómo se mide la producción", serie: "MCRFPUS2_M",
      explicacion: "Un barril equivale a 42 galones (unos 159 litros). La EIA publica la producción de crudo en miles de barriles por día, promediando cada mes.",
    },
  ],
  gas: [
    {
      termino: "Henry Hub", bajada: "Precio de referencia", serie: "RNGWHHD_D",
      explicacion: "Nodo de gasoductos en Erath, Luisiana. Su precio spot es la referencia del gas natural en EE. UU. y el punto de entrega del contrato de futuros de NYMEX.",
    },
    {
      termino: "MMBtu", bajada: "Millón de BTU",
      explicacion: "La BTU (unidad térmica británica) mide energía. El gas se cotiza por su contenido energético, no por volumen: en dólares por millón de BTU.",
    },
    {
      termino: "Bcf", bajada: "Almacenamiento subterráneo", serie: "NW2_EPG0_SWO_R48_BCF_W",
      explicacion: "Miles de millones de pies cúbicos. El gas se inyecta en yacimientos agotados, acuíferos y cavernas de sal en los meses templados y se retira en invierno.",
    },
    {
      termino: "Gas seco", bajada: "Producción lista para consumo", serie: "N9070US2_M",
      explicacion: "Es el gas comercializado menos los líquidos (etano, propano, butano) que se separan en plantas de procesamiento. Es el que llega por gasoducto a los usuarios.",
    },
    {
      termino: "Generación eléctrica", bajada: "Uso del gas en centrales", serie: "N3045US2_M",
      explicacion: "Gas que queman las centrales para producir electricidad. Su demanda pega picos en verano, cuando el aire acondicionado empuja el consumo eléctrico.",
    },
  ],
};

function Tarjeta({ c, datos }: { c: Concepto; datos: Datos }) {
  const [girada, setGirada] = useState(false);
  const s = c.serie ? datos.series[c.serie] : undefined;
  const u = c.serie ? datos.ultimo[c.serie] : undefined;

  return (
    <li
      className="tarjeta h-56 cursor-pointer list-none"
      data-girada={girada}
      tabIndex={0}
      aria-label={`${c.termino}: ${c.bajada}`}
      onClick={() => setGirada((g) => !g)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setGirada((g) => !g);
        }
      }}
    >
      <div className="tarjeta-giro">
        <div className="cara cara-frente flex flex-col justify-between rounded-xl border border-linea bg-superficie p-5">
          <div>
            <p className="font-display text-2xl font-semibold">{c.termino}</p>
            <p className="mt-1 text-sm text-tinta-2">{c.bajada}</p>
          </div>
          {s && u ? (
            <p className="text-sm">
              <span className="cifra block text-xl font-semibold">{valor(u.valor, s.unidad)}</span>
              <span className="text-tinta-2">
                {UNIDADES[s.unidad]?.corta ?? s.unidad} · {fechaSegunFrecuencia(u.fecha, s.frecuencia)}
              </span>
            </p>
          ) : (
            <p className="text-sm text-tinta-2">Unidad de medida</p>
          )}
          <span aria-hidden className="absolute right-4 top-4 text-xs text-tinta-2">↻</span>
        </div>
        <div
          className="cara cara-dorso rounded-xl border p-5 text-[15px] leading-relaxed"
          style={{ borderColor: "var(--acento)", background: "var(--superficie-2)" }}
        >
          <p className="font-medium">{c.termino}</p>
          <p className="mt-2 text-tinta">{c.explicacion}</p>
        </div>
      </div>
    </li>
  );
}

export function TarjetasConcepto({ sector, datos }: { sector: Sector; datos: Datos }) {
  return (
    <section aria-labelledby="t-conceptos">
      <h2 id="t-conceptos" className="font-display text-2xl font-semibold">Glosario rápido</h2>
      <p className="mt-1 text-sm text-tinta-2">
        Pasá el mouse, tocá o enfocá con el teclado cada tarjeta para ver qué significa.
      </p>
      <ul className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {CONCEPTOS[sector].map((c) => (
          <Tarjeta key={c.termino} c={c} datos={datos} />
        ))}
      </ul>
    </section>
  );
}
