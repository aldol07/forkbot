/** Dashboard talks to FastAPI through a same-origin rewrite, so the httpOnly session
 *  cookie just works and no CORS is needed for /api. */
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  compress: false, // keep Server-Sent Events streaming through the proxy unbuffered
  poweredByHeader: false,
  // the /api rewrite proxies uploads; Next's default 10 MB cap would turn big files into a bare 500.
  // Keep this above MAX_UPLOAD_MB so the API can answer with a proper "too large" message.
  experimental: { middlewareClientMaxBodySize: "30mb" },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
};
export default nextConfig;
