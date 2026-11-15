import type { NextConfig } from "next";

// The browser only ever talks to this Next.js origin. /api and /media are proxied to the FastAPI backend,
// so the admin session cookie is first-party (httpOnly, SameSite=Strict) and no backend URL or
// credential is exposed to the browser bundle.
const BACKEND = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8100";
const isDev = process.env.NODE_ENV !== "production";
// Origin that serves images: the API's PUBLIC_API_BASE_URL (local storage) or the S3/CDN public URL.
// Media URLs returned by the API are absolute, so the CSP must allow that origin explicitly.
const MEDIA_ORIGIN = process.env.MEDIA_PUBLIC_ORIGIN || (isDev ? "http://localhost:8100" : "");

const csp = [
  "default-src 'self'",
  `img-src 'self' data: blob: ${MEDIA_ORIGIN}`.trim(),
  "style-src 'self' 'unsafe-inline'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "font-src 'self'",
  "connect-src 'self'",
  "frame-src https://www.youtube-nocookie.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/media/:path*", destination: `${BACKEND}/media/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
