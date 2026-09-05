import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.KYRION_BUILD_DIRECTORY || ".next",
  output: "standalone",
};

export default nextConfig;
