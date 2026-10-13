import type { NextConfig } from "next";

const AUTH_BACKEND_BASE_URL =
  process.env.AUTH_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/_next/static/(.*)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/auth/:path*",
        destination: `${AUTH_BACKEND_BASE_URL}/auth/:path*`,
      },
    ];
  },
};

export default nextConfig;
