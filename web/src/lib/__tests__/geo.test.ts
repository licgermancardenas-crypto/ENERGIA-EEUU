// La capa geo publicada en public/data/geo debe ser coherente con lo que dibujan Red y Análisis.
import { existsSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { cargarGeo } from "../datos";

describe("capa geoespacial en public/data/geo", () => {
  const g = cargarGeo();

  it("tiene los 50 estados más DC y las geometrías que se bajan en el navegador", () => {
    expect(g.estados).toHaveLength(51);
    for (const capa of ["estados", "red", "condados"]) {
      expect(existsSync(path.join(process.cwd(), "public/data/geo", `mapa_${capa}.geojson`))).toBe(true);
    }
  });

  it("la suma de km por estado no supera la red total", () => {
    const suma = g.estados.reduce((s, e) => s + e.km, 0);
    expect(suma).toBeLessThanOrEqual(g.validacion.km_red_total);
    expect(g.validacion.estados_sin_km).toEqual(["DC", "HI"]);
  });

  it("los porcentajes de calefacción están entre 0 y 1", () => {
    for (const c of Object.values(g.condados)) {
      if (c[1] == null) continue;
      expect(c[1]).toBeGreaterThanOrEqual(0);
      expect(c[1]).toBeLessThanOrEqual(1);
    }
    expect(Object.values(g.condados).filter((c) => c[4] === 1).length).toBe(g.validacion.calefaccion.condados_alta_dependencia_lejos);
  });

  it("el Henry Hub está entre los hubs", () => {
    expect(g.puntos.hubs.some((h) => h.nombre === "Henry Hub")).toBe(true);
  });
});
