import { pctConSigno } from "@/lib/formato";

/** Variación con flecha + signo + texto: el sentido nunca depende solo del color. */
export function Variacion({ pct, sufijo }: { pct: number | null; sufijo?: string }) {
  if (pct === null) return <span className="text-tinta-2">sin dato previo</span>;
  const sube = pct > 0;
  const plano = pct === 0;
  return (
    <span className="cifra inline-flex items-baseline gap-1">
      <span
        aria-hidden
        className={plano ? "text-tinta-2" : sube ? "text-sube" : "text-baja"}
      >
        {plano ? "■" : sube ? "▲" : "▼"}
      </span>
      <span className="font-medium">{pctConSigno(pct)}</span>
      <span className="sr-only">{plano ? "sin cambios" : sube ? "de suba" : "de baja"}</span>
      {sufijo && <span className="text-tinta-2">{sufijo}</span>}
    </span>
  );
}
