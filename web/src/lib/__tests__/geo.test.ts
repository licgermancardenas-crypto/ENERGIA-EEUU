// La capa geo publicada en public/data/geo debe ser coherente con lo que dibujan Red y Análisis.
import { existsSync, readFileSync } from "node:fs";
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

  it("los pulsos avanzan: cada trayecto tiene km crecientes desde el Henry Hub", () => {
    const p = JSON.parse(readFileSync(path.join(process.cwd(), "public/data/geo/pulsos.json"), "utf-8")) as
      { max_km: number; trayectos: [number, number, number][][] };
    expect(p.trayectos.length).toBeGreaterThan(1000);
    for (const tr of p.trayectos) {
      for (let i = 1; i < tr.length; i++) expect(tr[i][2]).toBeGreaterThanOrEqual(tr[i - 1][2]);
    }
    expect(Math.max(...p.trayectos.map((tr) => tr[tr.length - 1][2]))).toBeCloseTo(p.max_km, 0);
  });

  it("cada flujo entre estados une dos estados con punto central y volumen positivo", () => {
    const centro = new Map(g.estados.map((e) => [e.k, e.centro]));
    expect(g.flujos.anios.length).toBeGreaterThan(0);
    for (const [o, d, , mmcf] of g.flujos.pares) {
      expect(centro.get(o)).toBeTruthy();
      expect(centro.get(d)).toBeTruthy();
      expect(o).not.toBe(d);
      expect(mmcf).toBeGreaterThan(0);
    }
  });
  it("refinerías: cada una con estado y capacidad; el total por estado es el de la API", () => {
    const { refinerias, estados, anio } = g.refinerias;
    expect(anio).toBeGreaterThanOrEqual(2026);
    expect(refinerias.length).toBeGreaterThan(100);
    for (const r of refinerias) {
      expect(r.estado).toMatch(/^[A-Z]{2}$/);
      expect(r.bcd).toBeGreaterThan(0);
    }
    const suma = refinerias.reduce((s, r) => s + r.bcd, 0);
    const api = Object.values(estados).reduce((s, e) => s + e.bcd, 0);
    expect(Math.abs(suma - api)).toBeLessThan(1);
  });
});
