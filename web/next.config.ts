import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // No floating Next.js badge over the crew-facing UI in development.
  devIndicators: false,
  // Lets a production build run beside the dev server without sharing its output folder.
  distDir: process.env.NEXT_DIST_DIR || '.next',
};

export default nextConfig;
