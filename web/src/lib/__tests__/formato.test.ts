import { describe, expect, it } from "vitest";

import { fechaCorta, fechaEje, mesAnio, num, pctConSigno, valor } from "../formato";

describe("formato rioplatense", () => {
  it("formatea números con punto de miles y coma decimal", () => {
    expect(num(1234567.891)).toBe("1.234.567,89");
    expect(valor(417797, "MBBL")).toBe("417.797");
    expect(valor(3.642, "$/GAL")).toBe("3,642");
  });
  it("muestra el signo de la variación", () => {
    expect(pctConSigno(0.0153)).toBe("+1,5 %");
    expect(pctConSigno(-0.0428)).toBe("−4,3 %");
  });
  it("formatea fechas ISO sin corrimiento de zona horaria", () => {
    expect(fechaCorta("2026-11-17")).toBe("17/11/2026");
    expect(fechaEje("2026-01-05")).toBe("ene 26");
    expect(mesAnio("2026-08-01")).toBe("agosto 2026");
  });
});
