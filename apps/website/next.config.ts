import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  distDir: process.env.KYRION_BUILD_DIRECTORY || ".next",
  // Linked checkouts must resolve their own dependencies and source tree.
  turbopack: { root: path.resolve(__dirname, "../..") },
  async redirects() {
    return [
      { source: "/de", destination: "/", permanent: true },
      { source: "/de/:path+", destination: "/:path+", permanent: true },
    ];
  },
};

export default nextConfig;
