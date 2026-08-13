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
  FileUp,
} from 'lucide-react'
import axios from 'axios'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import PrereqGraph, { PrereqGraphData } from '../components/PrereqGraph'
import DisciplineDrawer from '../components/DisciplineDrawer'
import DocenteDrawer from '../components/DocenteDrawer'
import DisciplineChips, { DisciplineListData } from '../components/DisciplineChips'
import AcBars, { AcReportData } from '../components/AcBars'
import ThemeToggle from '../components/ThemeToggle'
import DecryptText from '../components/DecryptText'
import LiveGraph from '../components/LiveGraph'
import GraphConfetti from '../components/GraphConfetti'
import PlannerDrawer from '../components/PlannerDrawer'

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
  intent?: string
  graph_data?: PrereqGraphData | null
  list_data?: DisciplineListData | null
  ac_data?: AcReportData | null
  suggestions?: string[] | null
}

interface PlanRequest {
  curso?: string | null
  completed?: string[]
  max_creditos?: number
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api'

const SUGGESTIONS = [
  'Quais são os pré-requisitos de Compiladores?',
  'Quem leciona Banco de Dados?',
  'Como funcionam as atividades complementares?',
  'Quais as últimas notícias do campus?',
]

const REASONING_STEPS: { label: string; at: number }[] = [
  { label: 'Interpretando a pergunta', at: 0 },
  { label: 'Consultando o Knowledge Graph', at: 800 },
  { label: 'Recuperando documentos', at: 2000 },
  { label: 'Gerando resposta', at: 3500 },
  { label: 'Verificando fatos no grafo', at: 6000 },
]

function AgentLabel({
  agent,
  agentInfo,
  intent,
}: {
  agent: string
  agentInfo?: AgentInfo
  intent?: string
}) {
  const color = agentInfo?.color || '#9aa8a2'
  const label = agentInfo?.label || agent
  const simbolico = agent === 'symbolic_kg'
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-paper-mute">
        {label}
      </span>
      {simbolico && intent && (
        <span className="demo-chip rounded-full border border-accent/30 bg-accent/10 px-2.5 py-0.5 font-mono text-[10px] text-accent">
          ⚙ {intent}
        </span>
      )}
      {simbolico && (
        <span
          className="demo-chip rounded-md border border-accent/25 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-accent"
          style={{ animationDelay: '0.15s' }}
        >
          verificado no grafo
        </span>
      )}
    </div>
  )
}

const STEP_NODES: number[][] = [
  [1],
  [1, 0, 6],
  [5, 6],
  [1, 2, 4],
  [0, 1, 3, 6],
]

function ReasoningIndicator({ firstQuery }: { firstQuery: boolean }) {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const timers = REASONING_STEPS.slice(1).map((step, i) =>
      setTimeout(() => setCurrent(i + 1), step.at),
    )
    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <div className="beam-border max-w-md overflow-hidden rounded-xl border border-line bg-ink-raise">
      <div className="pointer-events-none h-[110px] border-b border-line opacity-80">
        <LiveGraph
          highlight={STEP_NODES[Math.min(current, STEP_NODES.length - 1)]}
          cursorLink={false}
          className="h-full w-full"
        />
      </div>
      <div className="px-6 py-5">
      <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-paper-mute">
        Raciocinando
        {firstQuery && (
          <span className="ml-2 normal-case tracking-normal text-paper-mute/70">
            - primeira consulta pode levar mais tempo
          </span>
        )}
      </p>
      <ol className="space-y-0">
        {REASONING_STEPS.map((step, i) => {
          const done = i < current
          const active = i === current
          return (
            <li key={step.label} className="relative flex items-start gap-3 pb-3 last:pb-0">
              {i < REASONING_STEPS.length - 1 && (
                <span
                  className={`absolute left-[7px] top-[18px] h-full w-px ${
                    done ? 'bg-accent/40' : 'bg-line-strong'
                  }`}
                  aria-hidden
                />
              )}
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
                {active ? (
                  <DecryptText key={step.label} text={step.label} />
                ) : (
                  step.label
                )}
              </span>
            </li>
          )
        })}
      </ol>
      </div>
    </div>
  )
}

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

  }, [text, enabled])

  return { displayed, isDone }
}

