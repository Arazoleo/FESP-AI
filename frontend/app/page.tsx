'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader2, Sparkles, MessageSquare, GraduationCap } from 'lucide-react'
import axios from 'axios'
import ThemeToggle from './components/ThemeToggle'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    createNewConversation()
  }, [])

  const createNewConversation = async () => {
    try {
      const response = await axios.post(`${API_URL}/conversations`)
      setConversationId(response.data.conversation_id)
      setMessages([])
      setError(null)
    } catch (err) {
      console.error('Erro ao criar conversa:', err)
      setError('Erro ao inicializar conversa')
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    }

    setMessages((prev: Message[]) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setError(null)

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

      setMessages((prev: Message[]) => [...prev, assistantMessage])
      
      if (!conversationId) {
        setConversationId(response.data.conversation_id)
      }
    } catch (err: any) {
      console.error('Erro ao enviar mensagem:', err)
      setError(err.response?.data?.detail || 'Erro ao processar mensagem')
      setMessages((prev: Message[]) => prev.slice(0, -1))
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    createNewConversation()
  }

  const exampleQuestions = [
    'Quais são os pré-requisitos de Cálculo?',
    'Como funciona o sistema de avaliação?',
    'Quais disciplinas são obrigatórias?',
    'Explique sobre atividades complementares',
  ]

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 overflow-hidden">
      {/* Background decorative elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-0 w-96 h-96 bg-primary-200/20 dark:bg-primary-900/10 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-primary-300/20 dark:bg-primary-800/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-primary-400/10 dark:bg-primary-700/5 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '2s' }} />
      </div>

      {/* Header */}
      <header className="relative z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-primary-200/50 dark:border-primary-800/50 shadow-lg">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4 animate-fade-in-down">
            <div className="relative">
              <div className="w-14 h-14 bg-gradient-unifesp rounded-2xl flex items-center justify-center shadow-glow animate-scale-in">
                <GraduationCap className="w-8 h-8 text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-primary-400 rounded-full animate-ping" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-600 to-primary-500 dark:from-primary-400 dark:to-primary-300 bg-clip-text text-transparent">
                FESP-AI
              </h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                Assistente Inteligente UNIFESP
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleNewChat}
              className="hidden sm:flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100/80 dark:bg-slate-800/80 hover:bg-primary-100 dark:hover:bg-primary-900/50 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95 backdrop-blur-sm border border-slate-200/50 dark:border-slate-700/50"
              title="Nova conversa"
            >
              <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-400" />
              <span>Nova Conversa</span>
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto relative z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-16 animate-fade-in-up">
              <div className="relative inline-block mb-6">
                <div className="absolute inset-0 bg-gradient-unifesp rounded-full blur-xl opacity-50 animate-pulse" />
                <div className="relative w-24 h-24 bg-gradient-unifesp rounded-full flex items-center justify-center shadow-glow-lg animate-float">
                  <Bot className="w-12 h-12 text-white" />
                </div>
              </div>
              <h2 className="text-4xl font-bold text-slate-900 dark:text-white mb-3 bg-gradient-to-r from-primary-700 to-primary-500 dark:from-primary-400 dark:to-primary-300 bg-clip-text text-transparent">
                Olá! Como posso ajudar?
              </h2>
              <p className="text-lg text-slate-600 dark:text-slate-400 mb-8 max-w-2xl mx-auto">
                Faça perguntas sobre disciplinas, regimentos e informações acadêmicas da UNIFESP Campus São José dos Campos
              </p>
              
              {/* Example questions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl mx-auto mt-8">
                {exampleQuestions.map((question: string, index: number) => (
                  <button
                    key={index}
                    onClick={() => setInput(question)}
                    className="text-left px-4 py-3 bg-white/60 dark:bg-slate-800/60 backdrop-blur-sm border border-primary-200/50 dark:border-primary-800/50 rounded-xl hover:bg-primary-50 dark:hover:bg-primary-900/30 hover:border-primary-300 dark:hover:border-primary-700 transition-all duration-300 hover:scale-105 active:scale-95 animate-fade-in-up"
                    style={{ animationDelay: `${index * 0.1}s` }}
                  >
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-primary-600 dark:text-primary-400 flex-shrink-0" />
                      <span className="text-sm text-slate-700 dark:text-slate-300 font-medium">
                        {question}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex gap-4 animate-fade-in-up ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
              style={{ animationDelay: `${index * 0.05}s` }}
            >
              {message.role === 'assistant' && (
                <div className="flex-shrink-0 relative">
                  <div className="absolute inset-0 bg-gradient-unifesp rounded-full blur-md opacity-30" />
                  <div className="relative w-10 h-10 bg-gradient-unifesp rounded-full flex items-center justify-center shadow-lg">
                    <Bot className="w-6 h-6 text-white" />
                  </div>
                </div>
              )}
              
              <div
                className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-5 py-4 shadow-lg backdrop-blur-sm transition-all duration-300 hover:scale-[1.02] ${
                  message.role === 'user'
                    ? 'bg-gradient-unifesp text-white animate-slide-in-right'
                    : 'bg-white/80 dark:bg-slate-800/80 text-slate-900 dark:text-white border border-primary-200/50 dark:border-primary-800/50 animate-slide-in-left'
                }`}
              >
                <p className="whitespace-pre-wrap break-words leading-relaxed">
                  {message.content}
                </p>
              </div>

              {message.role === 'user' && (
                <div className="flex-shrink-0 relative">
                  <div className="absolute inset-0 bg-slate-400 dark:bg-slate-600 rounded-full blur-md opacity-30" />
                  <div className="relative w-10 h-10 bg-gradient-to-br from-slate-400 to-slate-500 dark:from-slate-600 dark:to-slate-700 rounded-full flex items-center justify-center shadow-lg">
                    <User className="w-6 h-6 text-white" />
                  </div>
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-4 justify-start animate-fade-in">
              <div className="flex-shrink-0 relative">
                <div className="absolute inset-0 bg-gradient-unifesp rounded-full blur-md opacity-30 animate-pulse" />
                <div className="relative w-10 h-10 bg-gradient-unifesp rounded-full flex items-center justify-center shadow-lg">
                  <Bot className="w-6 h-6 text-white" />
                </div>
              </div>
              <div className="bg-white/80 dark:bg-slate-800/80 rounded-2xl px-5 py-4 border border-primary-200/50 dark:border-primary-800/50 shadow-lg backdrop-blur-sm">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 text-primary-600 dark:text-primary-400 animate-spin" />
                  <span className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                    Processando... {messages.length === 0 && (
                      <span className="text-primary-600 dark:text-primary-400">(primeira vez pode demorar ~30s)</span>
                    )}
                  </span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50/80 dark:bg-red-900/20 backdrop-blur-sm border border-red-200 dark:border-red-800/50 rounded-xl px-5 py-4 text-red-700 dark:text-red-400 shadow-lg animate-fade-in">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{error}</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="relative z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-t border-primary-200/50 dark:border-primary-800/50 shadow-2xl">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex gap-3 items-end">
            <div className="flex-1 relative group">
              <div className="absolute inset-0 bg-gradient-unifesp rounded-2xl blur opacity-0 group-hover:opacity-20 transition-opacity duration-300" />
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Digite sua pergunta sobre a UNIFESP..."
                rows={1}
                className="relative w-full px-5 py-4 pr-14 bg-slate-50/80 dark:bg-slate-800/80 backdrop-blur-sm border-2 border-slate-200/50 dark:border-slate-700/50 rounded-2xl text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-400 dark:focus:border-primary-600 resize-none max-h-32 overflow-y-auto transition-all duration-300 shadow-lg"
                style={{
                  minHeight: '56px',
                  height: 'auto',
                }}
                onInput={(e: React.FormEvent<HTMLTextAreaElement>) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = `${Math.min(target.scrollHeight, 128)}px`
                }}
                disabled={isLoading}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="flex-shrink-0 w-14 h-14 bg-gradient-unifesp hover:shadow-glow disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-2xl flex items-center justify-center transition-all duration-300 shadow-lg hover:scale-110 active:scale-95 disabled:hover:scale-100 group"
            >
              {isLoading ? (
                <Loader2 className="w-6 h-6 animate-spin" />
              ) : (
                <Send className="w-6 h-6 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-3 text-center">
            Pressione <kbd className="px-2 py-1 bg-slate-200/50 dark:bg-slate-700/50 rounded">Enter</kbd> para enviar, <kbd className="px-2 py-1 bg-slate-200/50 dark:bg-slate-700/50 rounded">Shift+Enter</kbd> para nova linha
          </p>
        </div>
      </div>
    </div>
  )
}
