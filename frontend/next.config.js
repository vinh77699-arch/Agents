/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    // BACKEND_URL is server-side only (safe to use Docker internal hostname)
    // NEXT_PUBLIC_API_URL is for local dev where backend runs on localhost
    const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
