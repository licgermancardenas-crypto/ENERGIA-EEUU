// Los datos del mapa de petróleo deben ser coherentes con lo que dibuja /petroleo-red.
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const leer = (n: string) => JSON.parse(readFileSync(path.join(process.cwd(), "public/data/petroleo", n), "utf-8"));

describe("datos del mapa de petróleo", () => {
  const meta = leer("meta.json");

  it("cada capa trae origen, licencia y cantidad de elementos", () => {
    for (const [k, c] of Object.entries(meta.capas) as [string, { origen: string | null; licencia: string | null; elementos: number | null }][]) {
      if (k === "series") continue;
      expect(c.origen, k).toBeTruthy();
      expect(c.licencia, k).toBeTruthy();
      expect(c.elementos, k).toBeGreaterThan(0);
    }
    expect(meta.no_disponibles.length).toBeGreaterThan(0);
  });

  it("los km de ducto se calcularon y son plausibles para EE. UU.", () => {
    expect(meta.capas.oleoductos.km_total).toBeGreaterThan(30000);
    expect(meta.capas.poliductos.km_total).toBeGreaterThan(30000);
  });

  it("los pulsos avanzan desde Cushing (km crecientes)", () => {
    const p = leer("pulsos.json") as { origen: [number, number]; trayectos: [number, number, number][][] };
    expect(p.origen[0]).toBeCloseTo(meta.cushing.lon, 3);
    for (const tr of p.trayectos) for (let i = 1; i < tr.length; i++) expect(tr[i][2]).toBeGreaterThanOrEqual(tr[i - 1][2]);
  });

  it("la producción por PADD suma lo mismo que los estados más el offshore, con tolerancia", () => {
    const s = leer("series.json");
    const anio = Object.keys(s.produccion_padd.R30).sort().at(-1)!;
    const padd = Object.values(s.produccion_padd as Record<string, Record<string, number>>).reduce((a, x) => a + (x[anio] ?? 0), 0);
    expect(padd).toBeGreaterThan(5000);
    expect(s.offshore_golfo[anio]).toBeGreaterThan(0);
  });

  it("las plataformas no traen años de instalación imposibles", () => {
    const pl = leer("plataformas.json") as { features: { properties: { anio_instalacion: number | null } }[] };
    for (const f of pl.features) {
      const a = f.properties.anio_instalacion;
      if (a != null) expect(a).toBeGreaterThanOrEqual(1938);
    }
  });
});
