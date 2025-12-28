'use client'

import { useState, useRef, useEffect } from 'react'
import { 
  Send, 
  Bot, 
  Sparkles, 
  Plus,
  GraduationCap,
  Zap,
  ArrowDown,
} from 'lucide-react'
import axios from 'axios'
import ThemeToggle from './components/ThemeToggle'
import FloatingParticles from './components/FloatingParticles'
import LoadingDots from './components/LoadingDots'
import Avatar from './components/Avatar'
import SuggestionCard from './components/SuggestionCard'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const exampleQuestions = [
  { text: 'Quais são os pré-requisitos de Cálculo?', icon: 'book' as const },
  { text: 'Como funciona o sistema de avaliação?', icon: 'help' as const },
  { text: 'Quais disciplinas são obrigatórias?', icon: 'sparkle' as const },
  { text: 'Explique sobre atividades complementares', icon: 'message' as const },
]

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    createNewConversation()
  }, [])

  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100
      setShowScrollButton(!isNearBottom && messages.length > 0)
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
    } catch (err) {
      console.error('Erro ao criar conversa:', err)
      setError('Não foi possível inicializar a conversa. Verifique sua conexão.')
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setError(null)

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }

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
      }

      setMessages((prev) => [...prev, assistantMessage])

      if (!conversationId) {
        setConversationId(response.data.conversation_id)
      }
    } catch (err: any) {
      console.error('Erro ao enviar mensagem:', err)
      setError(err.response?.data?.detail || 'Erro ao processar sua mensagem. Tente novamente.')
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

  const handleNewChat = () => {
    createNewConversation()
  }

  const handleSuggestionClick = (question: string) => {
    setInput(question)
    inputRef.current?.focus()
  }

  const handleTextareaInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const target = e.target as HTMLTextAreaElement
    target.style.height = 'auto'
    target.style.height = `${Math.min(target.scrollHeight, 160)}px`
  }

  return (
    <div className="relative flex flex-col h-screen overflow-hidden bg-slate-50 dark:bg-[#0a0f1a]">
      {/* Aurora Background */}
      <div className="fixed inset-0 gradient-mesh animate-aurora pointer-events-none" />
      
      {/* Grid Pattern Overlay */}
      <div className="fixed inset-0 grid-pattern pointer-events-none" />
      
      {/* Floating Particles */}
      <FloatingParticles />

      {/* Decorative Orbs */}
      <div className="fixed top-0 left-0 w-[600px] h-[600px] rounded-full bg-gradient-to-br from-emerald-400/20 to-cyan-400/10 blur-3xl animate-float-orb pointer-events-none" />
      <div className="fixed bottom-0 right-0 w-[500px] h-[500px] rounded-full bg-gradient-to-tl from-violet-400/15 to-emerald-400/10 blur-3xl animate-float-orb-reverse pointer-events-none" />

      {/* ===== HEADER ===== */}
      <header className="relative z-20 glass-strong border-b border-white/10 dark:border-slate-700/50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Logo Section */}
            <div className="flex items-center gap-4 animate-slide-down">
              {/* Logo Icon */}
              <div className="relative group">
                {/* Glow Effect */}
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-400 to-cyan-400 rounded-2xl blur-xl opacity-50 group-hover:opacity-70 transition-opacity duration-500 animate-pulse-ring" />
                
                {/* Main Logo Container */}
                <div className="relative w-14 h-14 bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-600 rounded-2xl flex items-center justify-center shadow-xl shadow-emerald-500/30 border border-white/20 group-hover:scale-105 transition-transform duration-300">
                  <GraduationCap className="w-7 h-7 text-white drop-shadow-lg" />
                </div>
                
                {/* Live Indicator */}
                <div className="absolute -top-1 -right-1">
                  <span className="relative flex h-4 w-4">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500 border-2 border-white dark:border-slate-900" />
                  </span>
                </div>
              </div>

              {/* Brand Text */}
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
                  <span className="animate-text-shimmer">FESP-AI</span>
                </h1>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium hidden sm:block">
                  Assistente Inteligente UNIFESP
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 animate-slide-down delay-100">
              {/* New Chat Button */}
              <button
                onClick={handleNewChat}
                className="
                  flex items-center gap-2 px-4 py-2.5 rounded-xl
                  bg-white/80 dark:bg-slate-800/80
                  border border-slate-200/50 dark:border-slate-700/50
                  text-slate-700 dark:text-slate-200
                  font-medium text-sm
                  shadow-lg shadow-slate-200/50 dark:shadow-slate-900/50
                  hover:bg-white dark:hover:bg-slate-800
                  hover:border-emerald-300 dark:hover:border-emerald-700
                  hover:shadow-xl
                  transition-all duration-300
                  group
                "
              >
                <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
                <span className="hidden sm:inline">Nova Conversa</span>
              </button>

              {/* Theme Toggle */}
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* ===== MAIN CONTENT ===== */}
      <main 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto relative z-10"
      >
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Empty State - Welcome Screen */}
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
              {/* Hero Icon */}
              <div className="relative mb-8 animate-scale-bounce">
                <div className="absolute inset-0 w-28 h-28 bg-gradient-to-br from-emerald-400 to-cyan-400 rounded-3xl blur-2xl opacity-40 animate-pulse-ring" />
                <div className="relative w-28 h-28 bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-600 rounded-3xl flex items-center justify-center shadow-2xl shadow-emerald-500/40 border border-white/20">
                  <Sparkles className="w-14 h-14 text-white animate-icon-bounce" />
                </div>
              </div>

              {/* Welcome Text */}
              <h2 className="text-3xl sm:text-4xl font-bold text-slate-800 dark:text-white mb-4 animate-slide-up">
                Olá! Como posso ajudar?
              </h2>
              <p className="text-lg text-slate-600 dark:text-slate-400 mb-10 max-w-2xl animate-slide-up delay-100">
                Faça perguntas sobre disciplinas, regimentos e informações acadêmicas da{' '}
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  UNIFESP Campus São José dos Campos
                </span>
              </p>

              {/* Suggestion Cards */}
              <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-4">
                {exampleQuestions.map((q, index) => (
                  <SuggestionCard
                    key={index}
                    question={q.text}
                    icon={q.icon}
                    delay={200 + index * 100}
                    onClick={() => handleSuggestionClick(q.text)}
                  />
                ))}
              </div>

              {/* Powered By Badge */}
              <div className="mt-12 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-500 animate-slide-up delay-700">
                <Zap className="w-4 h-4 text-emerald-500" />
                <span>Powered by Advanced RAG Technology</span>
              </div>
            </div>
          )}

          {/* Messages */}
          <div className="space-y-6">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`
                  flex gap-4 animate-message
                  ${message.role === 'user' ? 'justify-end' : 'justify-start'}
                `}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Assistant Avatar */}
                {message.role === 'assistant' && (
                  <Avatar type="assistant" />
                )}

                {/* Message Bubble */}
                <div
                  className={`
                    max-w-[85%] sm:max-w-[75%] px-5 py-4
                    ${message.role === 'user' ? 'message-user' : 'message-assistant'}
                    transition-all duration-300
                  `}
                >
                  <p className="whitespace-pre-wrap break-words leading-relaxed text-[15px]">
                    {message.content}
                  </p>
                </div>

                {/* User Avatar */}
                {message.role === 'user' && (
                  <Avatar type="user" />
                )}
              </div>
            ))}

            {/* Loading State */}
            {isLoading && (
              <div className="flex gap-4 justify-start animate-message">
                <Avatar type="assistant" isAnimating />
                <div className="message-assistant px-6 py-5">
                  <div className="flex items-center gap-3">
                    <LoadingDots />
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      {messages.length === 0 ? (
                        <span className="flex items-center gap-2">
                          Inicializando
                          <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                            (primeira vez pode demorar ~30s)
                          </span>
                        </span>
                      ) : (
                        'Pensando...'
                      )}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="animate-message flex justify-center">
                <div className="
                  glass px-5 py-4 rounded-2xl
                  border border-red-200 dark:border-red-800/50
                  bg-red-50/80 dark:bg-red-900/20
                ">
                  <p className="text-sm text-red-700 dark:text-red-400 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    {error}
                  </p>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Scroll to Bottom Button */}
        {showScrollButton && (
          <button
            onClick={() => scrollToBottom()}
            className="
              fixed bottom-32 right-8 z-30
              w-12 h-12 rounded-full
              bg-white dark:bg-slate-800
              border border-slate-200 dark:border-slate-700
              shadow-xl shadow-slate-200/50 dark:shadow-slate-900/50
              flex items-center justify-center
              hover:bg-emerald-50 dark:hover:bg-emerald-900/30
              hover:border-emerald-300 dark:hover:border-emerald-700
              transition-all duration-300
              animate-slide-up
            "
          >
            <ArrowDown className="w-5 h-5 text-slate-600 dark:text-slate-300" />
          </button>
        )}
      </main>

      {/* ===== INPUT AREA ===== */}
      <footer className="relative z-20 glass-strong border-t border-white/10 dark:border-slate-700/50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex gap-4 items-end">
            {/* Input Container */}
            <div className="flex-1 relative group">
              {/* Glow Effect */}
              <div className="
                absolute inset-0 rounded-2xl
                bg-gradient-to-r from-emerald-400/20 to-cyan-400/20
                blur-xl opacity-0 group-focus-within:opacity-100
                transition-opacity duration-500
              " />
              
              {/* Textarea */}
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onInput={handleTextareaInput}
                placeholder="Digite sua pergunta sobre a UNIFESP..."
                rows={1}
                disabled={isLoading}
                className="
                  relative w-full px-5 py-4 pr-14
                  input-glass
                  text-slate-900 dark:text-white
                  placeholder-slate-400 dark:placeholder-slate-500
                  text-[15px] leading-relaxed
                  resize-none overflow-hidden
                  disabled:opacity-60 disabled:cursor-not-allowed
                "
                style={{ minHeight: '56px', maxHeight: '160px' }}
              />
            </div>

            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="
                flex-shrink-0 w-14 h-14
                btn-primary
                flex items-center justify-center
                disabled:opacity-50 disabled:cursor-not-allowed
                disabled:hover:transform-none disabled:hover:shadow-none
                group
              "
            >
              <span className="relative z-10">
                {isLoading ? (
                  <LoadingDots />
                ) : (
                  <Send className="w-5 h-5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform duration-300" />
                )}
              </span>
            </button>
          </div>

          {/* Keyboard Hints */}
          <p className="text-xs text-slate-500 dark:text-slate-500 mt-3 text-center">
            Pressione{' '}
            <kbd className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded font-mono text-[10px] border border-slate-200 dark:border-slate-700">
              Enter
            </kbd>
            {' '}para enviar,{' '}
            <kbd className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded font-mono text-[10px] border border-slate-200 dark:border-slate-700">
              Shift + Enter
            </kbd>
            {' '}para nova linha
          </p>
        </div>
      </footer>
    </div>
  )
}
