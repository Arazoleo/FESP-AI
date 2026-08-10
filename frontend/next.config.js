const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || 'http://backend:8000'

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/health', destination: `${BACKEND_URL}/health` },
      { source: '/telemetry', destination: `${BACKEND_URL}/telemetry` },
      { source: '/planner', destination: `${BACKEND_URL}/planner` },
      { source: '/plan/:path*', destination: `${BACKEND_URL}/plan/:path*` },
      { source: '/cursos', destination: `${BACKEND_URL}/cursos` },
    ]
  },
}

module.exports = nextConfig
