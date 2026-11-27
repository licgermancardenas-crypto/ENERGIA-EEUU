import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Pulso Energético de EE. UU. — Petróleo y gas",
  description:
    "Precios, inventarios, producción, consumo y la red de gas natural de EE. UU., con datos oficiales de la EIA.",
  authors: [{ name: "Germán Cárdenas" }],
};

export const viewport: Viewport = { themeColor: "#0b1f3a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-AR">
      <body>{children}</body>
    </html>
  );
}
