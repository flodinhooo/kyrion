import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/de", destination: "/", permanent: true },
      { source: "/de/:path+", destination: "/:path+", permanent: true },
    ];
  },
};

export default nextConfig;
