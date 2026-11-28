import { readFileSync } from "node:fs";
import path from "node:path";

import { Encabezado } from "@/components/marco";
import { MapaPetroleo } from "@/components/mapa-petroleo";
import type { DatosMapaPetroleo, MetaPetroleo } from "@/components/mapa-petroleo/tipos";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { indicadores } from "@/lib/indicadores";

export const metadata = { title: "Mapa de petróleo · Pulso Energético de EE. UU." };

export default function MapaDePetroleo() {
  const d = cargarDatos();
  const g = cargarGeo();
  const i = indicadores(d);
  const meta = JSON.parse(readFileSync(path.join(process.cwd(), "public/data/petroleo/meta.json"), "utf-8")) as MetaPetroleo;
  const k = (key: string) => ({ valor: d.ultimo[key]?.valor ?? null, fecha: d.ultimo[key]?.fecha ?? null });
  const datos: DatosMapaPetroleo = {
    meta, wti: k("RWTC_D"), crudo: k("WCESTUS1_W"), utilizacion: k("WPULEUS3_W"), spr: k("WCSSTUS1_W"),
    nombresEstados: Object.fromEntries(g.estados.map((e) => [e.k, e.nombre])),
  };
  return (
    <div className="flex min-h-screen flex-col bg-[#05080f]">
      <Encabezado activa="Mapa petróleo" titulo="La red del petróleo"
        bajada="Oleoductos, Cushing, refinerías, terminales y producción de crudo por estado" ind={i} />
      <main className="relative mx-auto h-[calc(100vh-150px)] min-h-[620px] w-full max-w-[1600px] px-3 py-3 max-lg:h-auto">
        <div className="h-full max-lg:h-[70vh]">
          <MapaPetroleo datos={datos} />
        </div>
      </main>
      <footer className="mx-auto w-full max-w-[1600px] px-4 pb-5 text-xs text-[#b9a999]">
        Fuente: EIA (API v2 y capas geoespaciales; copias públicas), USACE/BTS (NTAD), BOEM, U.S. Census · Mapa base:
        OpenFreeMap, © OpenMapTiles, © colaboradores de OpenStreetMap · Autor: Germán Cárdenas · La EIA no garantiza
        la exactitud de los datos geoespaciales · Los pulsos son una animación ilustrativa, no flujo medido
        {" · "}<a className="underline underline-offset-2 hover:text-white" href="https://github.com/licgermancardenas-crypto/ENERGIA-EEUU">Código</a>
      </footer>
    </div>
  );
}
