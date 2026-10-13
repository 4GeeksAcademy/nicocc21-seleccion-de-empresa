import type { NextConfig } from "next";

const AUTH_BACKEND_BASE_URL =
  process.env.AUTH_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
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
