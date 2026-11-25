import type { NextConfig } from "next";

// Export estático: `next build` deja el sitio en out/, listo para Vercel o cualquier hosting.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  poweredByHeader: false,
};

export default nextConfig;
