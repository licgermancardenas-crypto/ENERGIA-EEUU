import { Encabezado } from "@/components/marco";
import { Planta } from "@/components/planta";
import { datosPlanta, refinacionPorEstado } from "@/components/planta/tipos";
import { cargarDatos, cargarGeo } from "@/lib/datos";
import { indicadores } from "@/lib/indicadores";

export const metadata = { title: "Planta 3D: petróleo y gas en movimiento · Pulso Energético de EE. UU." };

export default function PaginaPlanta() {
  const d = cargarDatos();
  const g = cargarGeo();
  return (
    <div className="flex min-h-screen flex-col bg-papel">
      <Encabezado activa="Planta" titulo="Petróleo y gas en 3D"
        bajada="Una planta esquemática que se mueve con los datos de la EIA" ind={indicadores(d)} />
      <main className="mx-auto h-[calc(100vh-150px)] min-h-[620px] w-full max-w-[1600px] px-3 py-3 max-lg:h-auto">
        <div className="h-full max-lg:h-[70vh]">
          <Planta datos={datosPlanta(d)} refinacion={refinacionPorEstado(g)} refinerias={g.refinerias.refinerias} />
        </div>
      </main>
      <footer className="mx-auto w-full max-w-[1600px] px-4 pb-5 text-xs text-tinta-3">
        Fuente: U.S. Energy Information Administration (EIA), API v2 · Escena esquemática con modelos 3D
        propios (sin modelos externos) · Autor: Germán Cárdenas
        {" · "}<a className="underline underline-offset-2 hover:text-tinta" href="https://github.com/licgermancardenas-crypto/ENERGIA-EEUU">Código</a>
      </footer>
    </div>
  );
}
