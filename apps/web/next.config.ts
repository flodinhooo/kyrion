import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  distDir: process.env.KYRION_BUILD_DIRECTORY || ".next",
  output: "standalone",
  turbopack: {
    // apps/web is an intentionally independent pnpm workspace.
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
