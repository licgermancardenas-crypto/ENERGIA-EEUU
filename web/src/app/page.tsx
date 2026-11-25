import { Dashboard } from "@/components/Dashboard";
import { cargarDatos } from "@/lib/datos";

export default function Pagina() {
  return <Dashboard datos={cargarDatos()} />;
}
