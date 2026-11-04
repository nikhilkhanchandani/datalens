import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this folder. Otherwise Next can pick up an
  // unrelated package-lock.json in a parent directory and infer the wrong root.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
