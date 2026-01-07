'use client'

import { useState, useRef, useEffect } from 'react'
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
} from 'lucide-react'
import axios from 'axios'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const suggestions = [
  { text: 'Quais são os pré-requisitos de Cálculo Numérico?', icon: BookOpen },
  { text: 'Quem leciona Algoritmos e Estrutura de Dados?', icon: HelpCircle },
  { text: 'Qual a carga horária de Física I?', icon: Lightbulb },
  { text: 'Me fale sobre os cursos de graduação', icon: MessageSquare },
]

export default function ChatPage() {
  const router = useRouter()
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
    inputRef.current?.focus()
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
      setError('Não foi possível conectar ao servidor.')
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
    <div className="relative flex flex-col h-screen bg-[#030712] text-white overflow-hidden">
      {/* ===== ANIMATED BACKGROUND ===== */}
      <div className="fixed inset-0 pointer-events-none">
        {/* Gradient Orbs */}
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full opacity-20 blur-[100px] bg-emerald-500" />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full opacity-15 blur-[80px] bg-cyan-500" />
        
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cpath%20d%3D%22M0%200h60v60H0z%22%2F%3E%3Cpath%20d%3D%22M60%200v60H0%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.03)%22%20stroke-width%3D%221%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E')] opacity-50" />
      </div>

      {/* ===== HEADER ===== */}
      <header className="relative z-20 border-b border-white/5 bg-black/40 backdrop-blur-2xl">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Back + Logo */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/')}
                className="
                  p-2.5 rounded-xl
                  bg-white/5 border border-white/10
                  hover:bg-white/10 hover:border-white/20
                  transition-all duration-300
                "
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

            {/* New Chat Button */}
            <button
              onClick={createNewConversation}
              className="
                flex items-center gap-2 px-4 py-2.5 rounded-xl
                bg-white/5 border border-white/10
                text-slate-300 font-medium text-sm
                hover:bg-white/10 hover:border-emerald-500/30
                transition-all duration-300
                group
              "
            >
              <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
              <span className="hidden sm:inline">Nova Conversa</span>
            </button>
          </div>
        </div>
      </header>

      {/* ===== MAIN CONTENT ===== */}
      <main 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto relative z-10"
      >
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Empty State */}
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
              {/* Hero Icon */}
              <div className="relative mb-8">
                <div className="absolute inset-0 w-24 h-24 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-3xl blur-2xl opacity-40 animate-pulse" />
                <div className="relative w-24 h-24 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-3xl flex items-center justify-center shadow-2xl shadow-emerald-500/30">
                  <Sparkles className="w-12 h-12 text-white" />
                </div>
              </div>

              {/* Welcome Text */}
              <h2 className="text-3xl sm:text-4xl font-bold mb-4 bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                Como posso ajudar?
              </h2>
              <p className="text-lg text-slate-500 mb-10 max-w-xl">
                Pergunte sobre disciplinas, docentes, regimentos e informações da UNIFESP
              </p>

              {/* Suggestion Cards */}
              <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-3">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => handleSuggestionClick(suggestion.text)}
                    className="
                      group flex items-start gap-3 p-4 rounded-2xl text-left
                      bg-white/[0.02] border border-white/[0.05]
                      hover:bg-white/[0.05] hover:border-emerald-500/30
                      transition-all duration-300
                    "
                  >
                    <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20 transition-colors">
                      <suggestion.icon className="w-4 h-4" />
                    </div>
                    <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors leading-relaxed">
                      {suggestion.text}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          <div className="space-y-6">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {/* Assistant Avatar */}
                {message.role === 'assistant' && (
                  <div className="flex-shrink-0">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                  </div>
                )}

                {/* Message Bubble */}
                <div
                  className={`
                    max-w-[80%] sm:max-w-[70%] px-5 py-4 rounded-2xl
                    ${message.role === 'user' 
                      ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white rounded-br-md shadow-lg shadow-emerald-500/20' 
                      : 'bg-white/[0.03] border border-white/[0.05] text-slate-200 rounded-bl-md'
                    }
                  `}
                >
                  <p className="whitespace-pre-wrap break-words leading-relaxed text-[15px]">
                    {message.content}
                  </p>
                </div>

                {/* User Avatar */}
                {message.role === 'user' && (
                  <div className="flex-shrink-0">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center shadow-lg shadow-violet-500/20">
                      <User className="w-5 h-5 text-white" />
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Loading State */}
            {isLoading && (
              <div className="flex gap-4 justify-start">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 animate-pulse">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                </div>
                <div className="bg-white/[0.03] border border-white/[0.05] px-6 py-5 rounded-2xl rounded-bl-md">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map((i) => (
                        <div
                          key={i}
                          className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }}
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
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="flex justify-center">
                <div className="px-5 py-4 rounded-2xl bg-red-500/10 border border-red-500/20">
                  <p className="text-sm text-red-400 flex items-center gap-2">
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
              bg-white/10 border border-white/10
              backdrop-blur-xl
              flex items-center justify-center
              hover:bg-white/20 hover:border-emerald-500/30
              transition-all duration-300
            "
          >
            <ArrowDown className="w-5 h-5 text-slate-300" />
          </button>
        )}
      </main>

      {/* ===== INPUT AREA ===== */}
      <footer className="relative z-20 border-t border-white/5 bg-black/40 backdrop-blur-2xl">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex gap-4 items-end">
            {/* Input Container */}
            <div className="flex-1 relative group">
              {/* Glow Effect */}
              <div className="
                absolute inset-0 rounded-2xl
                bg-gradient-to-r from-emerald-500/20 to-cyan-500/20
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
                placeholder="Digite sua pergunta..."
                rows={1}
                disabled={isLoading}
                className="
                  relative w-full px-5 py-4 pr-14
                  bg-white/[0.03] border-2 border-white/[0.05]
                  rounded-2xl
                  text-white placeholder-slate-500
                  text-[15px] leading-relaxed
                  resize-none overflow-hidden
                  focus:outline-none focus:border-emerald-500/50
                  focus:shadow-[0_0_30px_rgba(16,185,129,0.15)]
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-all duration-300
                "
                style={{ minHeight: '56px', maxHeight: '160px' }}
              />
            </div>

            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="
                flex-shrink-0 w-14 h-14 rounded-2xl
                bg-gradient-to-r from-emerald-500 to-cyan-500
                text-white
                flex items-center justify-center
                disabled:opacity-30 disabled:cursor-not-allowed
                hover:shadow-[0_0_30px_rgba(16,185,129,0.4)]
                hover:scale-105 active:scale-95
                transition-all duration-300
                group
              "
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform duration-300" />
              )}
            </button>
          </div>

          {/* Keyboard Hints */}
          <p className="text-xs text-slate-600 mt-3 text-center">
            <kbd className="px-2 py-0.5 bg-white/5 text-slate-500 rounded text-[10px] border border-white/10">Enter</kbd>
            {' '}para enviar • {' '}
            <kbd className="px-2 py-0.5 bg-white/5 text-slate-500 rounded text-[10px] border border-white/10">Shift + Enter</kbd>
            {' '}para nova linha
          </p>
        </div>
      </footer>
    </div>
  )
}

