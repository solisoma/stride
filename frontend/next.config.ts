import type { NextConfig } from 'next';
const config: NextConfig = {
  distDir: process.env.LEARNFORWARD_TEST_DIST_DIR || '.next',
  experimental: { proxyClientMaxBodySize: '25mb', proxyTimeout: 1800000 },
  async rewrites() {
    const backend = process.env.BACKEND_URL || 'http://127.0.0.1:8001';
    return [{ source: '/api/backend/:path*', destination: `${backend}/:path*` }];
  },
};
export default config;
