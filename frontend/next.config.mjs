/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // MapLibre GL ships its CSS via the package; Next handles it through the
  // import in components/MapCanvas.tsx.
};

export default nextConfig;
