'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  Send,
  Plus,
  ArrowDown,
  ArrowLeft,
  Check,
  Route,
  X,
} from 'lucide-react'
import axios from 'axios'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface AgentInfo {
  label: string
  description: string
  color: string
  icon: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  active_agent?: string
  agent_info?: AgentInfo
}

interface PlanRequest {
  curso?: string | null
  completed?: string[]
  max_creditos?: number
}

// ─── Constantes ───────────────────────────────────────────────────────────────

// Default '/api' = mesma origem (rotas proxyadas via rewrites do next.config.js)
const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api'

const SUGGESTIONS = [
  'Quais são os pré-requisitos de Cálculo Numérico?',
  'Quem leciona Algoritmos e Estrutura de Dados?',
  'Qual a carga horária de Física I?',
  'Me fale sobre os cursos de graduação do ICT',
]

// Etapas que espelham o pipeline real (src/workflow/pipeline.py):
// router → agente (KG + retrieval + geração) → verificação neuro-simbólica.
// Sem streaming de status do backend, o avanço é estimado por tempo.
const REASONING_STEPS: { label: string; at: number }[] = [
  { label: 'Interpretando a pergunta', at: 0 },
  { label: 'Consultando o Knowledge Graph', at: 800 },
  { label: 'Recuperando documentos', at: 2000 },
  { label: 'Gerando resposta', at: 3500 },
  { label: 'Verificando fatos no grafo', at: 6000 },
]

// ─── Rótulo discreto do agente ────────────────────────────────────────────────

function AgentLabel({ agent, agentInfo }: { agent: string; agentInfo?: AgentInfo }) {
  const color = agentInfo?.color || '#9aa8a2'
  const label = agentInfo?.label || agent
  return (
    <div className="mb-3 flex items-center gap-2">
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-paper-mute">
        {label}
      </span>
    </div>
  )
}

// ─── Indicador de raciocínio (linha do tempo do pipeline) ─────────────────────

