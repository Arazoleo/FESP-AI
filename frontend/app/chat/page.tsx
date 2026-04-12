'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  Send,
  Sparkles,
  Plus,
  GraduationCap,
  ArrowDown,
  ArrowLeft,
  BookOpen,
  HelpCircle,
  MessageSquare,
  Lightbulb,
  Bot,
  User,
  Loader2,
  Users,
  FileText,
  Brain,
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

// ─── Constantes ───────────────────────────────────────────────────────────────

const AGENT_ICONS: Record<string, React.ElementType> = {
  BookOpen, GraduationCap, Users, FileText, Bot, Brain,
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const suggestions = [
  { text: 'Quais são os pré-requisitos de Cálculo Numérico?', icon: BookOpen },
  { text: 'Quem leciona Algoritmos e Estrutura de Dados?', icon: HelpCircle },
  { text: 'Qual a carga horária de Física I?', icon: Lightbulb },
  { text: 'Me fale sobre os cursos de graduação', icon: MessageSquare },
]

// ─── Componentes auxiliares ───────────────────────────────────────────────────

function AgentBadge({ agent, agentInfo }: { agent: string; agentInfo?: AgentInfo }) {
  const Icon = AGENT_ICONS[agentInfo?.icon || 'Bot'] || Bot
  const color = agentInfo?.color || '#6b7280'
  const label = agentInfo?.label || agent
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium mb-2"
      style={{
        backgroundColor: `${color}18`,
        border: `1px solid ${color}40`,
        color,
      }}
    >
      <Icon className="w-3 h-3" />
      <span>{label}</span>
    </div>
  )
}