function AssistantMessage({
  message,
  isAnimating,
  onAnimationDone,
  onAsk,
  onSelectDiscipline,
  showSuggestions,
}: {
  message: Message
  isAnimating: boolean
  onAnimationDone: () => void
  onAsk?: (question: string) => void
  onSelectDiscipline?: (nome: string) => void
  showSuggestions?: boolean
}) {
  const { displayed, isDone } = useTypewriter(
    message.content,
    isAnimating,
    onAnimationDone,
  )

  const textToRender = isAnimating ? displayed : message.content
  const hasGraph = !!message.graph_data?.nodes?.length
  const doneTyping = !isAnimating || isDone

  return (
    <div className="text-[15px]">
      {message.active_agent && message.active_agent !== 'fallback' && (
        <AgentLabel
          agent={message.active_agent}
          agentInfo={message.agent_info}
          intent={message.intent}
        />
      )}

      {hasGraph && (
        <PrereqGraph
          data={message.graph_data!}
          onAsk={onAsk}
          onSelect={onSelectDiscipline}
        />
      )}

      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {textToRender}
      </ReactMarkdown>

      {isAnimating && !isDone && (
        <span className="caret-blink ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] bg-accent" />
      )}

      {doneTyping && message.ac_data && <AcBars data={message.ac_data} />}

      {doneTyping && message.list_data && onSelectDiscipline && (
        <DisciplineChips data={message.list_data} onSelect={onSelectDiscipline} />
      )}

      {doneTyping && showSuggestions && !!message.suggestions?.length && (
        <div className="mt-4 flex flex-wrap gap-2">
          {message.suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onAsk?.(s)}
              className="rounded-full border border-accent/30 bg-accent/5 px-3.5 py-1.5 text-[12.5px] text-accent transition-colors hover:bg-accent/15"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [placeholder, setPlaceholder] = useState('Escreva sua pergunta')
  const [confete, setConfete] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [activeAgent, setActiveAgent] = useState<{ agent: string; info?: AgentInfo } | null>(null)
  const [animatingIndex, setAnimatingIndex] = useState(-1)
  const [plannerOpen, setPlannerOpen] = useState(false)
  const [plannerCurso, setPlannerCurso] = useState<string | null>(null)
  const [selectedDiscipline, setSelectedDiscipline] = useState<string | null>(null)
  const [selectedDocente, setSelectedDocente] = useState<string | null>(null)

  const [historicoCarregado, setHistoricoCarregado] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }

  useEffect(() => { scrollToBottom() }, [messages])

  useEffect(() => {
    createNewConversation()
    const params = new URLSearchParams(window.location.search)
    const q = params.get('q')
    if (q) {
      setInput(q)
      window.history.replaceState(null, '', '/chat')
    }
    inputRef.current?.focus()

  }, [])

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const frases = [
      'Quanto falta para me formar?',
      'Se eu tirar 9 em POO, meu CR vai a quanto?',
      'Vai ter Compiladores no próximo semestre?',
      'Quais os pré-requisitos de Compiladores?',
      'Como faço para colar grau?',
      'Quem leciona Interação Humano-Computador?',
    ]
    let idx = 0
    let pos = 0
    let apagando = false
    let timer: ReturnType<typeof setTimeout>
    const passo = () => {
      const alvo = frases[idx]
      let atraso = apagando ? 16 : 42
      if (!apagando) {
        pos += 1
        setPlaceholder(alvo.slice(0, pos))
        if (pos >= alvo.length) {
          apagando = true
          atraso = 2400
        }
      } else {
        pos -= 1
        setPlaceholder(alvo.slice(0, pos) || ' ')
        if (pos <= 0) {
          apagando = false
          idx = (idx + 1) % frases.length
          atraso = 450
        }
      }
      timer = setTimeout(passo, atraso)
    }
    timer = setTimeout(passo, 1500)
    return () => clearTimeout(timer)
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

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return

    const userMessage: Message = { role: 'user', content: content.trim() }
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
        intent: response.data.intent,
        graph_data: response.data.graph_data,
        list_data: response.data.list_data,
        ac_data: response.data.ac_data,
        suggestions: response.data.suggestions,
      }

      setMessages((prev) => {
        const next = [...prev, assistantMessage]
        setAnimatingIndex(next.length - 1)
        return next
      })

      setActiveAgent({
        agent: response.data.active_agent || 'fallback',
        info: response.data.agent_info,
      })

      const planReq: PlanRequest | undefined = response.data.plan_request
      if (planReq) {
        setPlannerCurso(planReq.curso || null)
        setPlannerOpen(true)
      }

      if (!conversationId) setConversationId(response.data.conversation_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao processar. Tente novamente.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSend = () => sendMessage(input)

  const handleGraphAsk = (question: string) => {
    if (isLoading) return
    setInput(question)
    sendMessage(question)
  }

  const handleHistoricoFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !conversationId) return
    const form = new FormData()
    form.append('file', file)
    form.append('conversation_id', conversationId)
    setIsLoading(true)
    setError(null)
    try {
      const resp = await axios.post(`${API_URL}/historico`, form)
      setHistoricoCarregado(true)
      setConfete((c) => c + 1)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resp.data.resumo,
          active_agent: 'symbolic_kg',
          suggestions: resp.data.suggestions,
        },
      ])
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Não consegui ler o histórico.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDrawerAsk = (question: string) => {
    setSelectedDiscipline(null)
    setSelectedDocente(null)
    handleGraphAsk(question)
  }

  const openDisciplina = (nome: string) => {
    setSelectedDocente(null)
    setSelectedDiscipline(nome)
  }

  const openDocente = (nome: string) => {
    setSelectedDiscipline(null)
    setSelectedDocente(nome)
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

      <h1 className="sr-only">FESP-AI - Assistente acadêmico da UNIFESP ICT</h1>
      <a
        href="#chat-main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:border focus:border-accent focus:bg-ink focus:px-4 focus:py-2 focus:text-sm focus:text-paper"
      >
        Pular para a conversa
      </a>

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
                onClick={() => { setPlannerCurso(null); setPlannerOpen(true) }}
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

              <button
                onClick={() => fileInputRef.current?.click()}
                title={historicoCarregado ? 'Histórico carregado nesta conversa' : 'Enviar seu Histórico Acadêmico (PDF) para respostas personalizadas'}
                className={`flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm transition-colors ${
                  historicoCarregado
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-line text-paper-dim hover:border-line-strong hover:text-paper'
                }`}
              >
                <FileUp className="h-4 w-4" />
                <span className="hidden sm:inline">
                  {historicoCarregado ? 'Histórico ✓' : 'Histórico'}
                </span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleHistoricoFile}
                className="hidden"
                aria-label="Enviar Histórico Acadêmico em PDF"
              />

              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <main id="chat-main" ref={messagesContainerRef} className="relative z-10 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">

          {messages.length === 0 && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex min-h-[55vh] flex-col justify-center"
            >
              <p className="mb-4 font-mono text-xs uppercase tracking-[0.25em] text-accent">
                UNIFESP - ICT
              </p>
              <h2 className="font-display text-3xl font-medium tracking-tightest text-paper sm:text-4xl">
                <DecryptText text="O que você quer saber?" delay={250} />
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
                        onAsk={handleGraphAsk}
                        onSelectDiscipline={openDisciplina}
                        showSuggestions={idx === messages.length - 1 && !isLoading}
                      />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

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

      <footer className="relative z-20 border-t border-line bg-ink/80 backdrop-blur-xl">
        <div className="mx-auto max-w-3xl px-4 py-5 sm:px-6">
          <div className="flex items-end gap-3">
            <div className="chat-input-glow w-full flex-1">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onInput={handleTextareaInput}
                placeholder={placeholder}
                rows={1}
                disabled={isLoading}
                className="w-full resize-none overflow-hidden rounded-xl border border-line bg-ink-raise px-5 py-[15px] text-[15px] leading-relaxed text-paper placeholder-paper-mute transition-colors focus:border-accent/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                style={{ minHeight: '54px', maxHeight: '160px' }}
              />
            </div>

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

      <GraphConfetti trigger={confete} />

      <AnimatePresence>
        {plannerOpen && (
          <PlannerDrawer
            apiUrl={API_URL}
            conversationId={conversationId}
            historicoCarregado={historicoCarregado}
            cursoInicial={plannerCurso}
            onClose={() => setPlannerOpen(false)}
            onOpenDiscipline={openDisciplina}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedDiscipline && (
          <DisciplineDrawer
            key={selectedDiscipline}
            nome={selectedDiscipline}
            apiUrl={API_URL}
            onClose={() => setSelectedDiscipline(null)}
            onNavigate={openDisciplina}
            onOpenDocente={openDocente}
            onAsk={handleDrawerAsk}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedDocente && (
          <DocenteDrawer
            key={selectedDocente}
            nome={selectedDocente}
            apiUrl={API_URL}
            onClose={() => setSelectedDocente(null)}
            onOpenDisciplina={openDisciplina}
            onAsk={handleDrawerAsk}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
