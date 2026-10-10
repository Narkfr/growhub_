/** @type {import('next').NextConfig} */
const API_URL = process.env.GROWHUB_API_URL || 'http://127.0.0.1:5001';

const nextConfig = {
  reactStrictMode: true,
  // Compression désactivée : le proxy réécrit /api vers le backend et recompressait
  // le flux SSE, qu'un navigateur bufferise alors par blocs — plus aucune mesure en
  // direct dans le tableau de bord (10 octets en 8 s en gzip contre 446 en clair),
  // alors que l'historique, lui, fonctionnait. Déclarer `Content-Encoding: identity`
  // côté Django n'a pas suffi. Sur un réseau local, la compression ne rapporte rien.
  compress: false,
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