// ─── Markdown com estilo customizado ─────────────────────────────────────────

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => (
    <p className="mb-3 last:mb-0 leading-relaxed text-slate-200">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-slate-300">{children}</em>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.includes('language-')
    return isBlock ? (
      <code className="block my-2 p-3 rounded-xl bg-black/40 border border-white/10 text-emerald-300 text-[13px] font-mono whitespace-pre-wrap leading-relaxed">
        {children}
      </code>
    ) : (
      <code className="px-1.5 py-0.5 rounded-md bg-white/10 text-emerald-300 text-[13px] font-mono">
        {children}
      </code>
    )
  },
  pre: ({ children }) => <>{children}</>,
  ul: ({ children }) => (
    <ul className="my-2 space-y-1.5 list-none pl-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 space-y-1.5 list-decimal pl-5 text-slate-200">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="flex items-start gap-2 text-slate-200">
      <span className="mt-[7px] w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
      <span className="flex-1">{children}</span>
    </li>
  ),
  h1: ({ children }) => (
    <h1 className="text-lg font-bold text-white mb-2 mt-3 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold text-white mb-2 mt-3 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-slate-100 mb-1.5 mt-2 first:mt-0">{children}</h3>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 pl-3 border-l-2 border-emerald-500/50 text-slate-400 italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-3 border-white/10" />,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-xl border border-white/10">
      <table className="min-w-full text-sm text-slate-200">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="px-4 py-2.5 bg-white/5 font-semibold text-white text-left border-b border-white/10">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-2.5 border-b border-white/5 text-slate-300">{children}</td>
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

// ─── Componente de mensagem do assistente ─────────────────────────────────────

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
        <AgentBadge agent={message.active_agent} agentInfo={message.agent_info} />
      )}

      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={mdComponents}
      >
        {textToRender}
      </ReactMarkdown>

      {/* Cursor piscante durante animação */}
      {isAnimating && !isDone && (
        <span className="inline-block w-[2px] h-[1em] bg-emerald-400 ml-0.5 align-middle animate-pulse" />
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
    <div className="relative flex flex-col h-screen bg-[#030712] text-white overflow-hidden">

      {/* ── Background ── */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full opacity-20 blur-[100px] bg-emerald-500" />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full opacity-15 blur-[80px] bg-cyan-500" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cpath%20d%3D%22M0%200h60v60H0z%22%2F%3E%3Cpath%20d%3D%22M60%200v60H0%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.03)%22%20stroke-width%3D%221%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E')] opacity-50" />
      </div>

      {/* ── Header ── */}
      <header className="relative z-20 border-b border-white/5 bg-black/40 backdrop-blur-2xl">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/')}
                className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all duration-300"
              >
                <ArrowLeft className="w-5 h-5 text-slate-400" />
              </button>

              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                    <GraduationCap className="w-6 h-6 text-white" />
                  </div>
                  <span className="absolute -top-0.5 -right-0.5 flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
                  </span>
                </div>
                <div>
                  <h1 className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                    FESP-AI
                  </h1>
                  <p className="text-xs text-slate-500 hidden sm:block">Assistente UNIFESP</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {activeAgent && !isLoading && (
                <motion.div
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all duration-500"
                  style={{
                    backgroundColor: `${activeAgent.info?.color || '#6b7280'}15`,
                    borderColor: `${activeAgent.info?.color || '#6b7280'}35`,
                    color: activeAgent.info?.color || '#6b7280',
                  }}
                >
                  {(() => { const Icon = AGENT_ICONS[activeAgent.info?.icon || 'Bot'] || Bot; return <Icon className="w-3.5 h-3.5" /> })()}
                  <span>{activeAgent.info?.label || activeAgent.agent}</span>
                </motion.div>
              )}

              {isLoading && (
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 animate-pulse">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processando...</span>
                </div>
              )}

              <button
                onClick={createNewConversation}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-slate-300 font-medium text-sm hover:bg-white/10 hover:border-emerald-500/30 transition-all duration-300 group"
              >
                <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
                <span className="hidden sm:inline">Nova Conversa</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ── Messages ── */}
      <main ref={messagesContainerRef} className="flex-1 overflow-y-auto relative z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

          {/* Empty state */}
          {messages.length === 0 && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center justify-center min-h-[60vh] text-center"
            >
              <div className="relative mb-8">
                <div className="absolute inset-0 w-24 h-24 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-3xl blur-2xl opacity-40 animate-pulse" />
                <div className="relative w-24 h-24 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-3xl flex items-center justify-center shadow-2xl shadow-emerald-500/30">
                  <Sparkles className="w-12 h-12 text-white" />
                </div>
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold mb-4 bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                Como posso ajudar?
              </h2>
              <p className="text-lg text-slate-500 mb-10 max-w-xl">
                Pergunte sobre disciplinas, docentes, regimentos e informações da UNIFESP
              </p>
              <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-3">
                {suggestions.map((s, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08 + 0.2 }}
                    onClick={() => { setInput(s.text); inputRef.current?.focus() }}
                    className="group flex items-start gap-3 p-4 rounded-2xl text-left bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.05] hover:border-emerald-500/30 transition-all duration-300"
                  >
                    <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20 transition-colors">
                      <s.icon className="w-4 h-4" />
                    </div>
                    <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors leading-relaxed">
                      {s.text}
                    </span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Lista de mensagens */}
          <div className="space-y-6">
            <AnimatePresence initial={false}>
              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 16, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {/* Avatar do assistente */}
                  {msg.role === 'assistant' && (
                    <div className="flex-shrink-0">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                        <Bot className="w-5 h-5 text-white" />
                      </div>
                    </div>
                  )}

                  {/* Balão */}
                  <div
                    className={`max-w-[82%] sm:max-w-[72%] rounded-2xl px-5 py-4 ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white rounded-br-md shadow-lg shadow-emerald-500/20'
                        : 'bg-white/[0.03] border border-white/[0.07] text-slate-200 rounded-bl-md'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <p className="whitespace-pre-wrap break-words leading-relaxed text-[15px]">
                        {msg.content}
                      </p>
                    ) : (
                      <AssistantMessage
                        message={msg}
                        isAnimating={idx === animatingIndex}
                        onAnimationDone={handleAnimationDone}
                      />
                    )}
                  </div>

                  {/* Avatar do usuário */}
                  {msg.role === 'user' && (
                    <div className="flex-shrink-0">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center shadow-lg shadow-violet-500/20">
                        <User className="w-5 h-5 text-white" />
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Loading — três pontinhos */}
            <AnimatePresence>
              {isLoading && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="flex gap-4 justify-start"
                >
                  <div className="flex-shrink-0">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 animate-pulse">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.07] px-6 py-5 rounded-2xl rounded-bl-md">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1.5">
                        {[0, 1, 2].map((i) => (
                          <motion.div
                            key={i}
                            className="w-2 h-2 rounded-full bg-emerald-500"
                            animate={{ y: [0, -6, 0] }}
                            transition={{
                              repeat: Infinity,
                              duration: 0.8,
                              delay: i * 0.15,
                              ease: 'easeInOut',
                            }}
                          />
                        ))}
                      </div>
                      <span className="text-sm text-slate-500">
                        {messages.length === 0 ? (
                          <span className="flex items-center gap-2">
                            Inicializando
                            <span className="text-emerald-400 text-xs">(~30s na primeira vez)</span>
                          </span>
                        ) : (
                          'Pensando...'
                        )}
                      </span>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Erro */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex justify-center"
                >
                  <div className="px-5 py-4 rounded-2xl bg-red-500/10 border border-red-500/20">
                    <p className="text-sm text-red-400 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      {error}
                    </p>
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
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={() => scrollToBottom()}
              className="fixed bottom-32 right-8 z-30 w-12 h-12 rounded-full bg-white/10 border border-white/10 backdrop-blur-xl flex items-center justify-center hover:bg-white/20 hover:border-emerald-500/30 transition-all duration-300"
            >
              <ArrowDown className="w-5 h-5 text-slate-300" />
            </motion.button>
          )}
        </AnimatePresence>
      </main>

      {/* ── Input ── */}
      <footer className="relative z-20 border-t border-white/5 bg-black/40 backdrop-blur-2xl">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex gap-4 items-end">
            <div className="flex-1 relative group">
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onInput={handleTextareaInput}
                placeholder="Digite sua pergunta..."
                rows={1}
                disabled={isLoading}
                className="relative w-full px-5 py-4 pr-14 bg-white/[0.03] border-2 border-white/[0.05] rounded-2xl text-white placeholder-slate-500 text-[15px] leading-relaxed resize-none overflow-hidden focus:outline-none focus:border-emerald-500/50 focus:shadow-[0_0_30px_rgba(16,185,129,0.15)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
                style={{ minHeight: '56px', maxHeight: '160px' }}
              />
            </div>

            <motion.button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="flex-shrink-0 w-14 h-14 rounded-2xl bg-gradient-to-r from-emerald-500 to-cyan-500 text-white flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-[0_0_30px_rgba(16,185,129,0.4)] transition-shadow duration-300"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </motion.button>
          </div>

          <p className="text-xs text-slate-600 mt-3 text-center">
            <kbd className="px-2 py-0.5 bg-white/5 text-slate-500 rounded text-[10px] border border-white/10">Enter</kbd>
            {' '}para enviar •{' '}
            <kbd className="px-2 py-0.5 bg-white/5 text-slate-500 rounded text-[10px] border border-white/10">Shift + Enter</kbd>
            {' '}para nova linha
          </p>
        </div>
      </footer>
    </div>
  )
}
