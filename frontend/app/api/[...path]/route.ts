import { NextRequest } from 'next/server'

// Proxy server-side de /api/* para o backend com timeout LONGO.
//
// Substitui o rewrite `/api/:path*` do next.config.js: o proxy interno do
// Next (undici) corta a conexão upstream em ~30s ("socket hang up"), o que
// derrubava respostas lentas do pipeline (roteador LLM + geração + retry).
// Aqui fazemos o fetch nós mesmos com AbortSignal de 300s e repassamos o
// corpo como stream (pass-through), sem bufferizar a resposta.

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || 'http://backend:8000'
const UPSTREAM_TIMEOUT_MS = 300_000 // 5 min

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

// Headers hop-by-hop / controlados pelo fetch — não repassar.
const SKIP_REQUEST_HEADERS = new Set([
  'host',
  'connection',
  'content-length',
  'accept-encoding',
  'transfer-encoding',
])
const SKIP_RESPONSE_HEADERS = new Set([
  'connection',
  'content-length',
  'content-encoding',
  'transfer-encoding',
  'keep-alive',
])

async function proxy(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const search = req.nextUrl.search || ''
  const target = `${BACKEND_URL}/${params.path.join('/')}${search}`

  const headers = new Headers()
  req.headers.forEach((value, key) => {
    if (!SKIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value)
  })

  const hasBody = req.method !== 'GET' && req.method !== 'HEAD'
  const body = hasBody ? await req.arrayBuffer() : undefined

  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    })
  } catch (err: any) {
    const timedOut = err?.name === 'TimeoutError' || err?.name === 'AbortError'
    return Response.json(
      {
        detail: timedOut
          ? 'Tempo limite excedido ao aguardar o backend.'
          : 'Falha ao conectar ao backend.',
      },
      { status: timedOut ? 504 : 502 }
    )
  }

  const responseHeaders = new Headers()
  upstream.headers.forEach((value, key) => {
    if (!SKIP_RESPONSE_HEADERS.has(key.toLowerCase())) {
      responseHeaders.set(key, value)
    }
  })

  // Pass-through do corpo como stream (não bufferiza).
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as HEAD,
  proxy as OPTIONS,
}
