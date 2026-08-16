/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  // Cesium ships huge prebuilt assets; they are copied to /public/cesium by
  // scripts/copy-cesium.mjs and loaded at runtime from CESIUM_BASE_URL.
  webpack: (config) => {
    config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false, http: false, https: false, zlib: false };
    return config;
  },
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false }
};

export default nextConfig;
