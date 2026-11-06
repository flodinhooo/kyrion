import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
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
