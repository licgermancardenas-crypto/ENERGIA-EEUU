// Los JSON publicados en public/data deben ser coherentes con lo que consume la página.
import { describe, expect, it } from "vitest";

import { cargarDatos, SERIES_GRAFICADAS } from "../datos";

describe("datos de Gold en public/data", () => {
  const d = cargarDatos();

  it("incluye todas las series que se grafican y su metadato", () => {
    for (const k of SERIES_GRAFICADAS) {
      expect(d.hechos[k].length).toBeGreaterThan(0);
      expect(d.series[k]).toBeDefined();
    }
  });

  it("el banner y las barras usan series con último dato", () => {
    for (const dest of Object.values(d.destacados)) {
      for (const k of [dest.banner.principal, ...dest.banner.indicadores]) {
        expect(d.ultimo[k]?.valor).toBeTypeOf("number");
      }
      for (const i of dest.barras.items) expect(i.valor).toBe(d.ultimo[i.key].valor);
      expect(dest.frases).toHaveLength(3);
    }
  });

  it("el último punto de cada serie coincide con fact_ultimo_dato", () => {
    for (const k of SERIES_GRAFICADAS) {
      const [fecha, v] = d.hechos[k][d.hechos[k].length - 1];
      expect(d.ultimo[k]).toMatchObject({ fecha, valor: v });
    }
  });

  it("trae los dos escenarios de rezago con su advertencia", () => {
    expect(d.rezago.escenarios.map((e) => e.id)).toEqual(["completo", "sin_pandemia"]);
    expect(d.rezago.advertencia).toMatch(/no causal/);
  });
});
