"use client";

import { useState } from "react";

/** Vista en tabla de cada gráfico (accesible y apta para lectores de pantalla). Se monta al abrirla. */
export function TablaDatos({ titulo, columnas, filas }: { titulo: string; columnas: string[]; filas: string[][] }) {
  const [abierta, setAbierta] = useState(false);
  return (
    <details className="mt-4 text-sm" onToggle={(e) => setAbierta((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer text-tinta-2 hover:text-tinta">Ver los datos en una tabla ({filas.length} filas)</summary>
      {abierta && (
        <div className="mt-3 max-h-80 overflow-auto rounded-lg border border-linea">
          <table className="cifra w-full text-left">
            <caption className="sr-only">{titulo}</caption>
            <thead className="sticky top-0 bg-superficie-2">
              <tr>
                {columnas.map((c, i) => (
                  <th key={c} scope="col" className={`px-3 py-2 font-medium ${i ? "text-right" : ""}`}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.join("|")} className="border-t border-linea">
                  {f.map((v, i) => (
                    <td key={i} className={`px-3 py-1.5 ${i ? "text-right" : ""}`}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}
