import type { NextConfig } from "next";

const backend = process.env.API_BASE_URL ?? "http://127.0.0.1:8400";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
};

export default config;
