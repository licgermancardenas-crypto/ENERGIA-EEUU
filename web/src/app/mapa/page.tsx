import { Encabezado } from "@/components/marco";
import { MapaAnimado } from "@/components/mapa-animado";
import type { DatosMapa } from "@/components/mapa-animado/tipos";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { indicadores } from "@/lib/indicadores";

export const metadata = { title: "Mapa de gas · Pulso Energético de EE. UU." };

export default function Mapa() {
  const d = cargarDatos();
  const g = cargarGeo();
  const i = indicadores(d);
  // gas almacenado de la última semana por región de la EIA (mismas series que la página Gas)
  const gasRegion = Object.fromEntries(["R31", "R32", "R33", "R34", "R35"]
    .map((r) => [r, d.ultimo[`NW2_EPG0_SWO_${r}_BCF_W`]?.valor])
    .filter(([, v]) => v != null)) as Record<string, number>;
  const datos: DatosMapa = {
    estados: g.estados.map(({ k, nombre, km, operadores, region, centro, hh, densidad, pct_gas_red }) =>
      ({ k, nombre, km, operadores, region, centro, hh, densidad, pct_gas_red })),
    hubs: g.puntos.hubs,
    gnl: g.puntos.gnl,
    henryHub: g.henryHub,
    fuentes: g.fuentes,
    precioHH: i.hh,
    fechaHH: d.ultimo.RNGWHHD_D?.fecha ?? null,
    gasRegion,
    gasTotal: i.gas,
    fechaGas: d.ultimo.NW2_EPG0_SWO_R48_BCF_W?.fecha ?? null,
    kmRed: g.validacion.km_red_total,
  };
  return (
    <div className="flex min-h-screen flex-col bg-[#05080f]">
      <Encabezado activa="Mapa gas" titulo="La red de gas en movimiento"
        bajada="Gasoductos, flujos entre estados y almacenamiento, con el Henry Hub como centro" ind={i} />
      <main className="relative mx-auto h-[calc(100vh-150px)] min-h-[620px] w-full max-w-[1600px] px-3 py-3 max-lg:h-auto">
        <div className="h-full max-lg:h-[70vh]">
          <MapaAnimado datos={datos} />
        </div>
      </main>
      <footer className="mx-auto w-full max-w-[1600px] px-4 pb-5 text-xs text-[#9db7dd]">
        Fuente: EIA (API v2, flujos interestatales y capas geoespaciales vía HIFLD/DHS; copias públicas) · U.S. Census ·
        Mapa base: OpenFreeMap, © OpenMapTiles, © colaboradores de OpenStreetMap · Autor: Germán Cárdenas ·
        La EIA no garantiza la exactitud de los datos geoespaciales · Los pulsos son una animación ilustrativa
        {" · "}<a className="underline underline-offset-2 hover:text-white" href="https://github.com/licgermancardenas-crypto/ENERGIA-EEUU">Código</a>
      </footer>
    </div>
  );
}
