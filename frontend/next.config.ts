import type { NextConfig } from "next";

const backend = process.env.API_BASE_URL ?? "http://127.0.0.1:8400";

// The browser only talks to this site: the API is reached through the rewrite below, and analytics through /_vercel.
// Next's own bootstrap scripts are inline, so scripts need 'unsafe-inline' until nonces are set up.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://va.vercel-scripts.com",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const config: NextConfig = {
  async headers() {
    return [{ source: "/(.*)", headers: [{ key: "Content-Security-Policy", value: process.env.NODE_ENV === "production" ? csp : csp.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'") }] }];
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
};

export default config;
