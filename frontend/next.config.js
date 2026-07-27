/** @type {import('next').NextConfig} */

// URL interna do backend (nome do serviço no docker-compose)
const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || 'http://backend:8000'

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy das rotas da API para o backend — permite servir tudo pela
    // mesma origem (um único túnel público, sem CORS).
    return [
      // Namespace /api/* — evita colisão com páginas do app router
      // (ex.: a página /chat sombrearia um rewrite direto de POST /chat).
      { source: '/api/:path*', destination: `${BACKEND_URL}/:path*` },
      // Rotas usadas pelo planner.html (iframe servido pelo backend usa
      // caminhos relativos à origem do frontend) — sem colisão com páginas.
      { source: '/health', destination: `${BACKEND_URL}/health` },
      { source: '/telemetry', destination: `${BACKEND_URL}/telemetry` },
      { source: '/planner', destination: `${BACKEND_URL}/planner` },
      { source: '/plan/:path*', destination: `${BACKEND_URL}/plan/:path*` },
      { source: '/cursos', destination: `${BACKEND_URL}/cursos` },
    ]
  },
}

module.exports = nextConfig
