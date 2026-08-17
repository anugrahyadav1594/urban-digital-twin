/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  // Cesium ships huge prebuilt assets; they are copied to /public/cesium by
  // scripts/copy-cesium.mjs and loaded at runtime from CESIUM_BASE_URL.
  webpack: (config) => {
    config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false, http: false, https: false, zlib: false };
    return config;
  },
  // NOTE: /api/v1/* is proxied by app/api/v1/[...path]/route.ts, not by a
  // rewrite - the built-in rewrite proxy times out at 30 s and long analyses
  // need far more than that.
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false }
};

export default nextConfig;
