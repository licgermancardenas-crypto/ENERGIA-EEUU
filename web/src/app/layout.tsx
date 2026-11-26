import type { Metadata, Viewport } from "next";
import { Fraunces, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--fuente-display", weight: ["500", "600"] });
const texto = IBM_Plex_Sans({ subsets: ["latin"], variable: "--fuente-texto", weight: ["400", "500", "600"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--fuente-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "Pulso Energético de EE. UU. — Petróleo y gas",
  description:
    "Precios, inventarios, producción y consumo de petróleo y gas natural de EE. UU., actualizados con datos oficiales de la EIA.",
  authors: [{ name: "Germán Cárdenas" }],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f1ea" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1113" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-AR" className={`${display.variable} ${texto.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
