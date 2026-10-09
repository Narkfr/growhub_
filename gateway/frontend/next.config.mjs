/** @type {import('next').NextConfig} */
const API_URL = process.env.GROWHUB_API_URL || 'http://127.0.0.1:5001';

const nextConfig = {
  reactStrictMode: true,
  // Le paquet partagé est livré en source TypeScript (pas d'étape de build) :
  // Next le compile avec l'application, et Metro fera de même côté mobile.
  transpilePackages: ['@growhub/client'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