function ReasoningIndicator({ firstQuery }: { firstQuery: boolean }) {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const timers = REASONING_STEPS.slice(1).map((step, i) =>
      setTimeout(() => setCurrent(i + 1), step.at),
    )
    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <div className="max-w-md rounded-xl border border-line bg-ink-raise px-6 py-5">
      <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-paper-mute">
        Raciocinando
        {firstQuery && (
          <span className="ml-2 normal-case tracking-normal text-paper-mute/70">
            — primeira consulta pode levar mais tempo
          </span>
        )}
      </p>
      <ol className="space-y-0">
        {REASONING_STEPS.map((step, i) => {
          const done = i < current
          const active = i === current
          return (
            <li key={step.label} className="relative flex items-start gap-3 pb-3 last:pb-0">
              {/* Linha vertical conectando as etapas */}
              {i < REASONING_STEPS.length - 1 && (
                <span
                  className={`absolute left-[7px] top-[18px] h-full w-px ${
                    done ? 'bg-accent/40' : 'bg-line-strong'
                  }`}
                  aria-hidden
                />
              )}
              {/* Marcador */}
              <span className="relative z-10 mt-[3px] flex h-[15px] w-[15px] flex-shrink-0 items-center justify-center">
                {done ? (
                  <span className="flex h-[15px] w-[15px] items-center justify-center rounded-full bg-accent/15">
                    <Check className="h-2.5 w-2.5 text-accent" strokeWidth={3} />
                  </span>
                ) : active ? (
                  <span className="step-active-dot h-[9px] w-[9px] rounded-full bg-accent" />
                ) : (
                  <span className="h-[7px] w-[7px] rounded-full border border-line-strong" />
                )}
              </span>
              <span
                className={`font-mono text-[12.5px] leading-[21px] transition-colors duration-300 ${
                  done ? 'text-paper-dim' : active ? 'text-paper' : 'text-paper-mute'
                }`}
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

// ─── Markdown com estilo customizado ─────────────────────────────────────────

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => (
    <p className="mb-3.5 leading-[1.75] text-paper/90 last:mb-0">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-paper">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-paper-dim">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
    >
      {children}
    </a>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.includes('language-')
    return isBlock ? (
      <code className="my-3 block whitespace-pre-wrap rounded-lg border border-line bg-ink-deep p-4 font-mono text-[13px] leading-relaxed text-accent">
        {children}
      </code>
    ) : (
      <code className="rounded bg-ink-deep px-1.5 py-0.5 font-mono text-[13px] text-accent">
        {children}
      </code>
    )
  },
  pre: ({ children }) => <>{children}</>,
  ul: ({ children }) => <ul className="my-3 list-none space-y-2 pl-0">{children}</ul>,
  ol: ({ children }) => (
    <ol className="my-3 list-decimal space-y-2 pl-5 text-paper/90 marker:text-paper-mute">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="flex items-start gap-2.5 text-paper/90">
      <span className="mt-[10px] h-1 w-1 flex-shrink-0 rounded-full bg-accent" />
      <span className="flex-1 leading-[1.7]">{children}</span>
    </li>
  ),
  h1: ({ children }) => (
    <h1 className="mb-3 mt-5 font-display text-lg font-medium text-paper first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2.5 mt-5 font-display text-base font-medium text-paper first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 font-display text-[15px] font-medium text-paper first:mt-0">
      {children}
    </h3>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-accent/40 pl-4 text-paper-dim">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-line" />,
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-line">
      <table className="min-w-full text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-line bg-ink-deep px-4 py-2.5 text-left font-mono text-xs uppercase tracking-wider text-paper-dim">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-line px-4 py-2.5 text-paper/90 last:border-b-0">
      {children}
    </td>
  ),
}

// ─── Hook: Typewriter ─────────────────────────────────────────────────────────

function useTypewriter(text: string, enabled: boolean, onDone?: () => void) {
  const [displayed, setDisplayed] = useState('')
  const [isDone, setIsDone] = useState(!enabled)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled) {
      setDisplayed(text)
      setIsDone(true)
      return
    }

    setDisplayed('')
    setIsDone(false)

    if (!text) {
      setIsDone(true)
      onDone?.()
      return
    }

    // Velocidade adaptativa: limita a animação total a ~2.5s
    const speed = Math.max(4, Math.min(18, Math.floor(2500 / text.length)))
    let i = 0

    const tick = () => {
      i++
      setDisplayed(text.slice(0, i))
      if (i < text.length) {
        timerRef.current = setTimeout(tick, speed)
      } else {
        setIsDone(true)
        onDone?.()
      }
    }

    timerRef.current = setTimeout(tick, speed)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, enabled])

  return { displayed, isDone }
}

// ─── Mensagem do assistente ───────────────────────────────────────────────────

function AssistantMessage({
  message,
  isAnimating,
  onAnimationDone,
}: {
  message: Message
  isAnimating: boolean
  onAnimationDone: () => void
}) {
  const { displayed, isDone } = useTypewriter(
    message.content,
    isAnimating,
    onAnimationDone,
  )

  const textToRender = isAnimating ? displayed : message.content

  return (
    <div className="text-[15px]">
      {message.active_agent && message.active_agent !== 'fallback' && (
        <AgentLabel agent={message.active_agent} agentInfo={message.agent_info} />
      )}

      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {textToRender}
      </ReactMarkdown>

      {/* Cursor durante a animação */}
      {isAnimating && !isDone && (
        <span className="caret-blink ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] bg-accent" />
      )}
    </div>
  )
}

// ─── Página principal ─────────────────────────────────────────────────────────

export default function ChatPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [activeAgent, setActiveAgent] = useState<{ agent: string; info?: AgentInfo } | null>(null)
  // Índice da mensagem atualmente sendo animada (-1 = nenhuma)
  const [animatingIndex, setAnimatingIndex] = useState(-1)
  // URL do planejador de trajetória (canvas ao vivo). null = painel fechado.
  const [plannerUrl, setPlannerUrl] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }

  useEffect(() => { scrollToBottom() }, [messages])

  useEffect(() => {
    createNewConversation()
    inputRef.current?.focus()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      setShowScrollButton(scrollHeight - scrollTop - clientHeight > 100 && messages.length > 0)
    }
    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [messages.length])

  const createNewConversation = async () => {
    try {
      const response = await axios.post(`${API_URL}/conversations`)
      setConversationId(response.data.conversation_id)
      setMessages([])
      setError(null)
      setAnimatingIndex(-1)
    } catch {
      setError('Não foi possível conectar ao servidor.')
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setError(null)

    if (inputRef.current) inputRef.current.style.height = 'auto'

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        message: userMessage.content,
        conversation_id: conversationId,
        include_history: true,
        max_history: 10,
      })

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.data.response,
        timestamp: response.data.timestamp,
        active_agent: response.data.active_agent,
        agent_info: response.data.agent_info,
      }

      setMessages((prev) => {
        const next = [...prev, assistantMessage]
        // Animar o índice da mensagem recém-adicionada
        setAnimatingIndex(next.length - 1)
        return next
      })

      setActiveAgent({
        agent: response.data.active_agent || 'fallback',
        info: response.data.agent_info,
      })

      // Se o agente pediu para montar a grade, abre o planejador (canvas ao vivo).
      const planReq: PlanRequest | undefined = response.data.plan_request
      if (planReq) {
        const params = new URLSearchParams()
        if (planReq.curso) {
          params.set('curso', planReq.curso)
          // Com curso detectado, o canvas já monta a grade sozinho.
          params.set('auto', '1')
        }
        if (planReq.completed && planReq.completed.length) {
          params.set('completed', planReq.completed.join(';'))
        }
        if (planReq.max_creditos) {
          params.set('creditos', String(planReq.max_creditos))
        }
        const qs = params.toString()
        setPlannerUrl(`${API_URL}/planner${qs ? `?${qs}` : ''}`)
      }

      if (!conversationId) setConversationId(response.data.conversation_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao processar. Tente novamente.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const t = e.target as HTMLTextAreaElement
    t.style.height = 'auto'
    t.style.height = `${Math.min(t.scrollHeight, 160)}px`
  }

  const handleAnimationDone = useCallback(() => {
    setAnimatingIndex(-1)
  }, [])

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-ink text-paper">

      {/* ── Header ── */}
      <header className="relative z-20 border-b border-line bg-ink/80 backdrop-blur-xl">
        <div className="mx-auto max-w-4xl px-4 py-4 sm:px-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/')}
                aria-label="Voltar para a página inicial"
                className="rounded-lg border border-line p-2 text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>

              <div className="flex items-center gap-3">
                <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
                  <line x1="5" y1="18" x2="12" y2="6" stroke="#34d399" strokeOpacity="0.5" strokeWidth="1.2" />
                  <line x1="12" y1="6" x2="19" y2="16" stroke="#34d399" strokeOpacity="0.5" strokeWidth="1.2" />
                  <line x1="5" y1="18" x2="19" y2="16" stroke="#34d399" strokeOpacity="0.5" strokeWidth="1.2" />
                  <circle cx="5" cy="18" r="2.4" fill="#34d399" />
                  <circle cx="12" cy="6" r="2.4" fill="#34d399" />
                  <circle cx="19" cy="16" r="2.4" fill="#34d399" />
                </svg>
                <div>
                  <span className="font-mono text-sm tracking-widest text-paper">FESP-AI</span>
                  <p className="hidden text-[11px] text-paper-mute sm:block">
                    Assistente da UNIFESP ICT
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              {activeAgent && !isLoading && activeAgent.agent !== 'fallback' && (
                <motion.div
                  initial={{ opacity: 0, x: 6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="hidden items-center gap-2 rounded-lg border border-line px-3 py-2 sm:flex"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: activeAgent.info?.color || '#9aa8a2' }}
                  />
                  <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-paper-dim">
                    {activeAgent.info?.label || activeAgent.agent}
                  </span>
                </motion.div>
              )}

              <button
                onClick={() => setPlannerUrl(`${API_URL}/planner`)}
                className="flex items-center gap-2 rounded-lg border border-line px-3.5 py-2 text-sm text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
              >
                <Route className="h-4 w-4" />
                <span className="hidden sm:inline">Planejador</span>
              </button>

              <button
                onClick={createNewConversation}
                className="flex items-center gap-2 rounded-lg border border-line px-3.5 py-2 text-sm text-paper-dim transition-colors hover:border-accent/40 hover:text-accent"
              >
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Nova conversa</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ── Mensagens ── */}
      <main ref={messagesContainerRef} className="relative z-10 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">

          {/* Estado vazio */}
          {messages.length === 0 && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex min-h-[55vh] flex-col justify-center"
            >
              <p className="mb-4 font-mono text-xs uppercase tracking-[0.25em] text-accent">
                UNIFESP — ICT
              </p>
              <h2 className="font-display text-3xl font-medium tracking-tightest text-paper sm:text-4xl">
                O que você quer saber?
              </h2>
              <p className="mt-4 max-w-lg text-paper-dim">
                Disciplinas, docentes, cursos e regimentos do campus São José dos
                Campos. As respostas são verificadas no grafo de conhecimento.
              </p>

              <div className="mt-10 grid gap-3 sm:grid-cols-2">
                {SUGGESTIONS.map((text, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.07 + 0.2 }}
                    onClick={() => { setInput(text); inputRef.current?.focus() }}
                    className="group rounded-xl border border-line bg-ink-raise p-4 text-left transition-colors hover:border-accent/30"
                  >
                    <span className="font-mono text-[11px] text-paper-mute transition-colors group-hover:text-accent">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <p className="mt-1.5 text-sm leading-relaxed text-paper-dim transition-colors group-hover:text-paper">
                      {text}
                    </p>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Lista de mensagens */}
          <div className="space-y-8">
            <AnimatePresence initial={false}>
              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className={msg.role === 'user' ? 'flex justify-end' : ''}
                >
                  {msg.role === 'user' ? (
                    <div className="max-w-[85%] rounded-2xl rounded-br-md border border-accent/20 bg-accent/10 px-5 py-3.5 sm:max-w-[70%]">
                      <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed text-paper">
                        {msg.content}
                      </p>
                    </div>
                  ) : (
                    <div className="rounded-2xl rounded-bl-md border border-line bg-ink-raise px-6 py-5">
                      <AssistantMessage
                        message={msg}
                        isAnimating={idx === animatingIndex}
                        onAnimationDone={handleAnimationDone}
                      />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Indicador de raciocínio */}
            <AnimatePresence>
              {isLoading && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.25 }}
                >
                  <ReasoningIndicator firstQuery={messages.length <= 1} />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Erro */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex justify-center"
                >
                  <div className="rounded-xl border border-red-500/25 bg-red-500/10 px-5 py-3.5">
                    <p className="text-sm text-red-300">{error}</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Botão de scroll */}
        <AnimatePresence>
          {showScrollButton && (
            <motion.button
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
              onClick={() => scrollToBottom()}
              aria-label="Ir para o fim da conversa"
              className="fixed bottom-32 right-8 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-ink-raise text-paper-dim backdrop-blur-xl transition-colors hover:border-accent/40 hover:text-accent"
            >
              <ArrowDown className="h-[18px] w-[18px]" />
            </motion.button>
          )}
        </AnimatePresence>
      </main>

      {/* ── Input ── */}
      <footer className="relative z-20 border-t border-line bg-ink/80 backdrop-blur-xl">
        <div className="mx-auto max-w-3xl px-4 py-5 sm:px-6">
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleTextareaInput}
              placeholder="Escreva sua pergunta"
              rows={1}
              disabled={isLoading}
              className="w-full flex-1 resize-none overflow-hidden rounded-xl border border-line bg-ink-raise px-5 py-[15px] text-[15px] leading-relaxed text-paper placeholder-paper-mute transition-colors focus:border-accent/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
              style={{ minHeight: '54px', maxHeight: '160px' }}
            />

            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              aria-label="Enviar pergunta"
              className="flex h-[54px] w-[54px] flex-shrink-0 items-center justify-center rounded-xl bg-accent text-ink transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-30"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>

          <p className="mt-3 text-center font-mono text-[11px] text-paper-mute">
            Enter envia. Shift + Enter quebra a linha. Respostas podem conter
            erros; confirme o que for importante.
          </p>
        </div>
      </footer>

      {/* Painel do Planejador de Trajetória (canvas ao vivo) */}
      <AnimatePresence>
        {plannerUrl && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setPlannerUrl(null)}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 260 }}
              className="fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-line bg-ink shadow-2xl md:w-[64%] lg:w-[58%]"
            >
              <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
                <div className="flex items-center gap-3">
                  <Route className="h-4 w-4 text-accent" />
                  <div>
                    <p className="font-mono text-xs uppercase tracking-[0.15em] text-paper">
                      Planejador de trajetória
                    </p>
                    <p className="text-[11px] text-paper-mute">
                      Montando sua grade ao vivo
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setPlannerUrl(null)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-line text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
                  aria-label="Fechar planejador"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <iframe
                src={plannerUrl}
                className="w-full flex-1 border-0"
                title="Planejador de Trajetória"
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
